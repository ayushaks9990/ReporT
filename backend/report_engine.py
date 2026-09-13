from __future__ import annotations

import logging

from backend.agent_engine import autogen_available, generate_autogen_report
from backend.analytics import local_report
from backend.config import settings


logger = logging.getLogger(__name__)

REPORT_LABELS = {
    "executive_summary": "Executive intelligence brief",
    "sales_performance": "Sales performance report",
    "marketing_campaign": "Marketing campaign report",
    "quarterly_summary": "Quarterly executive summary",
    "product_analysis": "Product performance analysis",
    "regional_analysis": "Regional growth analysis",
    "custom": "Custom intelligence report",
}


def build_title(report_type: str, filters: dict[str, str]) -> str:
    label = REPORT_LABELS.get(report_type, "Business intelligence report")
    detail = (
        filters.get("product")
        or filters.get("region")
        or filters.get("quarter")
        or filters.get("channel")
    )
    return f"{label} · {detail}" if detail else label


def generate_report(
    report_type: str,
    filters: dict[str, str],
    focus: str,
    question: str,
    snapshot: dict,
) -> tuple[str, str]:
    title = build_title(report_type, filters)
    if not settings.groq_api_key:
        return local_report(title, snapshot, focus, question), "Verified data engine"
    if not autogen_available():
        return (
            local_report(title, snapshot, focus, question),
            "Verified data engine · AutoGen unavailable",
        )

    try:
        result = generate_autogen_report(
            title=title,
            report_type=report_type,
            snapshot=snapshot,
            focus=focus,
            question=question,
        )
        return (
            result.content,
            f"Microsoft AutoGen · GROQ · {result.review_status}",
        )
    except Exception:
        logger.exception("AutoGen report generation failed; using the verified local engine")
        return (
            local_report(title, snapshot, focus, question),
            "Verified data engine · AutoGen fallback",
        )


def report_summary(snapshot: dict) -> str:
    kpis = snapshot["kpis"]
    parts: list[str] = []
    if snapshot["coverage"]["sales_records"]:
        parts.extend(
            [
                f"${kpis['revenue']:,.0f} revenue",
                f"{kpis['units']:,.0f} units",
            ]
        )
    if snapshot["coverage"]["marketing_records"]:
        parts.extend(
            [
                f"{kpis['conversions']:,.0f} conversions",
                f"{kpis['ctr']:.2f}% CTR",
            ]
        )
    return " · ".join(parts) or "Verified report generated from the selected source"
