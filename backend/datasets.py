from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from backend.models import Dataset


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 80

SALES_FIELDS = ["revenue", "units_sold", "product", "region", "quarter", "category", "customer_segment"]
MARKETING_FIELDS = ["budget", "impressions", "clicks", "conversions", "channel", "campaign_name", "quarter", "target_segment"]

ALIASES: dict[str, set[str]] = {
    "revenue": {"revenue", "sales", "sales_amount", "total_sales", "net_sales", "amount", "gmv", "turnover"},
    "units_sold": {"units_sold", "units", "quantity", "qty", "items_sold", "volume"},
    "product": {"product", "product_name", "item", "item_name", "sku", "service"},
    "region": {"region", "market", "territory", "location", "country", "state"},
    "quarter": {"quarter", "period", "month", "date", "year", "time_period"},
    "category": {"category", "product_category", "type", "segment"},
    "customer_segment": {"customer_segment", "customer_type", "buyer_segment", "client_segment"},
    "budget": {"budget", "spend", "cost", "ad_spend", "marketing_spend", "campaign_cost"},
    "impressions": {"impressions", "views", "reach", "exposures"},
    "clicks": {"clicks", "link_clicks", "visits", "traffic"},
    "conversions": {"conversions", "orders", "leads", "signups", "purchases", "acquisitions"},
    "channel": {"channel", "source", "platform", "medium", "marketing_channel"},
    "campaign_name": {"campaign_name", "campaign", "campaign_title", "ad_name"},
    "target_segment": {"target_segment", "audience", "target_audience", "segment"},
}


class DatasetError(ValueError):
    pass


def _header(value: Any) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", str(value or "column").strip().lower()).strip("_")
    return name[:80] or "column"


def _unique_headers(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: dict[str, int] = {}
    for value in values:
        base = _header(value)
        seen[base] = seen.get(base, 0) + 1
        result.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return result


def _clean_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)[:5000]
    text = str(value).strip()
    return text[:5000] if text else None


def _normalize_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    source_columns: list[str] = []
    for row in rows:
        for key in row:
            value = str(key)
            if value not in source_columns:
                source_columns.append(value)
    if not source_columns:
        raise DatasetError("The file has no columns")
    if len(source_columns) > MAX_COLUMNS:
        raise DatasetError(f"A maximum of {MAX_COLUMNS} columns is supported")

    columns = _unique_headers(source_columns)
    names = dict(zip(source_columns, columns))
    normalized = [
        {names[str(key)]: _clean_value(value) for key, value in row.items() if str(key) in names}
        for row in rows[:MAX_ROWS]
    ]
    normalized = [row for row in normalized if any(value not in (None, "") for value in row.values())]
    if not normalized:
        raise DatasetError("The file contains no usable rows")
    return normalized, columns


def parse_upload(filename: str, payload: bytes) -> tuple[list[dict], list[str]]:
    if not payload:
        raise DatasetError("The uploaded file is empty")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise DatasetError("The file is larger than the 5 MB upload limit")
    suffix = Path(filename or "").suffix.lower()
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetError("Use a UTF-8 encoded CSV or JSON file") from exc

    if suffix == ".csv":
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [dict(row) for row in csv.DictReader(io.StringIO(text), dialect=dialect)]
    elif suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"Invalid JSON near line {exc.lineno}") from exc
        if isinstance(value, dict):
            for key in ("data", "rows", "records", "items"):
                if isinstance(value.get(key), list):
                    value = value[key]
                    break
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise DatasetError("JSON must be an array of objects, or contain a data/rows/records array")
        rows = value
    else:
        raise DatasetError("Only .csv and .json files are supported")

    if len(rows) > MAX_ROWS:
        raise DatasetError(f"A maximum of {MAX_ROWS:,} rows is supported per dataset")
    return _normalize_rows(rows)


def to_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        number = float(text)
        return -number if negative and number > 0 else number
    except ValueError:
        return 0.0


