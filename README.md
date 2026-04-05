# Malambo Mutila — Digital Twin

A conversational AI assistant that represents my professional background, experience, projects, skills, publications, and Andela AI Engineering Bootcamp work. Built as a project during Week 1 of the Andela Agentic AI Track. You can chat with my digital twin here | [Malambo Mutila - Digital Twin](https://huggingface.co/spaces/MalamboMutila/Digital-Twin)

---

## What It Does

Visitors can ask natural language questions about my background and get accurate, grounded answers. The assistant will not invent credentials or experience — if something is not in the knowledge base, it says so.

It also captures contact details from recruiters or collaborators who want to get in touch, and logs questions it cannot answer so the knowledge base can be improved over time.

---

## Features

- **Conversational Q&A** — answers questions about experience, projects, education, skills, publications, and bootcamp work
- **Scoped retrieval** — detects whether a question is about professional work or bootcamp work and prioritises the relevant documents
- **TF-IDF retrieval layer** — scores and ranks knowledge chunks per query instead of stuffing all context into every prompt
- **Lead capture** — asks for contact details when a visitor expresses hiring or collaboration interest, with email validation and per-session rate limiting
- **Unknown question logging** — records questions the knowledge base cannot answer for future improvement
- **Knowledge integrity check** — validates all knowledge files at startup and warns if expected content is missing
- **Structured JSON logging** — emits token usage, latency, and tool call events as JSON for easy inspection
- **Pushover notifications** — optional real-time alerts for lead captures and unknown questions

---

## Tech Stack

- [Gradio](https://gradio.app/) — chat UI
- [OpenAI API](https://platform.openai.com/) — language model (`gpt-4.1-mini` by default)
- Python standard library — TF-IDF retrieval, no heavy ML dependencies

---

## Project Structure
```
.
├── digitaltwin.py        # Main application
├── me/                   # Knowledge base (markdown files)
│   ├── profile.md
│   ├── summary.md
│   ├── education.md
│   ├── experience.md
│   ├── projects.md
│   ├── skills.md
│   ├── publications.md
│   ├── andelabootcamp.md
│   ├── retrievalkeywords.md
│   ├── funfacts.md
│   └── metadata.md
├── logs/                 # Auto-created at runtime
│   ├── captured_leads.jsonl
│   └── unknown_questions.jsonl
├── requirements.txt
└── .env                  # Not committed — see Environment Variables below
```

---

## Environment Variables

Create a `.env` file in the project root:
```env
# Required
OPENAI_API_KEY=sk-...

# Optional — model and retrieval
OPENAI_MODEL=gpt-4.1-mini
KNOWLEDGE_DIR=me
MAX_CONTEXT_CHARS=120000
RAG_TOP_K=5

# Optional — UI
APP_TITLE=Malambo Mutila — Digital Twin
APP_DESCRIPTION=Ask questions about Malambo Mutila's background, projects, skills, publications, and bootcamp work.

# Optional — Pushover notifications
PUSHOVER_TOKEN=your_pushover_app_token
PUSHOVER_USER=your_pushover_user_key

# Optional — feature flags
LEAD_CAPTURE_ENABLED=true
UNKNOWN_QUESTION_ENABLED=true
LEAD_RATE_LIMIT=3

# Optional — logging
LOG_LEVEL=INFO
```

---

## Running Locally
```bash
# Clone the repo
git clone https://github.com/your-username/digital-twin.git
cd digital-twin

# Create and activate a virtual environment
python -m venv .dtwinenv
source .dtwinenv/bin/activate  # Windows: .dtwinenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add your .env file, then run
python digitaltwin.py
```

The app will be available at `http://localhost:7860`.

---

## Deploying to Hugging Face Spaces

### First-time setup

You will need a Hugging Face account and an access token with write permissions.
Generate one at: https://huggingface.co/settings/tokens

Clone your Space repository (use your access token as the password when prompted):
```bash
git clone https://huggingface.co/spaces/MalamboMutila/Digital-Twin
cd Digital-Twin
```

### Add your project files

Copy in the project files:
```
Digital-Twin/
├── digitaltwin.py        # Rename to app.py — HF Spaces expects this entry point
├── me/                   # Knowledge base — must be included
├── requirements.txt
└── README.md
```

> **Important:** Hugging Face Spaces expects the entry point to be named `app.py`. Rename `digitaltwin.py` to `app.py` before pushing.

### Add secrets and variables

In your Space settings (Settings → Variables and secrets), add:

**Secrets (Private)**
- `OPENAI_API_KEY` — your OpenAI API key

**Variables (Public)**
- `OPENAI_MODEL`, `KNOWLEDGE_DIR`, `MAX_CONTEXT_CHARS`, `APP_TITLE`, `APP_DESCRIPTION`, `LEAD_CAPTURE_ENABLED`, `UNKNOWN_QUESTION_ENABLED`

These are injected automatically as environment variables at runtime — no `.env` file needed on HF Spaces.

### Push and deploy
```bash
git add app.py me/ requirements.txt README.md
git commit -m "Initial deployment"
git push
```

Your Space will build automatically. The build installs everything in `requirements.txt` — `gradio` is pre-installed by HF Spaces but pinning it in `requirements.txt` ensures the correct version is used.

### Dependencies

Python dependencies are read from `requirements.txt` at build time. If you need any system-level packages, add them to a `packages.txt` file at the root of the repository.

### Logs

The `logs/` directory (lead captures and unknown questions) is ephemeral on HF Spaces — it resets on every restart. If you need leads to persist, route `PUSHOVER_TOKEN` and `PUSHOVER_USER` as Secrets so captures are sent to you in real time via Pushover, independent of the filesystem.

---

## Knowledge Base

The `me/` directory contains the knowledge base as plain markdown files. Each file covers a specific domain:

| File | Content |
|---|---|
| `profile.md` | Name, location, contact, professional summary |
| `summary.md` | One-paragraph bio |
| `education.md` | Degrees and professional certificates |
| `experience.md` | Work history with responsibilities and achievements |
| `projects.md` | Technical and hobby projects |
| `skills.md` | Technical skills list |
| `publications.md` | Authored publications with links |
| `andelabootcamp.md` | Andela AI Engineering Bootcamp modules and projects |
| `retrievalkeywords.md` | Domain and technical keywords for retrieval scoring |
| `funfacts.md` | Personality notes for light conversation |
| `metadata.md` | Knowledge base metadata and domain tags |

To update the knowledge base, edit the relevant markdown file and restart the app. The integrity check at startup will warn if expected content is missing.

---

## Bootcamp Context

This project was built during **Week 4 of the Andela AI Engineering Bootcamp** (Week 1 of the Agentic Track). The bootcamp is a 10-week elite programme covering LLM engineering, RAG systems, agentic AI, and production deployment, led by Ed Donner and Zion Pibowei.

---

## License

Apache 
