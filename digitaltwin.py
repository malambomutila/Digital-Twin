from __future__ import annotations

import json
import logging
import os
import re
import time
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gradio as gr
import requests
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

load_dotenv(override=True)

# Structured log formatter — emits JSON so HF Spaces logs are parseable.
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("duration_ms", "tokens_total", "tokens_prompt", "tokens_completion", "tool"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


_configure_logging()
logger = logging.getLogger("digital_twin")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    knowledge_dir: Path = field(default_factory=lambda: Path(os.getenv("KNOWLEDGE_DIR", "me")))
    max_context_chars: int = field(default_factory=lambda: int(os.getenv("MAX_CONTEXT_CHARS", "120000")))
    app_title: str = field(default_factory=lambda: os.getenv("APP_TITLE", "Malambo Mutila — Digital Twin"))
    app_description: str = field(
        default_factory=lambda: os.getenv(
            "APP_DESCRIPTION",
            "Malambo Mutila's AI digital twin",
        )
    )
    pushover_token: str | None = field(default_factory=lambda: os.getenv("PUSHOVER_TOKEN"))
    pushover_user: str | None = field(default_factory=lambda: os.getenv("PUSHOVER_USER"))
    lead_capture_enabled: bool = field(
        default_factory=lambda: os.getenv("LEAD_CAPTURE_ENABLED", "true").lower() == "true"
    )
    unknown_question_enabled: bool = field(
        default_factory=lambda: os.getenv("UNKNOWN_QUESTION_ENABLED", "true").lower() == "true"
    )
    # RAG settings
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "5")))
    rag_embedding_model: str = field(
        default_factory=lambda: os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )
    rag_chunk_size: int = field(default_factory=lambda: int(os.getenv("RAG_CHUNK_SIZE", "400")))
    rag_chunk_overlap: int = field(default_factory=lambda: int(os.getenv("RAG_CHUNK_OVERLAP", "80")))
    # Rate limiting: max lead captures per session
    lead_rate_limit: int = field(default_factory=lambda: int(os.getenv("LEAD_RATE_LIMIT", "3")))


SETTINGS = Settings(openai_api_key=os.environ["OPENAI_API_KEY"])


# -----------------------------------------------------------------------------
# Knowledge integrity check
# -----------------------------------------------------------------------------

# Maps filename → list of substrings that must appear in the file content.
REQUIRED_CONTENT: dict[str, list[str]] = {
    "profile.md": ["Name", "Location", "Title"],
    "experience.md": ["Organisation", "Period"],
    "education.md": ["Institution", "Year"],
    "summary.md": ["Malambo"],
    "skills.md": ["Python"],
    "publications.md": ["Article"],
    "projects.md": ["Type"],
    "andelabootcamp.md": ["Bootcamp"],
    "funfacts.md": ["Fun Facts"],
    "metadata.md": ["Primary Domains"],
    "retrievalkeywords.md": ["Data Engineering"],
}


def check_knowledge_integrity(knowledge_dir: Path) -> list[str]:
    """Return a list of integrity warnings. Empty list means all clear."""
    warnings: list[str] = []
    for filename, required_strings in REQUIRED_CONTENT.items():
        path = knowledge_dir / filename
        if not path.exists():
            warnings.append(f"MISSING FILE: {filename}")
            continue
        content = path.read_text(encoding="utf-8")
        for phrase in required_strings:
            if phrase not in content:
                warnings.append(f"{filename}: expected to contain '{phrase}' but it was not found.")
    return warnings


# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------


def push(text: str) -> None:
    if not SETTINGS.pushover_token or not SETTINGS.pushover_user:
        logger.info("Pushover not configured. Skipping notification: %s", text)
        return
    try:
        response = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": SETTINGS.pushover_token,
                "user": SETTINGS.pushover_user,
                "message": text,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to send Pushover notification: %s", exc)


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LEADS_FILE = LOG_DIR / "captured_leads.jsonl"
UNKNOWNS_FILE = LOG_DIR / "unknown_questions.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# -----------------------------------------------------------------------------
# Email validation
# -----------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


# -----------------------------------------------------------------------------
# Rate limiting (in-memory, per-session)
# -----------------------------------------------------------------------------

# Maps session_id → count of lead capture calls
_lead_counts: dict[str, int] = defaultdict(int)


def check_lead_rate_limit(session_id: str) -> bool:
    """Returns True if the session is within the allowed lead capture limit."""
    return _lead_counts[session_id] < SETTINGS.lead_rate_limit


