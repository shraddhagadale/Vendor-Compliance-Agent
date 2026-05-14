"""
FastAPI app — exposes the vendor compliance agent via HTTP.
Interactive docs available at http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import get_agent, run_agent
from .rag import get_retriever


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up RAG index and compile the agent graph on startup.
    # Prevents a slow first request — both are singletons so this runs once.
    get_retriever()
    get_agent()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Vendor Compliance Agent",
    description=(
        "Fully-local AI agent for vendor contract management, SLA monitoring, "
        "and compliance tracking. Powered by LangGraph ReAct + ChromaDB + Ollama."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str

    model_config = {"json_schema_extra": {"example": {"query": "What does our SLA say about uptime requirements?"}}}


class QueryResponse(BaseModel):
    answer: str
    steps: list[str] = []


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Check that the server is running."""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Send a natural language query to the vendor compliance agent."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        result = run_agent(request.query)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
