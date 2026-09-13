from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import settings


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _quarter_key(value: str) -> tuple[int, int]:
    try:
        quarter, year = value.split()
        return int(year), int(quarter.lstrip("Qq"))
    except (ValueError, TypeError):
        return 9999, 9


@lru_cache(maxsize=4)
def _load(name: str) -> tuple[dict, ...]:
    path = Path(settings.data_dir) / name
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{name} must contain a JSON array")
    return tuple(item for item in data if isinstance(item, dict))


def sales_data() -> list[dict]:
    return [dict(item) for item in _load("sales_data.json")]


def marketing_data() -> list[dict]:
    return [dict(item) for item in _load("marketing_data.json")]


def filter_options(
    source_sales: list[dict] | None = None,
    source_marketing: list[dict] | None = None,
) -> dict[str, list[str]]:
    sales = sales_data() if source_sales is None else source_sales
    marketing = marketing_data() if source_marketing is None else source_marketing
    return {
        "regions": sorted({str(row["region"]) for row in sales if row.get("region")}),
        "quarters": sorted(
            {str(row["quarter"]) for row in sales + marketing if row.get("quarter")},
            key=_quarter_key,
        ),
        "products": sorted({str(row["product"]) for row in sales if row.get("product")}),
        "channels": sorted({str(row["channel"]) for row in marketing if row.get("channel")}),
    }


