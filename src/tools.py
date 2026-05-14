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
            "deliveries": {"scheduled": 17, "on_time": 13, "missed": 3, "late": 1},
            "uptime_pct": 97.3,
            "sla_breaches": 3,
            "open_incidents": 2,
            "last_incident": "2026-05-09 — payment processing service unresponsive for 83 minutes",
            "compliance": {
                "ISO 27001": "valid — expires 2026-08-23",
                "Data Privacy Agreement": "valid — expires 2026-10-11",
                "Annual Security Audit": "submitted 2026-02-19",
            },
        },
        "techvendor": {
            "name": "TechVendor Inc.",
            "period": "last 30 days",
            "deliveries": {"scheduled": 11, "on_time": 11, "missed": 0, "late": 0},
            "uptime_pct": 99.8,
            "sla_breaches": 0,
            "open_incidents": 0,
            "last_incident": "None",
            "compliance": {
                "ISO 27001": "valid — expires 2027-03-04",
                "Data Privacy Agreement": "valid — expires 2026-12-17",
                "Annual Security Audit": "MISSING — due 2026-04-01, not submitted",
            },
        },
        "meridian_soft": {
            "name": "Meridian Software Ltd.",
            "period": "last 30 days",
            "deliveries": {"scheduled": 8, "on_time": 7, "missed": 0, "late": 1},
            "uptime_pct": 99.2,
            "sla_breaches": 0,
            "open_incidents": 1,
            "last_incident": "2026-05-03 — CDN cache invalidation caused 18-minute degraded response times",
            "compliance": {
                "ISO 27001": "valid — expires 2027-01-28",
                "Data Privacy Agreement": "valid — expires 2027-04-06",
                "Annual Security Audit": "submitted 2026-03-11",
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