def column_types(rows: list[dict], columns: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    sample = rows[:250]
    for column in columns:
        values = [row.get(column) for row in sample if row.get(column) not in (None, "")]
        if not values:
            result[column] = "empty"
            continue
        numeric = 0
        for value in values:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric += 1
            elif re.fullmatch(r"[\s$€£₹()%,+\-]*[0-9][0-9\s,]*(?:\.[0-9]+)?[%\s]*", str(value)):
                numeric += 1
        result[column] = "number" if numeric / len(values) >= 0.8 else "text"
    return result


def suggest_mapping(columns: list[str], types: dict[str, str], requested_kind: str) -> tuple[str, dict[str, str], str]:
    mapping: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        match = next((column for column in columns if column in aliases), None)
        if match and match not in mapping.values():
            mapping[target] = match

    sales_score = sum(field in mapping for field in SALES_FIELDS)
    marketing_score = sum(field in mapping for field in MARKETING_FIELDS)
    kind = requested_kind if requested_kind in {"sales", "marketing"} else (
        "marketing" if marketing_score > sales_score else "sales"
    )
    numeric = [column for column in columns if types.get(column) == "number" and column not in mapping.values()]
    if kind == "sales" and "revenue" not in mapping and numeric:
        mapping["revenue"] = numeric[0]
    if kind == "marketing" and not any(field in mapping for field in ("budget", "impressions", "clicks", "conversions")) and numeric:
        mapping["conversions"] = numeric[0]

    allowed = SALES_FIELDS if kind == "sales" else MARKETING_FIELDS
    mapping = {target: source for target, source in mapping.items() if target in allowed}
    ready = "revenue" in mapping if kind == "sales" else any(
        field in mapping for field in ("budget", "impressions", "clicks", "conversions")
    )
    return kind, mapping, "ready" if ready else "needs_mapping"


def validate_mapping(kind: str, mapping: dict[str, str], columns: list[str]) -> dict[str, str]:
    allowed = set(SALES_FIELDS if kind == "sales" else MARKETING_FIELDS)
    clean = {target: source for target, source in mapping.items() if target in allowed and source in columns}
    if len(clean.values()) != len(set(clean.values())):
        raise DatasetError("Each source column can map to only one field")
    if kind == "sales" and "revenue" not in clean:
        raise DatasetError("Map one numeric column to Revenue")
    if kind == "marketing" and not any(field in clean for field in ("budget", "impressions", "clicks", "conversions")):
        raise DatasetError("Map at least one performance metric such as Conversions, Clicks, Impressions, or Budget")
    return clean


def standardize_dataset(dataset: Dataset) -> tuple[list[dict], list[dict]]:
    mapping = dataset.mapping or {}
    if dataset.status != "ready":
        raise DatasetError("Finish mapping this dataset before analysis")

    if dataset.kind == "sales":
        sales: list[dict] = []
        for index, raw in enumerate(dataset.raw_rows, start=1):
            item = {
                "id": f"U{index:05d}",
                "revenue": to_number(raw.get(mapping.get("revenue", ""))),
                "units_sold": to_number(raw.get(mapping.get("units_sold", ""))),
                "product": str(raw.get(mapping.get("product", "")) or "Uncategorized"),
                "region": str(raw.get(mapping.get("region", "")) or "Unspecified"),
                "quarter": str(raw.get(mapping.get("quarter", "")) or "All periods"),
                "category": str(raw.get(mapping.get("category", "")) or "Uncategorized"),
                "customer_segment": str(raw.get(mapping.get("customer_segment", "")) or "Unspecified"),
            }
            sales.append(item)
        return sales, []

    marketing: list[dict] = []
    for index, raw in enumerate(dataset.raw_rows, start=1):
        item = {
            "id": f"U{index:05d}",
            "budget": to_number(raw.get(mapping.get("budget", ""))),
            "impressions": to_number(raw.get(mapping.get("impressions", ""))),
            "clicks": to_number(raw.get(mapping.get("clicks", ""))),
            "conversions": to_number(raw.get(mapping.get("conversions", ""))),
            "channel": str(raw.get(mapping.get("channel", "")) or "Unspecified"),
            "campaign_name": str(raw.get(mapping.get("campaign_name", "")) or "Untitled campaign"),
            "quarter": str(raw.get(mapping.get("quarter", "")) or "All periods"),
            "target_segment": str(raw.get(mapping.get("target_segment", "")) or "Unspecified"),
        }
        marketing.append(item)
    return [], marketing
