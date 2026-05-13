# Vendor Compliance Agent — Build Plan

## Context

Take-home assessment requiring a fully-local AI agent for vendor/supplier management. The agent must autonomously decide between three paths per query:
- **RAG only** — contract terms, SLA thresholds, policy rules
- **Tool only** — live performance data fetch
- **RAG + Tool + Synthesis** — multi-step reasoning, read contract → fetch data → take action

Stack chosen to satisfy "fully local" constraint with no API costs: Ollama (LLM + embeddings), ChromaDB (vector store), LangGraph ReAct (agent loop), FastAPI (API layer), uv (dependency management).

---

## Final Project Structure

```
vendor-compliance-agent/
├── docs/
│   ├── acme_corp_contract.txt        ← Acme contract: SLA, penalty clause, renewal dates
│   ├── techvendor_contract.txt       ← TechVendor contract: compliance cert requirements
│   ├── sla_policy.txt                ← Company SLA policy: 99.5% uptime, 4-hr response
│   ├── escalation_policy.txt         ← Escalation ladder: warning → dispute → review
│   └── compliance_requirements.txt   ← Annual cert deadlines: ISO, privacy, security audit
├── src/
│   ├── __init__.py                   ← Makes src a Python package (empty)
│   ├── rag.py                        ← ChromaDB setup + query_vendor_knowledge_base tool
│   ├── tools.py                      ← 4 mock action tools
│   ├── agent.py                      ← LangGraph ReAct agent + CoT system prompt
│   └── main.py                       ← FastAPI app
├── pyproject.toml                    ← uv-managed dependencies
└── README.md                         ← Stack justification + setup + demo queries
```

---

## Step-by-Step Build Plan

### Step 1 — `pyproject.toml`

**Purpose:** uv-managed project with all dependencies declared.

**Dependencies:**
- `langchain>=0.3` — base LangChain
- `langchain-ollama>=0.2` — `ChatOllama` + `OllamaEmbeddings`
- `langchain-chroma>=0.1` — `Chroma` vector store wrapper
- `langchain-text-splitters>=0.3` — `RecursiveCharacterTextSplitter`
- `langgraph>=0.2` — `create_react_agent` ReAct loop
- `fastapi>=0.115` + `uvicorn[standard]>=0.30` — API layer
- `chromadb>=0.5` — in-process vector DB
- `pydantic>=2.0` — request/response models

```toml
[project]
name = "vendor-compliance-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [...]

[tool.uv]
package = false
```

---

### Step 2 — `docs/` (RAG Corpus — 5 mock documents)

Realistic but fake. Evaluator cares about agent reasoning, not real data.

**`acme_corp_contract.txt`**
- Vendor: Acme Corp | Contract: 2025-01-01 to 2026-12-31
- Monthly deliveries due by the 5th
- SLA: 99.5% uptime, 4-hour critical response
- Penalty clause: 2 missed deliveries in a rolling 30-day period triggers a formal dispute (Clause 4.2)
- Payment: Net 30

**`techvendor_contract.txt`**
- Vendor: TechVendor Inc. | Contract: 2025-06-01 to 2026-05-31
- Annual certifications required: ISO 27001, data privacy agreement, security audit
- Must submit certifications by April 1 each year
- Non-submission triggers a compliance flag and 30-day cure period

**`sla_policy.txt`**
- Company-wide SLA standard: 99.5% monthly uptime
- Critical issue response: 4 hours
- High issue response: 24 hours
- SLA breach definition: falling below 99.5% uptime in any calendar month
- Remedies: service credits, formal dispute at repeated breach

**`escalation_policy.txt`**
- 1 missed delivery → automated warning email within 24 hours
- 2 consecutive misses in 30 days → raise formal dispute
- 3+ misses in 30 days → initiate contract review
- Disputes unresolved after 14 days → escalate to legal

**`compliance_requirements.txt`**
- All vendors must submit annually: ISO 27001 cert, data privacy agreement, security audit report
- Deadline: April 1 each calendar year
- Grace period: 30 days after deadline
- Past grace period → compliance flag raised, 30-day cure period
- Cure period missed → contract suspension

---

### Step 3 — `src/rag.py`

**Responsibilities:**
1. Load all `.txt` files from `docs/` as `Document` objects with source metadata
2. Split with `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`
3. Embed with `OllamaEmbeddings(model="nomic-embed-text")`
4. Persist to `ChromaDB` at `./chroma_db/` (skip re-indexing if already populated)
5. Expose `query_vendor_knowledge_base` as a `@tool` returning top-3 relevant chunks

**Key design choices:**
- Check `vectorstore._collection.count() == 0` before indexing (idempotent startup)
- Singleton `_retriever` — initialized once per process
- Tool description is verbose and explicit to help local model route correctly
- Return chunks with `[Source: filename]` prefix so agent can cite document

---

### Step 4 — `src/tools.py`

