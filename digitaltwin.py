from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
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

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("digital_twin")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    knowledge_dir: Path = Path(os.getenv("KNOWLEDGE_DIR", "me"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "120000"))
    app_title: str = os.getenv("APP_TITLE", "Malambo Mutila — Digital Twin")
    app_description: str = os.getenv(
        "APP_DESCRIPTION",
        "Ask questions about Malambo Mutila's background, projects, skills, publications, and bootcamp work.",
    )
    pushover_token: str | None = os.getenv("PUSHOVER_TOKEN")
    pushover_user: str | None = os.getenv("PUSHOVER_USER")
    lead_capture_enabled: bool = os.getenv("LEAD_CAPTURE_ENABLED", "true").lower() == "true"
    unknown_question_enabled: bool = os.getenv("UNKNOWN_QUESTION_ENABLED", "true").lower() == "true"


SETTINGS = Settings(openai_api_key=os.environ["OPENAI_API_KEY"])


# -----------------------------------------------------------------------------
# Notifications / tools
# -----------------------------------------------------------------------------


def push(text: str) -> None:
    """Send a Pushover notification if configured; otherwise no-op."""
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


# Simple file-based audit trail, useful even without Pushover.
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LEADS_FILE = LOG_DIR / "captured_leads.jsonl"
UNKNOWNS_FILE = LOG_DIR / "unknown_questions.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")



def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided") -> dict[str, str]:
    payload = {"email": email, "name": name, "notes": notes}
    _append_jsonl(LEADS_FILE, payload)
    push(f"Lead captured | name={name} | email={email} | notes={notes}")
    return {"recorded": "ok"}



def record_unknown_question(question: str) -> dict[str, str]:
    payload = {"question": question}
    _append_jsonl(UNKNOWNS_FILE, payload)
    push(f"Unknown question captured | {question}")
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
# Knowledge loading
# -----------------------------------------------------------------------------


class KnowledgeBase:
    """Loads and concatenates markdown knowledge files from the configured directory."""

    PREFERRED_ORDER = [
        "profile.md",
        "summary.md",
        "education.md",
        "experience.md",
        "projects.md",
        "skills.md",
        "publications.md",
        "retrievalkeywords.md",
        "andelabootcamp.md",
        "funfacts.md",
        "metadata.md",
    ]

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self.documents = self._load_documents()
        self.combined_context = self._build_combined_context()

    def _load_documents(self) -> list[tuple[str, str]]:
        if not self.knowledge_dir.exists() or not self.knowledge_dir.is_dir():
            raise FileNotFoundError(
                f"Knowledge directory '{self.knowledge_dir}' does not exist. "
                "Expected markdown files such as profile.md and experience.md."
            )

        discovered = {p.name: p for p in self.knowledge_dir.glob("*.md")}
        ordered_names = [name for name in self.PREFERRED_ORDER if name in discovered]
        remaining = sorted(name for name in discovered if name not in ordered_names)
        final_order = ordered_names + remaining

        documents: list[tuple[str, str]] = []
        for name in final_order:
            path = discovered[name]
            content = path.read_text(encoding="utf-8").strip()
            if content:
                documents.append((name, content))
                logger.info("Loaded knowledge file: %s", path)

        if not documents:
            raise ValueError(f"No markdown content found in '{self.knowledge_dir}'.")
        return documents

    def _build_combined_context(self) -> str:
        sections: list[str] = []
        for filename, content in self.documents:
            sections.append(f"\n\n# SOURCE: {filename}\n\n{content}")
        context = "".join(sections).strip()
        return context[: SETTINGS.max_context_chars]

    def list_sources(self) -> list[str]:
        return [name for name, _ in self.documents]


# -----------------------------------------------------------------------------
# Digital twin application
# -----------------------------------------------------------------------------


class DigitalTwin:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=SETTINGS.openai_api_key)
        self.name = "Malambo Mutila"
        self.role = "AI/ML Engineer"
        self.knowledge_base = KnowledgeBase(SETTINGS.knowledge_dir)

    def system_prompt(self) -> str:
        source_list = ", ".join(self.knowledge_base.list_sources())
        return f"""
You are acting as {self.name}, an experienced {self.role}.

Your job is to answer questions on {self.name}'s digital twin website accurately, professionally, warmly, and concisely.
You represent {self.name}'s real background, experience, projects, education, publications, skills, and bootcamp work.

Rules:
1. Stay grounded in the knowledge base provided below.
2. Do not invent experience, credentials, publications, or project outcomes.
3. If a detail is uncertain or not present in the knowledge base, say so briefly.
4. If the user asks something the knowledge base cannot answer, use the `record_unknown_question` tool.
5. If the user expresses hiring interest, collaboration interest, freelance interest, or asks to get in touch, politely ask for their email and use the `record_user_details` tool when they provide it.
6. Keep answers useful and natural, not robotic.
7. For recruiters or employers, emphasize relevant experience, business impact, technical breadth, and communication ability.
8. Fun facts are for light conversation only and should not be used in formal professional summaries unless the user explicitly asks.
9. When discussing bootcamp work, clearly separate it from professional work experience.
10. Use markdown formatting where it improves readability.

Available knowledge sources: {source_list}

## Knowledge Base
{self.knowledge_base.combined_context}
        """.strip()

    def handle_tool_call(self, tool_calls: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            logger.info("Tool called: %s | args=%s", tool_name, arguments)
            tool = TOOL_REGISTRY.get(tool_name)
            result = tool(**arguments) if tool else {"error": f"Unknown tool: {tool_name}"}
            results.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )
        return results

    def _normalize_history(self, history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not history:
            return []
        normalized: list[dict[str, Any]] = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role in {"user", "assistant", "system", "tool"}:
                normalized.append({"role": role, "content": content})
        return normalized

    def chat(self, message: str, history: list[dict[str, Any]] | None) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt()},
            *self._normalize_history(history),
            {"role": "user", "content": message},
        ]

        while True:
            response = self.client.chat.completions.create(
                model=SETTINGS.openai_model,
                messages=messages,
                tools=TOOLS if TOOLS else None,
                temperature=0.3,
            )
            assistant_message = response.choices[0].message

            if assistant_message.tool_calls:
                messages.append(assistant_message)
                messages.extend(self.handle_tool_call(assistant_message.tool_calls))
                continue

            return assistant_message.content or "I’m sorry, I don’t have a response right now."


# -----------------------------------------------------------------------------
# Gradio UI
# -----------------------------------------------------------------------------


def build_demo() -> gr.Blocks:
    twin = DigitalTwin()

    with gr.Blocks(title=SETTINGS.app_title, theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"# {SETTINGS.app_title}")
        gr.Markdown(SETTINGS.app_description)
        gr.Markdown(
            "Ask about experience, projects, education, publications, skills, digital health, "
            "bootcamp work, or how Malambo can contribute to a team or project."
        )

        gr.ChatInterface(
            fn=twin.chat,
            type="messages",
            chatbot=gr.Chatbot(height=650, type="messages"),
            textbox=gr.Textbox(
                placeholder="Ask about Malambo's background, projects, skills, or publications...",
                container=False,
                scale=7,
            ),
            examples=[
                "Give me a concise professional summary of Malambo Mutila.",
                "What data engineering experience does Malambo have?",
                "Which projects are most relevant to AI engineering roles?",
                "What public health and DHIS2 experience does he have?",
                "Summarise his Andela AI Engineering Bootcamp work.",
                "What publications has he authored?",
            ],
        )

    return demo


if __name__ == "__main__":
    app = build_demo()
    app.launch()
