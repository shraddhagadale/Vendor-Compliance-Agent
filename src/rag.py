"""
RAG pipeline: loads vendor documents, embeds them into ChromaDB,
and exposes a retrieval tool the agent can call.
"""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Paths ─────────────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent.parent / "docs"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "vendor_docs"

# ── Singleton — built once per process ────────────────────────────────────────

_vectorstore: Chroma | None = None


# ── Document loading ──────────────────────────────────────────────────────────

def _load_documents() -> list[Document]:
    """Read every .txt file in docs/ and wrap it as a LangChain Document.

    The source filename is stored in metadata so the agent can cite
    which document a retrieved chunk came from.
    """
    docs: list[Document] = []
    for path in sorted(DOCS_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


# ── Chunking ──────────────────────────────────────────────────────────────────

def _split(docs: list[Document]) -> list[Document]:
    """Split documents into overlapping chunks.

    Strategy: RecursiveCharacterTextSplitter
    ─────────────────────────────────────────
    Tries to split on natural boundaries in priority order:
      1. Paragraph breaks  (\n\n)
      2. Line breaks       (\n)
      3. Sentence endings  (". ")
      4. Characters        (last resort)

    chunk_size=600   — large enough for a full legal clause to fit in one chunk
    chunk_overlap=75 — ensures a clause that straddles a boundary isn't lost;
                       the tail of chunk N becomes the head of chunk N+1
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
    )
    return splitter.split_documents(docs)


# ── Vector store init ─────────────────────────────────────────────────────────

def _get_vectorstore() -> Chroma:
    """Return the singleton Chroma vectorstore, building it on first call.

    On the first run:
      1. Loads all docs from docs/
      2. Splits them into chunks
      3. Embeds each chunk with nomic-embed-text (runs locally via Ollama)
      4. Persists vectors to ./chroma_db/  (auto-persisted, no .persist() needed)

    On subsequent runs:
      - ChromaDB finds the existing collection on disk and skips re-indexing.
    """
    global _vectorstore

    if _vectorstore is not None:
        return _vectorstore

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )

    # _collection gives access to the underlying chromadb Collection object.
    # count() returns the number of embedded chunks already stored.
    # If 0, this is a fresh run — load, split, and index all documents.
    if vectorstore._collection.count() == 0:
        print("[RAG] No existing index found — loading and indexing documents...")
        raw_docs = _load_documents()
        chunks = _split(raw_docs)
        vectorstore.add_documents(chunks)
        print(f"[RAG] Indexed {len(chunks)} chunks from {len(raw_docs)} documents.")
    else:
        count = vectorstore._collection.count()
        print(f"[RAG] Loaded existing index ({count} chunks). Skipping re-indexing.")

    _vectorstore = vectorstore
    return _vectorstore


# ── Public retriever accessor ─────────────────────────────────────────────────

def get_retriever():
    """Return a LangChain retriever that fetches the top-3 most relevant chunks."""
    return _get_vectorstore().as_retriever(search_kwargs={"k": 3})


# ── LangChain Tool ────────────────────────────────────────────────────────────

@tool
def query_vendor_knowledge_base(query: str) -> str:
    """Search internal vendor contracts, SLA policies, escalation procedures, and compliance requirements.

    Use this tool for ANY question about:
    - Contract terms, clauses, or conditions (penalty clauses, delivery obligations, payment terms)
    - SLA thresholds (uptime requirements, response time tiers, breach definitions)
    - Escalation steps and procedures (what action to take after missed deliveries)
    - Compliance certification requirements and annual deadlines (ISO 27001, DPA, security audit)
    - Contract renewal dates, expiry dates, or termination conditions

    Input: a natural language question or keyword phrase describing what you need.
    Output: the most relevant excerpts from internal documents, each prefixed with its source filename.

    Always call this tool BEFORE taking any action — never guess contract terms or policy thresholds.
    """
    try:
        retriever = get_retriever()
        results = retriever.invoke(query)

        if not results:
            return (
                "No relevant information found in the vendor knowledge base for this query. "
                "Consider rephrasing or checking if the vendor or topic exists in the documents."
            )

        parts: list[str] = []
        for doc in results:
            source = doc.metadata.get("source", "unknown document")
            parts.append(f"[Source: {source}]\n{doc.page_content.strip()}")

        return "\n\n---\n\n".join(parts)

    except Exception as e:
        return f"[RAG ERROR] Failed to retrieve from knowledge base: {e}"