def increment_lead_count(session_id: str) -> None:
    _lead_counts[session_id] += 1


# Session ID is injected via a gr.State — tools receive it through a closure.
_current_session_id: str = "default"


def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided") -> dict[str, str]:
    if not is_valid_email(email):
        logger.warning("Invalid email rejected: %s", email)
        return {"recorded": "error", "reason": "invalid_email"}

    if not check_lead_rate_limit(_current_session_id):
        logger.warning("Lead rate limit hit for session: %s", _current_session_id)
        return {"recorded": "error", "reason": "rate_limit_exceeded"}

    payload = {"email": email, "name": name, "notes": notes}
    _append_jsonl(LEADS_FILE, payload)
    increment_lead_count(_current_session_id)
    push(f"Lead captured | name={name} | email={email} | notes={notes}")
    logger.info("Lead recorded: email=%s name=%s", email, name)
    return {"recorded": "ok"}


def record_unknown_question(question: str) -> dict[str, str]:
    payload = {"question": question}
    _append_jsonl(UNKNOWNS_FILE, payload)
    push(f"Unknown question captured | {question}")
    logger.info("Unknown question recorded: %s", question)
    return {"recorded": "ok"}


RECORD_USER_DETAILS_TOOL = {
    "name": "record_user_details",
    "description": "Record a visitor's name, email, and context when they want to get in touch.",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The visitor's email address."},
            "name": {"type": "string", "description": "The visitor's name, if provided."},
            "notes": {
                "type": "string",
                "description": "Useful context about the conversation, opportunity, or reason for contact.",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

RECORD_UNKNOWN_QUESTION_TOOL = {
    "name": "record_unknown_question",
    "description": "Record a question that could not be answered from the current knowledge base.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The unanswered question."},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}


def build_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if SETTINGS.lead_capture_enabled:
        tools.append({"type": "function", "function": RECORD_USER_DETAILS_TOOL})
    if SETTINGS.unknown_question_enabled:
        tools.append({"type": "function", "function": RECORD_UNKNOWN_QUESTION_TOOL})
    return tools


TOOLS = build_tools()
TOOL_REGISTRY = {
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question,
}


# -----------------------------------------------------------------------------
# RAG — Knowledge Base with ChromaDB (in-memory, HF Spaces safe)
# -----------------------------------------------------------------------------

# Files that belong to the "bootcamp" scope for scoped retrieval.
BOOTCAMP_FILES = {"andelabootcamp.md"}
# Files that are strictly professional context.
PROFESSIONAL_FILES = {
    "profile.md", "summary.md", "education.md", "experience.md",
    "projects.md", "skills.md", "publications.md", "metadata.md",
}
# Files that apply to both scopes.
GENERAL_FILES = {"retrievalkeywords.md", "funfacts.md"}


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]

def _file_scope(filename: str) -> str:
    if filename in BOOTCAMP_FILES:
        return "bootcamp"
    if filename in PROFESSIONAL_FILES:
        return "professional"
    return "general"

def _detect_scope(query: str) -> str:
    """
    Returns 'bootcamp', 'professional', or 'general' based on query keywords.
    Used to bias retrieval toward the right document scope.
    """
    q = query.lower()
    bootcamp_signals = {
        "bootcamp", "andela", "week", "neural forge", "rag challenge", "agentic track",
        "counsel of agents", "estock", "llm engineering", "production track",
        "ed donner", "solidroad", "capstone",
    }
    professional_signals = {
        "experience", "job", "role", "work", "employment", "project", "publication",
        "skill", "education", "degree", "certificate", "idinsight", "znphi", "find",
        "madesh", "dhis2", "airflow", "pipeline", "dashboard", "warehouse",
    }
    bootcamp_hits = sum(1 for s in bootcamp_signals if s in q)
    professional_hits = sum(1 for s in professional_signals if s in q)

    if bootcamp_hits > professional_hits:
        return "bootcamp"
    if professional_hits > bootcamp_hits:
        return "professional"
    return "general"


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())

