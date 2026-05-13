"""
Mock action tools the agent calls when it needs to take real-world actions.
Each tool simulates a backend system (dispute tracker, notification service, compliance registry).
"""

from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# Input schemas
# Pydantic schemas with Field descriptions guide the local LLM to fill 
# arguments correctly. Enumerating valid values prevents hallucination.

class GetVendorPerformanceInput(BaseModel):
    vendor_id: str = Field(
        description=(
            'The unique vendor identifier (lowercase, underscores). '
            'Valid values: "acme_corp" or "techvendor".'
        )
    )


class RaiseDisputeInput(BaseModel):
    vendor_id: str = Field(
        description=(
            'The unique vendor identifier (lowercase, underscores). '
            'Valid values: "acme_corp" or "techvendor".'
        )
    )
    clause_ref: str = Field(
        description=(
            'The contract clause being violated. '
            'Example: "clause_4.2" for a delivery dispute, "section_3.1" for SLA breach.'
        )
    )
    reason: str = Field(
        description=(
            'A concise description of the violation. '
            'Example: "3 missed deliveries in a rolling 30-day period".'
        )
    )


class SendRenewalReminderInput(BaseModel):
    vendor_id: str = Field(
        description=(
            'The unique vendor identifier (lowercase, underscores). '
            'Valid values: "acme_corp" or "techvendor".'
        )
    )
    days_until_expiry: int = Field(
        description=(
            'Number of days remaining until the vendor contract expires. '
            'Example: 233 if the contract expires in about 8 months.'
        )
    )


