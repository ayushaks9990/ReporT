"""
visualizations.py
Generates charts into charts/ and returns list of file paths.
"""

import os
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from config import DATA_DIR, PROJECT_ROOT

CHARTS_DIR = str(Path(PROJECT_ROOT) / "charts")

os.makedirs(CHARTS_DIR, exist_ok=True)

try:
    plt.style.use("seaborn-v0_8-darkgrid")
except Exception:
    pass


def load_data():
    sales_data = []
    marketing_data = []

    try:
        with open(os.path.join(DATA_DIR, "sales_data.json"), "r", encoding="utf-8") as f:
            sales_data = json.load(f)
    except Exception as e:
        print(f"Could not load sales data: {e}")

    try:
        with open(os.path.join(DATA_DIR, "marketing_data.json"), "r", encoding="utf-8") as f:
            marketing_data = json.load(f)
    except Exception as e:
        print(f"Could not load marketing data: {e}")

    return sales_data, marketing_data


def _save(fig, filename):
    path = os.path.join(CHARTS_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _quarter_sort_key(value):
    try:
        quarter, year = str(value).split()
        return int(year), int(quarter.lstrip("Qq"))
    except Exception:
        return 9999, str(value)


def create_sales_by_region_chart(sales_data):
    revenue = defaultdict(float)

    for s in sales_data:
        revenue[s.get("region", "Unknown")] += float(s.get("revenue", 0))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(list(revenue.keys()), list(revenue.values()))
    ax.set_title("Sales Revenue by Region")
    ax.set_ylabel("Revenue")
    return _save(fig, "sales_by_region.png")


def create_quarterly_performance_chart(sales_data):
    revenue = defaultdict(float)

    for s in sales_data:
        revenue[s.get("quarter", "Unknown")] += float(s.get("revenue", 0))

    quarters = sorted(revenue.keys(), key=_quarter_sort_key)
    values = [revenue[q] for q in quarters]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(quarters, values, marker="o")
    ax.set_title("Quarterly Sales Performance")
    ax.set_ylabel("Revenue")

    return _save(fig, "quarterly_performance.png")


def create_product_performance_chart(sales_data):
    revenue = defaultdict(float)

    for s in sales_data:
        revenue[s.get("product", "Unknown")] += float(s.get("revenue", 0))

    fig, ax = plt.subplots(figsize=(8, 8))

    labels = list(revenue.keys())
    values = list(revenue.values())

    if values:
        ax.pie(values, labels=labels, autopct="%1.1f%%")

    ax.set_title("Product Revenue Distribution")

    return _save(fig, "product_performance.png")


def create_marketing_roi_chart(marketing_data):
    totals = defaultdict(lambda: {"budget": 0.0, "conversions": 0.0})
    for row in marketing_data:
        name = row.get("campaign_name", "Campaign")
        totals[name]["budget"] += float(row.get("budget", 0))
        totals[name]["conversions"] += float(row.get("conversions", 0))

    ranked = sorted(
        totals.items(),
        key=lambda item: item[1]["conversions"],
        reverse=True,
    )[:10]
    campaigns = [name[:28] for name, _ in ranked]
    cost_per_conversion = [
        values["budget"] / values["conversions"] if values["conversions"] else 0
        for _, values in ranked
    ]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(campaigns[::-1], cost_per_conversion[::-1])
    ax.set_xlabel("Cost per conversion ($)")
    ax.set_title("Top Campaigns: Cost per Conversion")

    return _save(fig, "marketing_roi.png")


def create_channel_performance_chart(marketing_data):
    conversions = defaultdict(float)

    for m in marketing_data:
        conversions[m.get("channel", "Unknown")] += float(m.get("conversions", 0))

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.bar(list(conversions.keys()), list(conversions.values()))
    ax.set_title("Conversions by Marketing Channel")

    return _save(fig, "channel_performance.png")


def create_top_products_chart(sales_data):
    revenue = defaultdict(float)

    for s in sales_data:
        revenue[s.get("product", "Unknown")] += float(s.get("revenue", 0))

    top = sorted(revenue.items(), key=lambda x: x[1], reverse=True)[:10]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.barh([x[0] for x in top], [x[1] for x in top])
    ax.set_title("Top Products by Revenue")

    return _save(fig, "top_products.png")


def create_region_comparison_chart(sales_data):
    revenue = defaultdict(float)
    units = defaultdict(float)

    for s in sales_data:
        region = s.get("region", "Unknown")
        revenue[region] += float(s.get("revenue", 0))
        units[region] += float(s.get("units_sold", 0))

    regions = list(revenue.keys())
    x = np.arange(len(regions))

    fig, ax = plt.subplots(figsize=(10, 6))

    revenue_bars = ax.bar(x - 0.2, [revenue[r] for r in regions], 0.4, label="Revenue")
    ax.set_ylabel("Revenue ($)")
    units_axis = ax.twinx()
    units_bars = units_axis.bar(
        x + 0.2,
        [units[r] for r in regions],
        0.4,
        color="tab:orange",
        label="Units Sold",
    )
    units_axis.set_ylabel("Units sold")
    ax.set_xticks(x)
    ax.set_xticklabels(regions)
    ax.legend([revenue_bars, units_bars], ["Revenue", "Units Sold"], loc="upper right")
    ax.set_title("Regional Revenue and Unit Comparison")

    return _save(fig, "regional_comparison.png")


def create_quarterly_growth_chart(sales_data):
    revenue = defaultdict(float)

    for s in sales_data:
        revenue[s.get("quarter", "Unknown")] += float(s.get("revenue", 0))

    quarters = sorted(revenue.keys(), key=_quarter_sort_key)
    values = [revenue[q] for q in quarters]

    growth = [0]

    for i in range(1, len(values)):
        prev = values[i - 1]
        cur = values[i]
        growth.append(((cur - prev) / prev * 100) if prev else 0)

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(quarters, growth, marker="o")
    ax.set_title("Quarterly Growth %")
    ax.set_ylabel("Growth %")

    return _save(fig, "quarterly_growth.png")


def generate_all_charts(
    sales_data=None,
    marketing_data=None,
    region=None,
    quarter=None,
    product=None,
    channel=None,
    domain=None,
):
    if sales_data is None or marketing_data is None:
        sales_data, marketing_data = load_data()

    if region:
        sales_data = [x for x in sales_data if x.get("region") == region]

    if quarter:
        sales_data = [x for x in sales_data if x.get("quarter") == quarter]
        marketing_data = [x for x in marketing_data if x.get("quarter") == quarter]

    if product:
        sales_data = [x for x in sales_data if x.get("product") == product]

    if channel:
        marketing_data = [x for x in marketing_data if x.get("channel") == channel]

    if domain == "sales":
        marketing_data = []
    elif domain == "marketing":
        sales_data = []

    charts = []

    chart_builders = []
    if sales_data:
        chart_builders.extend([
            (create_sales_by_region_chart, sales_data),
            (create_quarterly_performance_chart, sales_data),
            (create_product_performance_chart, sales_data),
            (create_top_products_chart, sales_data),
            (create_region_comparison_chart, sales_data),
            (create_quarterly_growth_chart, sales_data),
        ])
    if marketing_data:
        chart_builders.extend([
            (create_marketing_roi_chart, marketing_data),
            (create_channel_performance_chart, marketing_data),
        ])

    for builder, records in chart_builders:
        try:
            charts.append(builder(records))
        except Exception as e:
            print(f"{builder.__name__} failed: {e}")

    return charts


if __name__ == "__main__":
    files = generate_all_charts()
    print(files)