Four `@tool`-decorated mock functions. Each returns realistic string output (not JSON objects) so the local model can parse it easily.

**`get_vendor_performance(vendor_id: str)`**
- Mock data for `acme_corp` and `techvendor`
- Returns: delivery stats (scheduled/on-time/missed/late), uptime %, SLA breaches, open incidents, compliance status
- Handles unknown vendor gracefully with a clear error message

**`raise_dispute(vendor_id: str, clause_ref: str, reason: str)`**
- Returns: dispute ID (generated), timestamp, status OPEN, next steps (14-day response window)

**`send_renewal_reminder(vendor_id: str, days_until_expiry: int)`**
- Returns: confirmation, recipients (vendor + internal procurement), timestamp

**`flag_compliance_gap(vendor_id: str, missing_cert: str)`**
- Returns: flag ID, timestamp, compliance team notified, vendor notified, 30-day deadline

---

### Step 5 — `src/agent.py`

**LLM:** `ChatOllama(model="llama3.1:8b", temperature=0)`
Temperature=0 for deterministic tool routing.

**System Prompt (CoT):**
```
You are a Vendor Compliance Agent. Think step by step before acting.

Step 1: Identify what the query needs:
  - Contract terms / SLA / policy / dates → query_vendor_knowledge_base FIRST
  - Current vendor stats → get_vendor_performance
  - Filing a dispute → raise_dispute
  - Sending a reminder → send_renewal_reminder
  - Flagging missing cert → flag_compliance_gap

Step 2: For complex queries, chain tools:
  → RAG (get policy) → get_vendor_performance (confirm facts) → action tool

NEVER guess contract terms or performance numbers. Always use tools.
After all tool calls, synthesize into a clear actionable response.
```

**LangGraph version compatibility:**
`create_react_agent` API changed across versions (0.1: `messages_modifier`, 0.2: `state_modifier`, 0.3+: `prompt`). Use `inspect.signature` to detect the correct parameter name at runtime.

**`run_agent(query: str) -> dict`**
- Invokes the agent graph
- Extracts intermediate steps from message history (tool calls + results)
- Returns `{"answer": str, "steps": list[str]}`

---

### Step 6 — `src/main.py`

FastAPI app with lifespan context manager (initializes RAG + agent on startup).

**Endpoints:**
- `POST /query` — takes `{"query": "..."}`, returns `{"answer": "...", "steps": [...]}`
- `GET /health` — returns `{"status": "ok"}`

**Pydantic models:** `QueryRequest(query: str)`, `QueryResponse(answer: str, steps: list[str])`

**Error handling:**
- Empty query → HTTP 400
- Agent/Ollama failure → HTTP 500 with descriptive message

---

### Step 7 — `README.md`

Sections:
1. **What it does** — one paragraph
2. **Tech Stack & Justification** — table: component | tool | why
3. **Prerequisites** — Ollama install + model pulls
4. **Setup & Run** — `uv sync` → `uv run uvicorn src.main:app --reload`
5. **Demo Queries** — all 5 queries with expected paths
6. **Project Structure** — file tree with descriptions

---

## 5 Demo Queries (Acceptance Tests)

| # | Query | Expected Path |
|---|-------|---------------|
| 1 | "What does our SLA say about uptime requirements?" | RAG only |
| 2 | "Get me Acme Corp's current performance stats" | Tool only (`get_vendor_performance`) |
| 3 | "Acme missed 3 deliveries this month, what should we do?" | RAG → Tool → `raise_dispute` |
| 4 | "When does Acme Corp's contract expire?" | RAG only |
| 5 | "TechVendor hasn't submitted their annual ISO certification, handle it" | RAG → Tool → `flag_compliance_gap` |

---

## Verification Steps

```bash
# 1. Prerequisites
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# 2. Install dependencies
uv sync

# 3. Start the API server
uv run uvicorn src.main:app --reload

# 4. Test via Swagger UI
open http://localhost:8000/docs

# 5. Test via curl (example — query 3)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Acme missed 3 deliveries this month, what should we do?"}'
```

Expected response shape:
```json
{
  "answer": "Acme Corp has violated Clause 4.2... I've raised dispute DISP-ACME-...",
  "steps": [
    "Tool call: query_vendor_knowledge_base(...)",
    "Tool result [query_vendor_knowledge_base]: ...",
    "Tool call: get_vendor_performance(...)",
    "Tool call: raise_dispute(...)"
  ]
}
```

---

## Files to Create (in order)

1. `pyproject.toml`
2. `src/__init__.py`
3. `docs/acme_corp_contract.txt`
4. `docs/techvendor_contract.txt`
5. `docs/sla_policy.txt`
6. `docs/escalation_policy.txt`
7. `docs/compliance_requirements.txt`
8. `src/rag.py`
9. `src/tools.py`
10. `src/agent.py`
11. `src/main.py`
12. `README.md`