class FlagComplianceGapInput(BaseModel):
    vendor_id: str = Field(
        description=(
            'The unique vendor identifier (lowercase, underscores). '
            'Valid values: "acme_corp" or "techvendor".'
        )
    )
    missing_cert: str = Field(
        description=(
            'The name of the missing or overdue compliance certification. '
            'Valid values: "ISO 27001", "Data Privacy Agreement", "Annual Security Audit".'
        )
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _short_id(prefix: str, vendor_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M")
    tag = vendor_id.upper().replace("_", "")[:6]
    return f"{prefix}-{tag}-{ts}"


# Tools

@tool(args_schema=GetVendorPerformanceInput)
def get_vendor_performance(vendor_id: str) -> str:
    """Fetch current performance metrics for a vendor: delivery stats, uptime, SLA breaches, incidents, and compliance status.
    Use this ONLY when you need live data about a vendor's current performance — not for contract terms or policy rules."""
    mock_data = {
        "acme_corp": {
            "name": "Acme Corp",
            "period": "last 30 days",
            "deliveries": {"scheduled": 4, "on_time": 1, "missed": 3, "late": 0},
            "uptime_pct": 97.2,
            "sla_breaches": 1,
            "open_incidents": 2,
            "last_incident": "2026-05-05 — API timeout causing 3-hour outage",
            "compliance": {
                "ISO 27001": "valid — expires 2026-11-30",
                "Data Privacy Agreement": "valid — expires 2027-01-01",
                "Annual Security Audit": "submitted 2025-12-10",
            },
        },
        "techvendor": {
            "name": "TechVendor Inc.",
            "period": "last 30 days",
            "deliveries": {"scheduled": 6, "on_time": 6, "missed": 0, "late": 0},
            "uptime_pct": 99.8,
            "sla_breaches": 0,
            "open_incidents": 0,
            "last_incident": "None",
            "compliance": {
                "ISO 27001": "MISSING — annual renewal overdue since 2026-04-01",
                "Data Privacy Agreement": "valid — expires 2026-12-31",
                "Annual Security Audit": "submitted 2025-11-15",
            },
        },
    }

    try:
        key = vendor_id.lower().strip().replace(" ", "_").replace("-", "_")
        data = mock_data.get(key)

        if not data:
            available = ", ".join(mock_data.keys())
            return (
                f"No performance data found for vendor '{vendor_id}'. "
                f"Available vendor IDs: {available}."
            )

        d = data["deliveries"]
        lines = [
            f"Vendor: {data['name']} ({key})",
            f"Period: {data['period']}",
            f"Deliveries — Scheduled: {d['scheduled']} | On-time: {d['on_time']} | Missed: {d['missed']} | Late: {d['late']}",
            f"Uptime: {data['uptime_pct']}%",
            f"SLA breaches: {data['sla_breaches']}",
            f"Open incidents: {data['open_incidents']}",
            f"Last incident: {data['last_incident']}",
            "Compliance status:",
        ]
        for cert, status in data["compliance"].items():
            lines.append(f"  • {cert}: {status}")

        return "\n".join(lines)

    except Exception as e:
        return f"[TOOL ERROR] get_vendor_performance failed: {e}"


@tool(args_schema=RaiseDisputeInput)
def raise_dispute(vendor_id: str, clause_ref: str, reason: str) -> str:
    """Formally raise a contractual dispute against a vendor for an SLA or delivery violation.
    Use this ONLY after confirming the violation via query_vendor_knowledge_base and get_vendor_performance — never raise a dispute without first verifying the facts."""
    try:
        dispute_id = _short_id("DISP", vendor_id)
        ts = _utc_now()

        return "\n".join([
            "Dispute raised successfully.",
            f"  Dispute ID   : {dispute_id}",
            f"  Vendor       : {vendor_id}",
            f"  Clause       : {clause_ref}",
            f"  Reason       : {reason}",
            f"  Timestamp    : {ts}",
            f"  Status       : OPEN",
            f"  Next steps   : Vendor has 14 calendar days to respond with a root cause analysis.",
            f"                 If unresolved after 14 days, escalation to legal will be triggered automatically.",
        ])

    except Exception as e:
        return f"[TOOL ERROR] raise_dispute failed: {e}"


@tool(args_schema=SendRenewalReminderInput)
def send_renewal_reminder(vendor_id: str, days_until_expiry: int) -> str:
    """Send a contract renewal reminder to a vendor whose contract is approaching expiry.
    Use this ONLY when the contract expiry date is within 365 days and a reminder is warranted."""
    try:
        ts = _utc_now()
        vendor_email = f"contracts@{vendor_id.replace('_', '')}.com"

        return "\n".join([
            "Renewal reminder sent successfully.",
            f"  Vendor           : {vendor_id}",
            f"  Days until expiry: {days_until_expiry}",
            f"  Recipients       : {vendor_email}, procurement@internalco.com",
            f"  Timestamp        : {ts}",
            f"  Next steps       : Vendor must acknowledge within 30 days.",
            f"                     Auto-escalation to legal if no response received.",
        ])

    except Exception as e:
        return f"[TOOL ERROR] send_renewal_reminder failed: {e}"


@tool(args_schema=FlagComplianceGapInput)
def flag_compliance_gap(vendor_id: str, missing_cert: str) -> str:
    """Flag a vendor for a missing or overdue compliance certification and notify the compliance team.
    Use this ONLY when a required certification (ISO 27001, Data Privacy Agreement, or Annual Security Audit) is confirmed missing."""
    try:
        flag_id = _short_id("COMP", vendor_id)
        ts = _utc_now()
        vendor_email = f"compliance@{vendor_id.replace('_', '')}.com"

        return "\n".join([
            "Compliance gap flagged successfully.",
            f"  Flag ID              : {flag_id}",
            f"  Vendor               : {vendor_id}",
            f"  Missing certification: {missing_cert}",
            f"  Timestamp            : {ts}",
            f"  Compliance team      : compliance@internalco.com (notified)",
            f"  Vendor notified      : {vendor_email}",
            f"  Cure period          : 30 calendar days from today to submit the certification.",
            f"  Next steps           : If unresolved after 30 days, contract suspension will be initiated.",
        ])

    except Exception as e:
        return f"[TOOL ERROR] flag_compliance_gap failed: {e}"