class LightKnowledgeBase:
    """
    Keyword-scored retrieval using TF-IDF. 
    Zero external dependencies beyond what you already have.
    """
    PREFERRED_ORDER = [
        "profile.md", "summary.md", "education.md", "experience.md",
        "projects.md", "skills.md", "publications.md", "retrievalkeywords.md",
        "andelabootcamp.md", "funfacts.md", "metadata.md",
    ]

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self.documents: list[tuple[str, str]] = self._load_documents()
        self._build_index()
        logger.info("Light knowledge base ready. %d files loaded.", len(self.documents))

    def _load_documents(self) -> list[tuple[str, str]]:
        if not self.knowledge_dir.exists():
            raise FileNotFoundError(f"Knowledge directory '{self.knowledge_dir}' does not exist.")
        discovered = {p.name: p for p in self.knowledge_dir.glob("*.md")}
        ordered = [n for n in self.PREFERRED_ORDER if n in discovered]
        remaining = sorted(n for n in discovered if n not in ordered)
        docs = []
        for name in ordered + remaining:
            content = discovered[name].read_text(encoding="utf-8").strip()
            if content:
                docs.append((name, content))
                logger.info("Loaded: %s", name)
        if not docs:
            raise ValueError(f"No markdown content found in '{self.knowledge_dir}'.")
        return docs

    def _build_index(self) -> None:
        """Precompute TF-IDF weights for each document."""
        N = len(self.documents)
        self._tf: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}
        token_sets = []

        for _, content in self.documents:
            tokens = _tokenize(content)
            counts = Counter(tokens)
            total = max(len(tokens), 1)
            tf = {word: count / total for word, count in counts.items()}
            self._tf.append(tf)
            token_sets.append(set(counts.keys()))

        # IDF: how rare is this word across all documents
        for word in set(w for ts in token_sets for w in ts):
            df = sum(1 for ts in token_sets if word in ts)
            self._idf[word] = math.log(N / df)

    def _score(self, query: str, doc_index: int) -> float:
        tf = self._tf[doc_index]
        return sum(
            tf.get(word, 0.0) * self._idf.get(word, 0.0)
            for word in _tokenize(query)
        )

    def retrieve(self, query: str, top_k: int | None = None) -> str:
        k = top_k or SETTINGS.rag_top_k
        scope = _detect_scope(query)

        scored = []
        for i, (filename, content) in enumerate(self.documents):
            file_scope = _file_scope(filename)
            score = self._score(query, i)
            # Boost documents that match the detected scope
            if scope != "general" and file_scope == scope:
                score *= 1.5
            scored.append((score, filename, content))

        scored.sort(reverse=True, key=lambda x: x[0])
        top = scored[:k]

        sections = [f"[SOURCE: {fn}]\n{content}" for _, fn, content in top if content]
        return "\n\n---\n\n".join(sections) if sections else "No relevant knowledge found."

    def list_sources(self) -> list[str]:
        return [name for name, _ in self.documents]

# -----------------------------------------------------------------------------
# Digital twin
# -----------------------------------------------------------------------------

