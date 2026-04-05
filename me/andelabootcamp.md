# Malambo Mutila Knowledge Base

## Andela AI Engineering Bootcamp

I participated in the Andela AI Engineering Bootcamp. My Digital Twin was developed as a project from the bootcamp.

### Bootcamp Overview

The AI Engineering Bootcamp was a 10-week elite training program designed for those seeking to excel in best practices for building and shipping enterprise-grade AI-powered software. The programme covered the path from core LLM-powered applications to RAG systems and agentic systems deployed to production.

The bootcamp was led by Ed Donner and Zion Pibowei, and supported by a team of training assistants, including Hope Ogbons, the TA for my squad, **Neural Forge**.

### Bootcamp Outcomes
The programme helped build advanced AI engineering capability in:

- LLM engineering
- Retrieval-augmented generation
- Agentic AI systems
- Production deployment
- Enterprise AI software practices

---

## 10-Week Programme Schedule

### Week 1
- **Phase:** Core
- **Content:** LLM Engineering W1-4

### Week 2
- **Phase:** Core
- **Content:** LLM Engineering W5-8
- **Other:** Behavioral Workshop 1

### Week 3
- **Phase:** Core
- **Content:** AI Leadership module
- **Deliverable:** Project 1
- **Other:** Survey 1

### Week 4
- **Phase:** Agentic
- **Content:** Agentic Track W1-3
- **Other:** Behavioral Workshop 2

### Week 5
- **Phase:** Agentic
- **Content:** Agentic Track W4-6

### Week 6
- **Phase:** Agentic
- **Content:** Project Focus
- **Deliverable:** Project 2
- **Other:** Survey 2

### Week 7
- **Phase:** Production
- **Content:** Production Track W1-2
- **Other:** Behavioral Workshop 3

### Week 8
- **Phase:** Production
- **Content:** Production Track W3-4

### Week 9
- **Phase:** Capstone
- **Content:** Group project work
- **Deliverable:** Project 3
- **Other:** Survey 3

### Week 10
- **Phase:** Capstone
- **Content:** Assessment week
- **Other:** Showcase presentation

### Professional Skills Development

Each phase built on the last. By Week 10, the programme had progressed from prompts to production-ready AI systems.

Behavioral workshops developed professional skills important in client engagements, including:

- Proactive communication
- Ownership
- Adaptive problem-solving
- Professional presence

### SolidRoad Soft Skills Training

To strengthen soft skills, SolidRoad, a behavioral competency AI training platform, was used throughout the bootcamp. It provided AI-driven simulations based on real workplace and interview scenarios.

---

## Bootcamp Modules and Projects

### Week 1-2: LLM Engineering
- **Module:** LLM Engineering
- **Supporting Course:** AI Engineer Core Track: LLM Engineering, RAG, QLoRA, Agents by Ed Donner
- **Certificate:** https://www.udemy.com/certificate/UC-c60f166a-b497-49b1-9c99-8357c24b32e4/

#### Course Project: Counsel of Agents

At the end of the course and Week 2 of the bootcamp, I developed **Counsel of Agents**, a multi-agent AI system that analyses a user's legal case from multiple perspectives using five specialist agents in parallel debate.

**Agents**
- **Plaintiff's Counsel** (Llama 3.3 70B via Hugging Face): builds the strongest argument in favour of the user's position
- **Defense Counsel** (Llama 3.3 70B via Hugging Face): mounts the strongest counter-argument to stress-test weaknesses
- **Expert Witness** (Claude Sonnet via OpenRouter): provides objective analysis of statutes, precedents, and burden of proof
- **Judge** (OpenAI o3 via OpenRouter): scores both sides across five legal criteria and identifies vulnerabilities
- **Legal Strategist** (GPT-4o via OpenRouter): synthesises all outputs into an actionable case preparation memo

**System Features**
- Streams results step by step through a styled Gradio UI
- Supports 11 legal areas including Contract, Employment, IP, Criminal, and Family Law
- Built on a unified `LLMAdapter` that handles provider differences, including models without temperature or JSON mode support

**Project Link**
- https://github.com/malambomutila/llm_engineering/blob/week8_exercise_bootcamp_feb2026_MalamboMutila/week8/community_contributions/MalamboMutila/week_8_exercise.ipynb

### Week 3: AI Leadership Module
- **Module:** AI Leadership
- **Course:** AI Leader: Generative AI & Agentic AI for Leaders & Founders by Ed Donner

**Overview**
The course focused on strategy, decision-making, and leading AI initiatives for managers, leaders, executives, and founders who want commercial results with AI.

**Key Learnings**
1. Becoming an AI strategist and decision-maker
2. Understanding AI scaling laws and techniques
3. Exploring Agentic AI, its risks, and opportunities
4. Analysing AI architecture from a commercial perspective

### Week 3: Project 1 - RAG Challenge

The challenge was to beat Ed Donner's model performance on a retrieval-augmented generation system.

#### Objective
Improve retrieval and answer quality over the baseline system.

#### Baseline
The baseline system:

- Embedded document chunks with `all-MiniLM-L6-v2`
- Stored them in a Chroma vector store
- Retrieved the three nearest chunks by cosine similarity
- Used `gpt-4.1-nano` for answer generation

**Baseline metrics**
- **MRR:** 0.72
- **nDCG:** 0.74
- **Completeness:** 3.53 / 5

#### Interventions

##### Intervention 1: Cross-Encoder Re-ranking
Used `cross-encoder/ms-marco-MiniLM-L-6-v2` to rerank a widened candidate pool of 15 chunks.

**Result**
- MRR improved from 0.72 to 0.88
- Keyword coverage rose by 9 percentage points

