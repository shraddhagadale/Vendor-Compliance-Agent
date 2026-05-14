"""
LangGraph ReAct agent — wires the LLM, tools, and system prompt together.
The LLM autonomously decides which tools to call and in what order.
"""

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .rag import query_vendor_knowledge_base
from .tools import (
    flag_compliance_gap,
    get_vendor_performance,
    send_renewal_reminder,
)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Vendor Compliance Agent for InternalCo Ltd.
You help manage vendor contracts, SLA compliance, and certification requirements.

You have 4 tools. Always invoke them using the tool calling interface — never write tool calls as JSON or plain text.

- query_vendor_knowledge_base: use for contract terms, SLA thresholds, penalty clauses, escalation rules, compliance deadlines, renewal dates, or any internal policy question
- get_vendor_performance: use for live vendor stats — delivery counts, uptime percentage, SLA breaches, open incidents, compliance certificate status
- flag_compliance_gap: use to raise a compliance flag when a vendor is missing or has an overdue certification
- send_renewal_reminder: use to send a contract renewal reminder to a vendor approaching expiry

For complex queries, chain tools — gather facts first, then act.
Never guess contract terms, thresholds, or vendor data — always use tools.

Action tool rules:
- When the user describes a vendor violation (missing cert, SLA breach) or asks to send a reminder — verify the facts with tools, then immediately call the appropriate action tool (flag_compliance_gap, send_renewal_reminder). Do not outline steps or ask for confirmation — just act and report what was done.
- For purely informational questions (e.g. "what does our SLA say?", "when does the contract expire?", "get me the performance stats"), use only query_vendor_knowledge_base and get_vendor_performance — never call action tools.

After all tool calls, write one clear synthesized response explaining what you found and what action was taken."""

# ── LLM ───────────────────────────────────────────────────────────────────────

def _build_llm() -> ChatOllama:
    return ChatOllama(
        model="qwen2.5:7b",
        temperature=0,
        num_ctx=4096,
    )


# ── Agent ─────────────────────────────────────────────────────────────────────

_agent = None


def _build_agent():
    llm = _build_llm()
    tools = [
        query_vendor_knowledge_base,
        get_vendor_performance,
        flag_compliance_gap,
        send_renewal_reminder,
    ]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# ── Run ───────────────────────────────────────────────────────────────────────

def run_agent(query: str) -> dict:
    agent = get_agent()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    messages = result.get("messages", [])

    steps = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append(f"[Tool Call] {tc['name']}({tc['args']})")
        elif msg.__class__.__name__ == "ToolMessage":
            steps.append(f"[Tool Result] {msg.name}: {msg.content}")

    answer = messages[-1].content if messages else "No response generated."
    return {"answer": answer, "steps": steps}
