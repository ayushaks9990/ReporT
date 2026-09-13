from __future__ import annotations # Forward class definition
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json
import logging
import os
import re

from config import DATA_DIR

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Try to import user-provided vector DB adapter functions
VECTOR_DB_IMPORT_ERROR: Optional[Exception] = None
try:
    from vector_db import query_vectordb, initialize_chromadb  # type: ignore
except Exception as exc:
    query_vectordb = None
    initialize_chromadb = None
    VECTOR_DB_IMPORT_ERROR = exc
    logger.warning("Vector retrieval is unavailable; local JSON retrieval will be used: %s", exc)

# -------------------------
# Configuration helpers
# -------------------------
DEFAULT_N_RESULTS = int(os.getenv("RAG_DEFAULT_N_RESULTS", "5"))
DEFAULT_MAX_CONTENT_CHARS = int(os.getenv("RAG_MAX_CONTENT_CHARS", "2000"))
DEFAULT_CONTEXT_MAX_ITEMS = int(os.getenv("RAG_CONTEXT_MAX_ITEMS", "5"))

# Optional collection overrides (useful if your vector DB stores different domains separately)
COLLECTION_OVERRIDES = {
    "sales": os.getenv("VECTOR_DB_SALES_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "marketing": os.getenv("VECTOR_DB_MARKETING_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "combined": os.getenv("VECTOR_DB_COMBINED_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "product": os.getenv("VECTOR_DB_PRODUCT_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "regional": os.getenv("VECTOR_DB_REGIONAL_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "custom": os.getenv("VECTOR_DB_CUSTOM_COLLECTION") or os.getenv("VECTOR_DB_COLLECTION") or None,
    "all": os.getenv("VECTOR_DB_COLLECTION") or None,
}


def _coerce_query(query: str, analysis_focus: Optional[str] = None) -> str:
    """Append the user focus to the retrieval query so the vector search is better targeted."""
    query = (query or "").strip()
    analysis_focus = (analysis_focus or "").strip()
    if not analysis_focus:
        return query
    return f"{query}\n\nUser analysis focus:\n{analysis_focus}" if query else f"User analysis focus:\n{analysis_focus}"


def _safe_currency(val: Any) -> str:
    """Format numeric currency safely for inclusion in prompts."""
    try:
        if val is None:
            return "N/A"
        v = float(val)
        if abs(v - int(v)) < 0.001:
            return f"${int(v):,}"
        return f"${v:,.2f}"
    except Exception:
        return str(val)


def _safe_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _load_json_records(filename: str) -> List[Dict[str, Any]]:
    path = Path(DATA_DIR) / filename
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("the JSON root must be an array")
        records = [item for item in payload if isinstance(item, dict)]
        if not records:
            raise ValueError("the dataset contains no object records")
        return records
    except Exception as exc:
        logger.error("Unable to load %s: %s", path, exc)
        return []


def _query_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (query or "").lower())
        if len(token) >= 3
    }


def _detect_filters(
    records: List[Dict[str, Any]],
    query: str,
    fields: List[str],
) -> Dict[str, List[str]]:
    """Find dataset values explicitly mentioned in a natural-language query."""
    query_lower = (query or "").lower()
    tokens = _query_tokens(query)
    ignored_aliases = {"marketing", "campaign", "performance", "platform", "suite", "data"}
    detected: Dict[str, List[str]] = {}

    for field in fields:
        values = sorted({str(row.get(field, "")).strip() for row in records if row.get(field)})
        exact = [value for value in values if value.lower() in query_lower]
        if exact:
            detected[field] = exact
            continue

        # Accept an unambiguous shortened value such as "Email" for
        # "Email Marketing", while avoiding broad words such as "marketing".
        alias_matches: Dict[str, List[str]] = defaultdict(list)
        for value in values:
            for token in set(re.findall(r"[a-z0-9]+", value.lower())):
                if len(token) >= 4 and token not in ignored_aliases:
                    alias_matches[token].append(value)
        inferred = {
            matches[0]
            for token, matches in alias_matches.items()
            if token in tokens and len(set(matches)) == 1
        }
        if inferred:
            detected[field] = sorted(inferred)

    # Avoid double-filtering when a shorter dimension value is part of a more
    # specific value, e.g. category "Analytics" inside product
    # "Analytics Dashboard" or segment "Enterprise" inside a product name.
    all_values = [
        (field, value)
        for field, values in detected.items()
        for value in values
    ]
    for field in list(detected):
        detected[field] = [
            value
            for value in detected[field]
            if not any(
                other_field != field
                and value.lower() != other_value.lower()
                and value.lower() in other_value.lower()
                for other_field, other_value in all_values
            )
        ]
        if not detected[field]:
            detected.pop(field)

    return detected


def _apply_filters(
    records: List[Dict[str, Any]],
    filters: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    if not filters:
        return list(records)
    return [
        row
        for row in records
        if all(str(row.get(field, "")) in accepted for field, accepted in filters.items())
    ]


def _top_totals(
    records: List[Dict[str, Any]],
    label_field: str,
    metric_field: str,
    limit: int = 5,
) -> str:
    totals: Dict[str, float] = defaultdict(float)
    for row in records:
        label = str(row.get(label_field) or "Unknown")
        totals[label] += _safe_number(row.get(metric_field))
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return "; ".join(f"{name}: {value:,.0f}" for name, value in ranked) or "N/A"


def _filter_description(filters: Dict[str, List[str]]) -> str:
    if not filters:
        return "none (all records included)"
    return "; ".join(
        f"{field.replace('_', ' ')}={', '.join(values)}"
        for field, values in filters.items()
    )


def _rank_sample_records(
    records: List[Dict[str, Any]],
    query: str,
    metric_field: str,
    limit: int,
) -> List[Dict[str, Any]]:
    tokens = _query_tokens(query)

    def score(row: Dict[str, Any]) -> tuple[int, float]:
        text = " ".join(str(value) for value in row.values()).lower()
        overlap = sum(1 for token in tokens if token in text)
        return overlap, _safe_number(row.get(metric_field))

    return sorted(records, key=score, reverse=True)[: max(1, limit)]


def _sales_context(query: str, n_results: int) -> str:
    records = _load_json_records("sales_data.json")
    if not records:
        return ""

    filters = _detect_filters(
        records,
        query,
        ["region", "quarter", "product", "category", "customer_segment", "sales_rep"],
    )
    matched = _apply_filters(records, filters)
    exact_match = bool(matched)
    analysis_rows = matched if exact_match else records

    total_revenue = sum(_safe_number(row.get("revenue")) for row in analysis_rows)
    total_units = sum(_safe_number(row.get("units_sold")) for row in analysis_rows)
    average_revenue = total_revenue / len(analysis_rows) if analysis_rows else 0
    coverage = sorted({str(row.get("quarter")) for row in records if row.get("quarter")})

    lines = [
        "SALES DATASET SUMMARY (calculated directly from sales_data.json)",
        f"Applied filters: {_filter_description(filters)}",
        f"Matched records: {len(matched)} of {len(records)}",
    ]
    if filters and not exact_match:
        lines.append(
            "Coverage notice: no rows matched every requested filter; the overall "
            f"dataset summary is shown instead. Available quarters: {', '.join(coverage)}."
        )
    lines.extend(
        [
            f"Total revenue: {_safe_currency(total_revenue)}",
            f"Total units sold: {total_units:,.0f}",
            f"Average revenue per record: {_safe_currency(average_revenue)}",
            f"Top products by revenue: {_top_totals(analysis_rows, 'product', 'revenue')}",
            f"Top regions by revenue: {_top_totals(analysis_rows, 'region', 'revenue')}",
            f"Revenue by quarter: {_top_totals(analysis_rows, 'quarter', 'revenue', limit=8)}",
            "Representative sales records:",
        ]
    )
    for row in _rank_sample_records(analysis_rows, query, "revenue", n_results):
        lines.append(f"- {row.get('description') or json.dumps(row, ensure_ascii=False)}")
    return "\n".join(lines)


def _marketing_context(query: str, n_results: int) -> str:
    records = _load_json_records("marketing_data.json")
    if not records:
        return ""

    filters = _detect_filters(
        records,
        query,
        ["channel", "quarter", "campaign_name", "target_segment"],
    )
    query_lower = (query or "").lower()
    sales_records = _load_json_records("sales_data.json")
    product_mentions = sorted({
        str(row.get("product"))
        for row in sales_records
        if row.get("product") and str(row.get("product")).lower() in query_lower
    })
    region_mentions = sorted({
        str(row.get("region"))
        for row in sales_records
        if row.get("region") and str(row.get("region")).lower() in query_lower
    })

    candidate_rows = records
    if product_mentions:
        candidate_rows = [
            row
            for row in candidate_rows
            if any(product in str(row.get("campaign_name", "")) for product in product_mentions)
        ]

    matched = _apply_filters(candidate_rows, filters)
    exact_match = bool(matched)
    analysis_rows = matched if exact_match else records
    display_filters = dict(filters)
    if product_mentions:
        display_filters["promoted_product"] = product_mentions

    budget = sum(_safe_number(row.get("budget")) for row in analysis_rows)
    impressions = sum(_safe_number(row.get("impressions")) for row in analysis_rows)
    clicks = sum(_safe_number(row.get("clicks")) for row in analysis_rows)
    conversions = sum(_safe_number(row.get("conversions")) for row in analysis_rows)
    ctr = clicks / impressions * 100 if impressions else 0
    conversion_rate = conversions / clicks * 100 if clicks else 0
    cost_per_conversion = budget / conversions if conversions else 0
    coverage = sorted({str(row.get("quarter")) for row in records if row.get("quarter")})

    lines = [
        "MARKETING DATASET SUMMARY (calculated directly from marketing_data.json)",
        f"Applied filters: {_filter_description(display_filters)}",
        f"Matched records: {len(matched)} of {len(records)}",
    ]
    if region_mentions:
        lines.append(
            "Coverage notice: marketing_data.json has no region field, so marketing "
            f"metrics cannot be filtered for {', '.join(region_mentions)}."
        )
    if display_filters and not exact_match:
        lines.append(
            "Coverage notice: no rows matched every requested filter; the overall "
            f"dataset summary is shown instead. Available quarters: {', '.join(coverage)}."
        )
    lines.extend(
        [
            f"Total budget: {_safe_currency(budget)}",
            f"Total impressions: {impressions:,.0f}",
            f"Total clicks: {clicks:,.0f}",
            f"Total conversions: {conversions:,.0f}",
            f"Click-through rate: {ctr:.2f}%",
            f"Click-to-conversion rate: {conversion_rate:.2f}%",
            f"Cost per conversion: {_safe_currency(cost_per_conversion)}",
            f"Top channels by conversions: {_top_totals(analysis_rows, 'channel', 'conversions')}",
            f"Top campaigns by conversions: {_top_totals(analysis_rows, 'campaign_name', 'conversions')}",
            f"Conversions by quarter: {_top_totals(analysis_rows, 'quarter', 'conversions', limit=8)}",
            "Representative marketing records:",
        ]
    )
    for row in _rank_sample_records(analysis_rows, query, "conversions", n_results):
        lines.append(f"- {row.get('description') or json.dumps(row, ensure_ascii=False)}")
    return "\n".join(lines)


def build_local_data_context(
    query: str,
    filter_type: Optional[str] = None,
    n_results: int = DEFAULT_N_RESULTS,
) -> str:
    """Build a reliable, numeric context directly from the bundled JSON data."""
    if filter_type == "sales":
        return _sales_context(query, n_results)
    if filter_type == "marketing":
        return _marketing_context(query, n_results)

    per_domain = max(1, int(n_results) // 2)
    sections = [
        section
        for section in (
            _sales_context(query, per_domain),
            _marketing_context(query, per_domain),
        )
        if section
    ]
    return "\n\n".join(sections)


# -------------------------
# Vector DB compatibility layer
# -------------------------
#Then The chromadb initalize return dict string have to normalize
def _normalize_collection_result(init_result: Any) -> Any:
    """Extract a usable collection object from various initializer return shapes."""
    if init_result is None:
        return None

    # Common patterns:
    # 1) (client, collection)
    # 2) {"client": ..., "collection": ...}
    # 3) collection directly
    if isinstance(init_result, tuple) and len(init_result) >= 2:
        return init_result[1]
    if isinstance(init_result, dict):
        for key in ("collection", "col", "db_collection"):
            if key in init_result:
                return init_result[key]
    return init_result

# Tries Then different ways of calling query_vectordb() to ensure compatibility with different vector database implementations.
def _call_query_vectordb(collection: Any, query: str, n_results: int, filter_dict: Optional[Dict[str, Any]] = None) -> Any:
    """Call query_vectordb with the adapter signature it supports."""
    if query_vectordb is None:
        raise RuntimeError("vector_db.query_vectordb is not available")
    last_exc: Optional[Exception] = None
    candidates = [
        # Preferred keyword style
        lambda: query_vectordb(collection, query, n_results=n_results, filter_dict=filter_dict),
        # Alternate keyword names
        lambda: query_vectordb(collection, query, n_results=n_results, where=filter_dict),
        # Positional fallback
        lambda: query_vectordb(collection, query, n_results, filter_dict),
        lambda: query_vectordb(collection, query, n_results),
        lambda: query_vectordb(collection, query),
    ]
    for attempt in candidates:
        try:
            return attempt()
        except TypeError as e:
            last_exc = e
            continue
        except Exception as e:
            # Other exceptions should be surfaced to the caller
            raise e
    raise last_exc or RuntimeError("Unable to call query_vectordb with known signatures")

# It only initializes ChromaDB and returns the collection (database/table) that will be searched.
def _get_collection(collection_name: Optional[str] = None) -> Any:
    """Initialize chromadb and return the most appropriate collection object."""
    if initialize_chromadb is None:
        return None
    init_result = initialize_chromadb()
    collection = _normalize_collection_result(init_result)

    # If the initializer returned a client/dict with multiple collections, try common access patterns.
    if collection_name and isinstance(init_result, dict):
        for key in (collection_name, f"{collection_name}_collection", f"{collection_name}Collection"):
            if key in init_result:
                return init_result[key]

    return collection


# -------------------------
# Retrieval and formatting
# -------------------------
# retrival of the query answer
def retrieve_relevant_context(
    query: str,
    n_results: int = DEFAULT_N_RESULTS,
    filter_type: Optional[str] = None,
    analysis_focus: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve raw results from the vector DB. Returns a dict or None on failure."""
    if initialize_chromadb is None or query_vectordb is None:
        logger.warning("vector_db functions not available; cannot fetch real context.")
        return None

    safe_query = _coerce_query(query, analysis_focus=analysis_focus)
    filter_dict = {"type": filter_type} if filter_type else None

    try:
        collection = _get_collection(collection_name)
        if collection is None:
            logger.warning("No vector DB collection available after initialization.")
            return None
    except Exception as e:
        logger.exception("Failed to initialize vector DB collection: %s", e)
        return None

    try:
        results = _call_query_vectordb(collection, safe_query, n_results=n_results, filter_dict=filter_dict)

        # Normalize common shapes for downstream formatting.
        if results is None:
            return None
        if isinstance(results, dict):
            return results
        if isinstance(results, list):
            # Accept either a list of docs, list of dicts, or list of tuples.
            return {"documents": [results], "metadatas": [[]], "distances": [[]]}

        # Some adapters return a raw string or single object
        return {"documents": [[str(results)]], "metadatas": [[{}]], "distances": [[0.0]]}
    except Exception as e:
        logger.exception("Vector DB query failed: %s", e)
        return None


def _extract_nested(block: Any) -> List[Any]:
    """Handle shapes like [[...]] or [...] and always return a flat list."""
    if block is None:
        return []
    if isinstance(block, list) and block and isinstance(block[0], list):
        return list(block[0])
    if isinstance(block, list):
        return list(block)
    return [block]

# It Then formats the retrieved results into a consistent structure and includes the existing metadata with each document.
def format_retrieval_results(results: Optional[Dict[str, Any]]) -> Union[str, List[Dict[str, Any]]]:
    """Normalize and format raw retrieval results into a list of items or a string message."""
    if not results:
        return "No relevant information found."

    try:
        # If a caller already passed a list of formatted items, accept it.
        if isinstance(results, list):
            if results and isinstance(results[0], dict) and {"rank", "content"}.issubset(results[0].keys()):
                return results
            # Otherwise treat as document list.
            docs = results
            metas = [{} for _ in docs]
            dists = [0.0 for _ in docs]
        else:
            documents_block = results.get("documents")
            metadatas_block = results.get("metadatas")
            distances_block = results.get("distances")

            docs = _extract_nested(documents_block)
            metas = _extract_nested(metadatas_block)
            dists = _extract_nested(distances_block)

            if not docs:
                # Also support alternative keys from some adapters.
                for alt_key in ("data", "items", "results"):
                    if alt_key in results and isinstance(results[alt_key], list):
                        docs = results[alt_key]
                        metas = [{} for _ in docs]
                        dists = [0.0 for _ in docs]
                        break

        if not docs:
            return "No relevant information found."

        formatted: List[Dict[str, Any]] = []
        for i, doc in enumerate(docs):
            if doc is None:
                continue

            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            dist = dists[i] if i < len(dists) else 0.0

            try:
                relevance_score = max(0.0, min(1.0, 1.0 - float(dist)))
            except Exception:
                relevance_score = 1.0

            content = doc if isinstance(doc, str) else str(doc)
            formatted.append(
                {
                    "rank": len(formatted) + 1,
                    "relevance_score": relevance_score,
                    "type": (meta or {}).get("type", "unknown"),
                    "content": content,
                    "metadata": meta or {},
                }
            )

        return formatted if formatted else "No relevant information found."
    except Exception as e:
        logger.exception("Failed to format retrieval results: %s", e)
        return "No relevant information found."

# ItThen combines all the formatted retrieval items into a single text string (context), which is then sent to the LLM as part of the prompt.
def create_context_string(formatted_context: Union[str, List[Dict[str, Any]]], max_items: int = DEFAULT_CONTEXT_MAX_ITEMS) -> str:
    """Create a single prompt-ready context string for the LLM."""
    if isinstance(formatted_context, str):
        return formatted_context

    parts: List[str] = ["Retrieved relevant information:"]
    count = 0

    for item in formatted_context:
        if count >= max_items:
            break
        if not isinstance(item, dict):
            continue

        count += 1
        rank = item.get("rank", count)
        typ = str(item.get("type", "unknown")).upper()
        score = item.get("relevance_score", 1.0)
        parts.append(f"\n{rank}. [{typ}] (Relevance: {score:.2f})")

        content = str(item.get("content", ""))
        if len(content) > DEFAULT_MAX_CONTENT_CHARS:
            content = content[:DEFAULT_MAX_CONTENT_CHARS] + " ...[truncated]"
        parts.append(f"   {content}")

        meta = item.get("metadata", {}) or {}
        meta_parts: List[str] = []

        item_type = str(item.get("type", "")).lower()
        if item_type == "sales":
            product = meta.get("product") or meta.get("product_name") or "N/A"
            revenue = _safe_currency(meta.get("revenue"))
            region = meta.get("region", "N/A")
            quarter = meta.get("quarter", "N/A")
            meta_parts.extend([
                f"Product: {product}",
                f"Revenue: {revenue}",
                f"Region: {region}",
                f"Quarter: {quarter}",
            ])
        elif item_type == "marketing":
            campaign = meta.get("campaign_name") or meta.get("campaign") or "N/A"
            channel = meta.get("channel", "N/A")
            budget = _safe_currency(meta.get("budget"))
            conversions = meta.get("conversions", "N/A")
            meta_parts.extend([
                f"Campaign: {campaign}",
                f"Channel: {channel}",
                f"Budget: {budget}",
                f"Conversions: {conversions}",
            ])
        else:
            if isinstance(meta, dict):
                if "source" in meta:
                    meta_parts.append(f"Source: {meta['source']}")
                if "id" in meta:
                    meta_parts.append(f"ID: {meta['id']}")
                if "region" in meta:
                    meta_parts.append(f"Region: {meta['region']}")
                if "quarter" in meta:
                    meta_parts.append(f"Quarter: {meta['quarter']}")
                if "product" in meta:
                    meta_parts.append(f"Product: {meta['product']}")
                if "campaign_name" in meta:
                    meta_parts.append(f"Campaign: {meta['campaign_name']}")

        if meta_parts:
            parts.append("   " + " | ".join(meta_parts))

    if count == 0:
        return "No relevant information found."
    return "\n".join(parts)


# -------------------------
# Convenience wrappers used by agent.py / report generators
# -------------------------
#Simply Then chains these three steps before this together so other functions don't have to call each one separately.
def _wrap_retrieval(
    query: str,
    n_results: int = DEFAULT_N_RESULTS,
    filter_type: Optional[str] = None,
    analysis_focus: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> str:
    # The exact-data summary is always included. Chroma adds semantic examples
    # when available, but access to the bundled data never depends on Chroma.
    local_context = build_local_data_context(
        _coerce_query(query, analysis_focus),
        filter_type=filter_type,
        n_results=n_results,
    )
    results = retrieve_relevant_context(
        query,
        n_results=n_results,
        filter_type=filter_type,
        analysis_focus=analysis_focus,
        collection_name=collection_name,
    )
    formatted = format_retrieval_results(results)
    vector_context = create_context_string(formatted)

    sections = []
    if local_context:
        sections.append(local_context)
    if vector_context and "No relevant information found" not in vector_context:
        sections.append("SEMANTIC RETRIEVAL RESULTS\n" + vector_context)

    if sections:
        return "\n\n".join(sections)
    return (
        "DATA RETRIEVAL ERROR: neither the bundled JSON datasets nor the vector "
        "database could provide records. Check DATA_DIR and ChromaDB initialization."
    )


def retrieve_sales_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type="sales",
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("sales"),
    )


def retrieve_marketing_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type="marketing",
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("marketing"),
    )


def retrieve_combined_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type=None,
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("combined"),
    )


# Extra helpers for report_generator.py / app.py compatibility

def retrieve_product_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type="product",
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("product"),
    )


def retrieve_regional_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type="regional",
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("regional"),
    )


def retrieve_custom_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type="custom",
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("custom"),
    )


def retrieve_all_data(query: str, n_results: int = DEFAULT_N_RESULTS, analysis_focus: Optional[str] = None) -> str:
    return _wrap_retrieval(
        query,
        n_results=n_results,
        filter_type=None,
        analysis_focus=analysis_focus,
        collection_name=COLLECTION_OVERRIDES.get("all"),
    )


# Backwards-compatible aliases that some codebases use
retrieve_context = retrieve_relevant_context
retrieve_relevant_data = retrieve_relevant_context

# Then The checks whether the Python file is being run directly or imported as a module.
if __name__ == "__main__":
    print("RAG retrieval smoke test")
    q = "Top performing products in North America"
    ctx = retrieve_combined_data(q, n_results=3, analysis_focus="Focus on enterprise customers.")
    try:
        print("\nContext:\n", ctx)
    except Exception:
        print("\nContext (raw):", json.dumps(ctx, indent=2) if isinstance(ctx, (dict, list)) else str(ctx))