##### Intervention 2: Hybrid BM25 + Dense Retrieval
Combined BM25 keyword search with dense retrieval, then reranked the merged candidate pool.

##### Intervention 3: Multi-Query Expansion
Used `gpt-4.1-nano` to generate three diverse sub-queries per question, merged retrieval pools, and reranked the result set.

##### Intervention 4: Small-to-Big Retrieval / Sentence-Window Expansion
Expanded each retrieved chunk with neighbouring context to improve answer completeness.

##### Intervention 5: Cross-Encoder Upgrade - L-12 Model
Tested `ms-marco-MiniLM-L-12-v2` against the 6-layer model. Retrieval improved marginally but answer quality declined.

##### Intervention 6: RAPTOR Hierarchical Summarisation
Added document summaries and category rosters to the retrieval corpus. Retrieval metrics improved, but completeness fell because summaries displaced richer context.

##### Intervention 7: Reciprocal Rank Fusion (RRF) Hybrid Search
Used RRF to combine BM25 and dense rankings more systematically. Final answer quality remained similar to the strongest retrieval-only baseline.

##### Intervention 8: DeepSeek-R1 Reasoning Model
Used `gpt-4.1-nano` for sub-query generation and `deepseek/deepseek-r1` for final answer generation.

**Best active configuration**
- **Model:** DeepSeek-R1
- **k:** 7
- **w:** 2
- **N:** 4

#### Evaluation Table

| Pipeline | MRR | nDCG | Coverage | Accuracy | Completeness | Relevance |
|---|---:|---:|---:|---:|---:|---:|
| Baseline (Ed Donner) | 0.723 | 0.739 | 80.8% | 4.07 | 3.53 | 4.80 |
| Cross encoder reranking | 0.882 | 0.882 | 90.0% | 4.36 | 3.59 | 4.85 |
| Hybrid BM25 and dense retrieval | 0.932 | 0.916 | 95.5% | 4.45 | 3.58 | 4.87 |
| Multi-query expansion, N=3, k=7 | 0.937 | 0.908 | 96.7% | 4.58 | 3.73 | 4.95 |
| Small to Big expansion, w=2, k=5 | 0.945 | 0.921 | 97.2% | 4.75 | 3.88 | 4.99 |
| Cross encoder L-12 upgrade | 0.946 | 0.924 | 97.2% | 4.73 | 3.80 | 4.99 |
| RAPTOR hierarchical summaries | **0.958** | **0.949** | **98.1%** | 4.71 | 3.53 | 4.96 |
| RRF hybrid search, k=5 | 0.944 | 0.919 | 97.2% | 4.67 | 3.87 | 4.94 |
| **DeepSeek-R1, k=7, w=2, N=4 (active)** | 0.946 | 0.903 | 97.5% | **4.85** | **4.05** | **4.97** |

#### Active Pipeline Summary
- Bi-encoder: `all-MiniLM-L6-v2`
- Hybrid retrieval: BM25 + dense search with RRF
- Candidate pool: 30 from each retriever
- Sub-query generation: `gpt-4.1-nano`
- Re-ranking: `ms-marco-MiniLM-L-6-v2`
- Context selection: top 7 documents
- Context expansion: window-2 Small-to-Big
- Final answer model: `deepseek/deepseek-r1`
- Temperature: 0.6

### Week 4-6: Agentic Track
- **Module:** Agentic Track
- **Course:** AI Engineer Agentic Track: The Complete Agent & MCP Course by Ed Donner

**Overview**
I built four real-world projects using:

- OpenAI Agents SDK
- CrewAI
- LangGraph
- AutoGen
- MCP

My Digital Twin was built in Week 4 of the bootcamp, which was Week 1 of the Agentic Track course.

#### Project 1: Mini Math Personal Tutor
- Built a personal math tutor that shows how to find the inverse of a 2x2 matrix using an agent loop with step-by-step todos.

#### Project 2: Research Report Agent
- Built a Gradio app that uses the OpenAI Agents SDK with OpenRouter to run a multi-step flow:
  - asks three clarifying questions
  - plans web searches using Serper or DuckDuckGo
  - writes a Markdown report
  - loops with an evaluator until the work is good enough

#### Project 3: Sidekick Agent Upgrade
Improved Ed Donner's sidekick agent by:

- Adding a three-question clarification flow in Gradio
- Feeding answers into `clarification_context` for planning and execution
- Exposing an optional login where the username doubles as the LangGraph `thread_id`
- Replacing in-memory checkpoints with `AsyncSqliteSaver` backed by a SQLite file in the working directory
- Using a local task library and sandbox files
- Building a multi-step graph with planner, worker, tools, and evaluator nodes
- Restricting the toolset for safety:
  - files
  - SQLite task DB with read-only SQL
  - Wikipedia
  - safe calculator
  - optional Pushover
- Removing Python REPL and browser/navigation tools for security

#### Project 4: AI Equity Trading Agent
Extended Ed Donner's trading simulator by:

- Giving each Trader direct `mcp-server-fetch` capability so traders can independently retrieve investor-relations pages, earnings press releases, or financial data endpoints
- Adding a Risk Manager as a second sub-agent tool on each Trader

**Risk constraints enforced**
- No single position exceeds 25% of total portfolio value
- At least 10% of portfolio value stays in cash at all times
- No single trade deploys more than 15% of total portfolio value

### Week 6: Project 2 - eStock Simulator
See the project entry above under **Projects > eStock Simulator**.

### Week 7: Production Track
- **Module:** Production
- **Course:** AI Engineer Production Track: Deploy LLMs & Agents at Scale by Ed Donner
- **Status:** Currently underway

---