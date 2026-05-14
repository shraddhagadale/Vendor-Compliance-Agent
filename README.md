# Vendor Compliance Agent

A fully-local AI agent for vendor and supplier management. Given a natural language query, the agent autonomously decides whether to search internal documents (RAG), fetch live vendor data (tool), or chain both to take a compliance action — with no hardcoded routing logic.

---

## Stack

**LangGraph (ReAct agent)**
The ReAct pattern was chosen specifically for its reasoning-then-acting loop. The agent observes the query, decides which tools to call, processes the results, and decides whether to act — all autonomously. LangGraph's `create_react_agent` compiles this loop as a stateful graph, making tool chaining and multi-step reasoning first-class citizens rather than something bolted on.

**qwen2.5:7b via Ollama**
qwen2.5:7b is purpose-built for function calling. Unlike general-purpose local models, it reliably handles the full agent loop: it can retrieve from the knowledge base, inspect live vendor data, and follow through with a tool-based action — all in a single agent run. Ollama provides a clean local runtime with no cloud dependency, satisfying the fully-local constraint.

**ChromaDB**
Lightweight, fully local vector store that requires no separate server process. It auto-persists the index to disk on first run and reloads it on subsequent runs — zero configuration. `langchain-chroma` integrates it directly into the LangChain tool ecosystem.

**nomic-embed-text via Ollama**
Strong open-source embedding model that produces high-quality semantic vectors for short legal and policy text. Runs locally via Ollama alongside the main LLM.

**FastAPI**
Clean async HTTP layer with automatic Swagger UI at `/docs`. Serves as the interface for submitting queries and reviewing agent responses.

---

## Architecture

```
docs/ (5 vendor documents)
    └── ChromaDB (embedded at startup via nomic-embed-text)
            └── query_vendor_knowledge_base [RAG tool]
                        │
                        ▼
              LangGraph ReAct Agent (qwen2.5:7b)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
query_vendor_knowledge_base  get_vendor_performance  flag_compliance_gap
  [RAG tool]                   [data tool]             [action tool]
                        │
                        ▼
                  FastAPI /query
```

The agent autonomously selects tools based on the query. Informational queries use RAG or the data tool. Compliance or renewal queries chain retrieval with an action tool.

---

## Project Structure

```
vendor-compliance-agent/
├── docs/                        # 5 vendor documents (contracts, SLA, escalation, compliance)
├── src/
│   ├── rag.py                   # ChromaDB setup and RAG tool
│   ├── tools.py                 # Mock action tools with Pydantic schemas
│   ├── agent.py                 # LangGraph ReAct agent and system prompt
│   └── main.py                  # FastAPI app
├── pyproject.toml
└── uv.lock
```

---

## Setup & Run

**Prerequisites:** [Ollama](https://ollama.com) and [uv](https://github.com/astral-sh/uv) installed.

```bash
# Pull models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Install dependencies
uv sync

# Start the server
uv run uvicorn src.main:app --reload
```

Open `http://localhost:8000/docs` to use the Swagger UI.

On first run, the agent automatically embeds the 5 vendor documents into ChromaDB. Subsequent runs reuse the persisted index.

---

## Demo Queries

| Query | Agent behaviour |
|---|---|
| `What does our SLA say about uptime requirements?` | RAG only — retrieves SLA policy and breach tiers |
| `What does our contract say about missed deliveries, and how many has Acme Corp missed?` | Multi-step — calls RAG and `get_vendor_performance` in parallel, then synthesizes both |
| `TechVendor's Annual Security Audit is overdue, flag them` | Action — agent directly flags the compliance gap |

The second query demonstrates multi-step reasoning: the agent autonomously fires both a document lookup and a live data fetch in parallel, then combines the results to answer. The third query shows direct action routing — the user provided the context, the agent executed immediately.

---

## API

**`POST /query`**
```json
{ "query": "TechVendor hasn't submitted their annual ISO certification, handle it" }
```
```json
{ "answer": "TechVendor has been flagged for the missing Annual Security Audit..." }
```

**`GET /health`**
```json
{ "status": "ok" }
```

---

## Demo Log

See [`demo.log`](demo.log) for a full agent run showing the query that requires both document lookup and tool execution.