class DigitalTwin:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=SETTINGS.openai_api_key)
        self.name = "Malambo Mutila"
        self.role = "AI/ML Engineer"

        # Run integrity check before loading
        warnings = check_knowledge_integrity(SETTINGS.knowledge_dir)
        if warnings:
            for w in warnings:
                logger.warning("Knowledge integrity: %s", w)
        else:
            logger.info("Knowledge integrity check passed.")

        self.knowledge_base = LightKnowledgeBase(SETTINGS.knowledge_dir)

    def _base_system_prompt(self) -> str:
        source_list = ", ".join(self.knowledge_base.list_sources())
        return f"""
You are acting as {self.name}, an experienced {self.role}.

Your job is to answer questions on {self.name}'s digital twin website accurately, professionally, warmly, and concisely.
You represent {self.name}'s real background, experience, projects, education, publications, skills, and bootcamp work.

Rules:
1. Stay grounded in the retrieved knowledge context provided in each message.
2. Do not invent experience, credentials, publications, or project outcomes.
3. If a detail is uncertain or not present in the retrieved context, say so briefly.
4. If the user asks something the knowledge base cannot answer, use the `record_unknown_question` tool.
5. If the user expresses hiring interest, collaboration interest, freelance interest, or asks to get in touch, politely ask for their email and use the `record_user_details` tool when they provide it.
6. Keep answers useful and natural, not robotic.
7. For recruiters or employers, emphasise relevant experience, business impact, technical breadth, and communication ability.
8. Fun facts are for light conversation only — do not include them in formal professional summaries unless explicitly asked.
9. When discussing bootcamp work, clearly separate it from professional work experience.
10. Use markdown formatting where it improves readability.

Available knowledge sources: {source_list}
        """.strip()

    def _build_messages(
        self,
        message: str,
        history: list[Any] | None,
        retrieved_context: str,
    ) -> list[dict[str, Any]]:
        system = self._base_system_prompt()
        context_block = f"\n\n## Retrieved Knowledge Context\n\n{retrieved_context}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system + context_block},
            *self._normalize_history(history),
            {"role": "user", "content": message},
        ]
        return messages

    def _normalize_history(self, history: list[Any] | None) -> list[dict[str, Any]]:
        if not history:
            return []
        normalized: list[dict[str, Any]] = []
        for item in history:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                user_msg, bot_msg = item
                if user_msg:
                    normalized.append({"role": "user", "content": str(user_msg)})
                if bot_msg:
                    normalized.append({"role": "assistant", "content": str(bot_msg)})
            elif isinstance(item, dict):
                role = item.get("role")
                content = item.get("content", "")
                if role in {"user", "assistant", "system", "tool"}:
                    normalized.append({"role": role, "content": content})
        return normalized

    def handle_tool_call(self, tool_calls: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            logger.info("Tool called", extra={"tool": tool_name})
            tool = TOOL_REGISTRY.get(tool_name)
            result = tool(**arguments) if tool else {"error": f"Unknown tool: {tool_name}"}
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })
        return results

    def chat(self, message: str, history: list[Any] | None) -> str:
        t_start = time.perf_counter()

        # RAG: retrieve relevant context for this specific query
        retrieved_context = self.knowledge_base.retrieve(message)
        messages = self._build_messages(message, history, retrieved_context)

        total_prompt_tokens = 0
        total_completion_tokens = 0

        while True:
            response = self.client.chat.completions.create(
                model=SETTINGS.openai_model,
                messages=messages,
                tools=TOOLS if TOOLS else None,
                temperature=0.3,
            )
            assistant_message = response.choices[0].message

            # Accumulate token usage
            if response.usage:
                total_prompt_tokens += response.usage.prompt_tokens
                total_completion_tokens += response.usage.completion_tokens

            if assistant_message.tool_calls:
                messages.append(assistant_message)
                messages.extend(self.handle_tool_call(assistant_message.tool_calls))
                continue

            duration_ms = int((time.perf_counter() - t_start) * 1000)
            logger.info(
                "Chat response complete",
                extra={
                    "duration_ms": duration_ms,
                    "tokens_prompt": total_prompt_tokens,
                    "tokens_completion": total_completion_tokens,
                    "tokens_total": total_prompt_tokens + total_completion_tokens,
                },
            )
            return assistant_message.content or "I'm sorry, I don't have a response right now."


# -----------------------------------------------------------------------------
# Gradio UI
# -----------------------------------------------------------------------------


def build_demo() -> gr.Blocks:
    twin = DigitalTwin()

    def chat_with_session(message: str, history: list[Any], session_id: str) -> str:
        global _current_session_id
        _current_session_id = session_id
        return twin.chat(message, history)

    import uuid

    with gr.Blocks(title=SETTINGS.app_title) as demo:
        # Each browser tab gets a unique session ID for rate limiting
        session_id = gr.State(value=lambda: str(uuid.uuid4()))

        gr.Markdown(f"# {SETTINGS.app_title}")
        gr.Markdown(SETTINGS.app_description)
        gr.Markdown(
            ""
        )
        # gr.Markdown(
        #     "Ask me about his work experience, projects, education, publications, skills, "
        #     "or how he, well, I can contribute to your team or project."
        # )

        gr.ChatInterface(
            fn=chat_with_session,
            additional_inputs=[session_id],
            chatbot=gr.Chatbot(height=650),
            textbox=gr.Textbox(
                placeholder="Type your own questions about Malambo's background, projects, skills, or publications...",
                container=False,
                scale=7,
            ),
            examples=[
                ["Give me a concise professional summary of Malambo Mutila.", None],
                ["What data engineering experience does Malambo have?", None],
                ["Which projects are most relevant to AI engineering roles?", None],
                ["What public health and DHIS2 experience does he have?", None],
                ["Summarise his Andela AI Engineering Bootcamp work.", None],
                ["What publications has he authored?", None],
            ],
        )

    return demo


if __name__ == "__main__":
    app = build_demo()
    app.launch(theme=gr.themes.Soft(        
        font=[
            gr.themes.GoogleFont("Inter"),
            "ui-sans-serif",
            "sans-serif",
        ]))