def _filtered(
    filters: dict[str, str],
    source_sales: list[dict] | None = None,
    source_marketing: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    sales = sales_data() if source_sales is None else [dict(item) for item in source_sales]
    marketing = marketing_data() if source_marketing is None else [dict(item) for item in source_marketing]

    region = filters.get("region")
    quarter = filters.get("quarter")
    product = filters.get("product")
    channel = filters.get("channel")

    if region:
        sales = [row for row in sales if row.get("region") == region]
    if quarter:
        sales = [row for row in sales if row.get("quarter") == quarter]
        marketing = [row for row in marketing if row.get("quarter") == quarter]
    if product:
        sales = [row for row in sales if row.get("product") == product]
        marketing = [
            row for row in marketing
            if product.lower() in str(row.get("campaign_name", "")).lower()
        ]
    if channel:
        marketing = [row for row in marketing if row.get("channel") == channel]
    return sales, marketing


def _totals(rows: list[dict], label: str, metric: str, limit: int | None = None) -> list[dict]:
    values: dict[str, float] = defaultdict(float)
    for row in rows:
        values[str(row.get(label) or "Unknown")] += _number(row.get(metric))
    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
    if limit:
        ranked = ranked[:limit]
    return [{"name": name, "value": round(value, 2)} for name, value in ranked]


def _period_change(
    filters: dict[str, str],
    source_sales: list[dict] | None = None,
    source_marketing: list[dict] | None = None,
) -> float | None:
    comparison_filters = {key: value for key, value in filters.items() if key != "quarter"}
    rows, _ = _filtered(comparison_filters, source_sales, source_marketing)
    revenue: dict[str, float] = defaultdict(float)
    for row in rows:
        revenue[str(row.get("quarter") or "Unknown")] += _number(row.get("revenue"))
    quarters = sorted((key for key in revenue if key != "Unknown"), key=_quarter_key)
    current = filters.get("quarter") or (quarters[-1] if quarters else None)
    if not current or current not in quarters:
        return None
    index = quarters.index(current)
    if index == 0:
        return None
    previous = revenue[quarters[index - 1]]
    if not previous:
        return None
    return round((revenue[current] - previous) / previous * 100, 1)


def dashboard_snapshot(
    filters: dict[str, str] | None = None,
    source_sales: list[dict] | None = None,
    source_marketing: list[dict] | None = None,
) -> dict:
    filters = filters or {}
    sales, marketing = _filtered(filters, source_sales, source_marketing)

    revenue = sum(_number(row.get("revenue")) for row in sales)
    units = sum(_number(row.get("units_sold")) for row in sales)
    budget = sum(_number(row.get("budget")) for row in marketing)
    impressions = sum(_number(row.get("impressions")) for row in marketing)
    clicks = sum(_number(row.get("clicks")) for row in marketing)
    conversions = sum(_number(row.get("conversions")) for row in marketing)
    ctr = clicks / impressions * 100 if impressions else 0
    conversion_rate = conversions / clicks * 100 if clicks else 0
    cpa = budget / conversions if conversions else 0

    revenue_quarter = _totals(sales, "quarter", "revenue")
    revenue_quarter.sort(key=lambda item: _quarter_key(item["name"]))
    region_revenue = _totals(sales, "region", "revenue")
    top_products = _totals(sales, "product", "revenue", 6)

    conversions_quarter = _totals(marketing, "quarter", "conversions")
    conversions_quarter.sort(key=lambda item: _quarter_key(item["name"]))
    spend_quarter = _totals(marketing, "quarter", "budget")
    spend_quarter.sort(key=lambda item: _quarter_key(item["name"]))

    channel_map: dict[str, dict[str, float]] = defaultdict(
        lambda: {"conversions": 0, "budget": 0, "clicks": 0, "impressions": 0}
    )
    for row in marketing:
        item = channel_map[str(row.get("channel") or "Unknown")]
        item["conversions"] += _number(row.get("conversions"))
        item["budget"] += _number(row.get("budget"))
        item["clicks"] += _number(row.get("clicks"))
        item["impressions"] += _number(row.get("impressions"))
    channels = []
    for name, values in sorted(
        channel_map.items(), key=lambda item: item[1]["conversions"], reverse=True
    ):
        channels.append(
            {
                "name": name,
                "conversions": round(values["conversions"], 2),
                "budget": round(values["budget"], 2),
                "impressions": round(values["impressions"], 2),
                "clicks": round(values["clicks"], 2),
                "cpa": round(values["budget"] / values["conversions"], 2)
                if values["conversions"]
                else 0,
                "ctr": round(values["clicks"] / values["impressions"] * 100, 2)
                if values["impressions"]
                else 0,
                "conversion_rate": round(values["conversions"] / values["clicks"] * 100, 2)
                if values["clicks"]
                else 0,
            }
        )

    insights: list[str] = []
    if top_products:
        insights.append(
            f"{top_products[0]['name']} leads product revenue at ${top_products[0]['value']:,.0f}."
        )
    if region_revenue:
        insights.append(
            f"{region_revenue[0]['name']} is the strongest region with ${region_revenue[0]['value']:,.0f} in revenue."
        )
    if channels:
        insights.append(
            f"{channels[0]['name']} produced the most conversions ({channels[0]['conversions']:,.0f})."
        )
    if cpa:
        insights.append(f"Blended marketing cost per conversion is ${cpa:,.2f}.")

    return {
        "filters": filters,
        "coverage": {
            "sales_records": len(sales),
            "marketing_records": len(marketing),
        },
        "kpis": {
            "revenue": round(revenue, 2),
            "units": round(units, 2),
            "marketing_budget": round(budget, 2),
            "impressions": round(impressions, 2),
            "clicks": round(clicks, 2),
            "conversions": round(conversions, 2),
            "ctr": round(ctr, 2),
            "conversion_rate": round(conversion_rate, 2),
            "cost_per_conversion": round(cpa, 2),
            "period_change": _period_change(filters, source_sales, source_marketing),
        },
        "charts": {
            "revenue_by_quarter": revenue_quarter,
            "revenue_by_region": region_revenue,
            "top_products": top_products,
            "conversions_by_quarter": conversions_quarter,
            "spend_by_quarter": spend_quarter,
            "channel_performance": channels,
            "acquisition_funnel": [
                {"name": "Impressions", "value": round(impressions, 2)},
                {"name": "Clicks", "value": round(clicks, 2)},
                {"name": "Conversions", "value": round(conversions, 2)},
            ],
        },
        "insights": insights,
    }


def report_context(snapshot: dict, report_type: str, question: str = "") -> str:
    kpis = snapshot["kpis"]
    charts = snapshot["charts"]
    filters = snapshot["filters"] or {"scope": "all available data"}
    lines = [
        "VERIFIED BUSINESS DATA",
        f"Report type: {report_type}",
        f"Requested question: {question or 'standard performance review'}",
        f"Filters: {json.dumps(filters, ensure_ascii=False)}",
        f"Coverage: {json.dumps(snapshot['coverage'])}",
        f"Total revenue: ${kpis['revenue']:,.2f}",
        f"Units sold: {kpis['units']:,.0f}",
        f"Marketing budget: ${kpis['marketing_budget']:,.2f}",
        f"Impressions: {kpis['impressions']:,.0f}",
        f"Clicks: {kpis['clicks']:,.0f}",
        f"Conversions: {kpis['conversions']:,.0f}",
        f"Click-through rate: {kpis['ctr']:.2f}%",
        f"Conversion rate: {kpis['conversion_rate']:.2f}%",
        f"Cost per conversion: ${kpis['cost_per_conversion']:.2f}",
        f"Revenue by quarter: {json.dumps(charts['revenue_by_quarter'])}",
        f"Revenue by region: {json.dumps(charts['revenue_by_region'])}",
        f"Top products: {json.dumps(charts['top_products'])}",
        f"Conversions by quarter: {json.dumps(charts['conversions_by_quarter'])}",
        f"Marketing spend by quarter: {json.dumps(charts['spend_by_quarter'])}",
        f"Channel performance: {json.dumps(charts['channel_performance'])}",
        f"Detected insights: {json.dumps(snapshot['insights'], ensure_ascii=False)}",
    ]
    return "\n".join(lines)


def local_report(title: str, snapshot: dict, focus: str = "", question: str = "") -> str:
    kpis = snapshot["kpis"]
    charts = snapshot["charts"]
    filters = snapshot["filters"]
    coverage = snapshot["coverage"]
    scope = ", ".join(f"{key}: {value}" for key, value in filters.items()) or "All available data"
    focus_text = focus or "Identify the most important performance signals and next actions."
    question_text = question or "What should decision-makers know and do next?"

    def safe(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    scorecard: list[tuple[str, str, str]] = []
    if coverage["sales_records"]:
        scorecard.extend(
            [
                ("Revenue", f"${kpis['revenue']:,.0f}", f"{coverage['sales_records']:,} sales records"),
                ("Units sold", f"{kpis['units']:,.0f}", "Volume in the selected scope"),
            ]
        )
    if coverage["marketing_records"]:
        scorecard.extend(
            [
                ("Marketing investment", f"${kpis['marketing_budget']:,.0f}", f"{coverage['marketing_records']:,} marketing records"),
                ("Impressions", f"{kpis['impressions']:,.0f}", "Measured top-of-funnel reach"),
                ("Clicks", f"{kpis['clicks']:,.0f}", f"{kpis['ctr']:.2f}% click-through rate"),
                ("Conversions", f"{kpis['conversions']:,.0f}", f"{kpis['conversion_rate']:.2f}% of clicks"),
                ("Cost per conversion", f"${kpis['cost_per_conversion']:,.2f}", "Blended acquisition efficiency"),
            ]
        )
    scorecard_table = "\n".join(
        f"| {safe(metric)} | {safe(value)} | {safe(readout)} |"
        for metric, value, readout in scorecard
    )
    insights = "\n".join(f"- {safe(item)}" for item in snapshot["insights"])

    quarter_rows = charts["revenue_by_quarter"]
    revenue_trend = ""
    trend_signal = ""
    if quarter_rows:
        revenue_trend = "\n".join(
            f"| {safe(item['name'])} | ${item['value']:,.0f} | "
            f"{(item['value'] / kpis['revenue'] * 100 if kpis['revenue'] else 0):.1f}% |"
            for item in quarter_rows
        )
        if len(quarter_rows) > 1 and quarter_rows[0]["value"]:
            change = (quarter_rows[-1]["value"] - quarter_rows[0]["value"]) / quarter_rows[0]["value"] * 100
            direction = "higher" if change >= 0 else "lower"
            trend_signal = (
                f"Revenue in **{safe(quarter_rows[-1]['name'])}** was **{abs(change):.1f}% {direction}** "
                f"than **{safe(quarter_rows[0]['name'])}** within the available timeline."
            )

    product_rows = charts["top_products"][:6]
    product_table = "\n".join(
        f"| {index} | {safe(item['name'])} | ${item['value']:,.0f} | "
        f"{(item['value'] / kpis['revenue'] * 100 if kpis['revenue'] else 0):.1f}% |"
        for index, item in enumerate(product_rows, start=1)
    )
    region_rows = charts["revenue_by_region"][:6]
    region_table = "\n".join(
        f"| {index} | {safe(item['name'])} | ${item['value']:,.0f} | "
        f"{(item['value'] / kpis['revenue'] * 100 if kpis['revenue'] else 0):.1f}% |"
        for index, item in enumerate(region_rows, start=1)
    )
    channel_rows = charts["channel_performance"][:8]
    channel_table = "\n".join(
        f"| {index} | {safe(item['name'])} | {item['conversions']:,.0f} | "
        f"${item['budget']:,.0f} | ${item['cpa']:,.2f} | {item['ctr']:.2f}% |"
        for index, item in enumerate(channel_rows, start=1)
    )

    actions: list[tuple[str, str, str, str]] = []
    if product_rows:
        top = product_rows[0]
        share = top["value"] / kpis["revenue"] * 100 if kpis["revenue"] else 0
        actions.append(
            (
                "Now",
                "Sales lead",
                f"Protect momentum for {safe(top['name'])} and test whether its {share:.1f}% revenue share is repeatable.",
                "Revenue and mix by period",
            )
        )
    if region_rows:
        top = region_rows[0]
        actions.append(
            (
                "Next",
                "Regional lead",
                f"Document the commercial playbook behind {safe(top['name'])} before extending it to weaker regions.",
                "Regional revenue gap",
            )
        )
    efficient = [item for item in channel_rows if item["conversions"] > 0 and item["cpa"] > 0]
    if efficient:
        best = min(efficient, key=lambda item: item["cpa"])
        actions.append(
            (
                "Next",
                "Growth lead",
                f"Validate incremental budget for {safe(best['name'])}, currently the lowest-CPA measured channel.",
                "CPA and conversion volume",
            )
        )
    actions.append(
        (
            "Later",
            "Analytics owner",
            f"Run the next review around: {safe(focus_text)}",
            "Same KPI definitions and scope",
        )
    )
    action_table = "\n".join(
        f"| {horizon} | {owner} | {action} | {measure} |"
        for horizon, owner, action, measure in actions
    )

    summary_parts: list[str] = []
    if coverage["sales_records"]:
        summary_parts.append(
            f"**${kpis['revenue']:,.0f} in revenue** across **{kpis['units']:,.0f} units**"
        )
    if coverage["marketing_records"]:
        summary_parts.append(
            f"**{kpis['conversions']:,.0f} conversions** from **${kpis['marketing_budget']:,.0f}** in measured spend"
        )
    executive_signal = " and ".join(summary_parts) or "a verified dataset with no aggregatable performance metrics"

    sales_section = ""
    if quarter_rows or product_rows or region_rows:
        sales_section = f"""
## Revenue and market performance

{trend_signal or "The available sales scope does not contain enough periods for a directional comparison."}

### Revenue trajectory

| Period | Revenue | Share of scoped revenue |
|---|---:|---:|
{revenue_trend or "| No period dimension | — | — |"}

### Product concentration

| Rank | Product | Revenue | Share |
|---:|---|---:|---:|
{product_table or "| — | No mapped product dimension | — | — |"}

### Regional contribution

| Rank | Region | Revenue | Share |
|---:|---|---:|---:|
{region_table or "| — | No mapped region dimension | — | — |"}
"""

    marketing_section = ""
    if coverage["marketing_records"]:
        marketing_section = f"""
## Acquisition and channel efficiency

The measured funnel contains **{kpis['impressions']:,.0f} impressions**, **{kpis['clicks']:,.0f} clicks**, and **{kpis['conversions']:,.0f} conversions**. This produces a **{kpis['ctr']:.2f}% CTR**, **{kpis['conversion_rate']:.2f}% click-to-conversion rate**, and **${kpis['cost_per_conversion']:,.2f} blended CPA**.

| Rank | Channel | Conversions | Spend | CPA | CTR |
|---:|---|---:|---:|---:|---:|
{channel_table or "| — | No mapped channel dimension | — | — | — | — |"}
"""

    return f"""# {title}

> **Decision brief:** The selected scope produced {executive_signal}. The visual evidence and priorities below identify where attention should move next.

## Executive decision summary

**Question:** {safe(question_text)}

**Scope:** {safe(scope)}

**Analysis focus:** {safe(focus_text)}

The evidence covers **{coverage['sales_records']:,} sales records** and **{coverage['marketing_records']:,} marketing records** after filters were applied.

## Performance scorecard

| Metric | Verified value | Executive readout |
|---|---:|---|
{scorecard_table}

## What the data is saying

{insights or "- The selected records provide metrics but no comparative dimensions for an automated ranking."}

{sales_section}

{marketing_section}

## Risks and watchpoints

- Rankings show concentration, not causality; operational context is required before changing budgets or targets.
- Missing mapped dimensions reduce the comparisons available to the report.
- Historical performance should be validated against future periods before it is treated as a forecast.

## Recommended action plan

| Horizon | Suggested owner | Evidence-led action | Success measure |
|---|---|---|---|
{action_table}

## Data scope and methodology

Every number in this report was calculated from the selected source records after the displayed filters were applied. Visualizations use the same stored chart series as this narrative. Recommendations are decision prompts—not claims of causality or guaranteed forecasts.
""".strip()
