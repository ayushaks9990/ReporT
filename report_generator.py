"""
report_generator.py - convenience wrappers and CLI around agent + RAG.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import argparse
from datetime import datetime
import json
import logging
import os
import re

# Prefer the richer multi-agent entrypoint, but keep the legacy wrapper available.
try:
    from agent import generate_report_with_autogen_multiagent, generate_report_with_rag, generate_custom_report
except Exception as e:  # pragma: no cover
    raise RuntimeError("Failed to import agent module. Ensure agent.py is present and importable.") from e

# Optional direct RAG preview / fallback utilities.
try:
    from rag_retrieval import (
        retrieve_sales_data,
        retrieve_marketing_data,
        retrieve_combined_data,
        retrieve_product_data,
        retrieve_regional_data,
        retrieve_custom_data,
        retrieve_all_data,
    )
except Exception:  # pragma: no cover
    retrieve_sales_data = None
    retrieve_marketing_data = None
    retrieve_combined_data = None
    retrieve_product_data = None
    retrieve_regional_data = None
    retrieve_custom_data = None
    retrieve_all_data = None

# Logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# -------------------------
# Internal helpers
# -------------------------

def _clean_text(val: Optional[str]) -> str:
    return (val or "").strip()


def _build_focus(query: str, analysis_focus: Optional[str] = None) -> str:
    query = _clean_text(query)
    focus = _clean_text(analysis_focus)
    if not focus:
        return query
    return f"{query}\n\nUser analysis focus:\n{focus}" if query else f"User analysis focus:\n{focus}"


def _generate(query: str, report_type: str, n_results: int = 8, analysis_focus: str = "") -> str:
    """Single place to call the report engine with consistent arguments."""
    # Keep the older multi-agent wrapper as the primary path because app.py depends on the
    # report_generator layer, not agent.py directly.
    return generate_report_with_autogen_multiagent(
        query,
        report_type=report_type,
        n_results=n_results,
        analysis_focus=analysis_focus,
    )


def _preview_context(kind: str, query: str, n_results: int = 5, analysis_focus: str = "") -> str:
    """Optional helper for direct retrieval previews or debugging."""
    retrieval_map = {
        "sales": retrieve_sales_data,
        "marketing": retrieve_marketing_data,
        "combined": retrieve_combined_data,
        "product": retrieve_product_data,
        "regional": retrieve_regional_data,
        "custom": retrieve_custom_data,
        "all": retrieve_all_data,
    }
    fn = retrieval_map.get(kind)
    if fn is None:
        return "RAG retrieval helpers are unavailable."
    try:
        try:
            return fn(_build_focus(query, analysis_focus), n_results=n_results, analysis_focus=analysis_focus)  # type: ignore[arg-type]
        except TypeError:
            return fn(_build_focus(query, analysis_focus), n_results=n_results)  # type: ignore[misc]
    except Exception as e:
        logger.exception("Context preview failed: %s", e)
        return f"ERROR: failed to retrieve context — {e}"


# -------------------------
# Report helpers
# -------------------------

def generate_sales_performance_report(
    region: Optional[str] = None,
    quarter: Optional[str] = None,
    analysis_focus: str = "",
) -> str:
    query_parts = ["Analyze sales performance"]
    if region:
        query_parts.append(f"in {region}")
    if quarter:
        query_parts.append(f"for {quarter}")
    query = " ".join(query_parts)
    logger.info("Generating sales performance report — Query: %s", query)
    try:
        return _generate(query, report_type="sales", n_results=8, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate sales performance report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


def generate_marketing_campaign_report(
    channel: Optional[str] = None,
    quarter: Optional[str] = None,
    analysis_focus: str = "",
) -> str:
    query_parts = ["Analyze marketing campaign performance"]
    if channel:
        query_parts.append(f"for {channel} channel")
    if quarter:
        query_parts.append(f"in {quarter}")
    query = " ".join(query_parts)
    logger.info("Generating marketing campaign report — Query: %s", query)
    try:
        return _generate(query, report_type="marketing", n_results=8, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate marketing campaign report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


def generate_quarterly_summary_report(quarter: str, analysis_focus: str = "") -> str:
    quarter = _clean_text(quarter)
    query = f"Provide a comprehensive summary of sales and marketing performance for {quarter}"
    logger.info("Generating quarterly summary report — Query: %s", query)
    try:
        return _generate(query, report_type="combined", n_results=10, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate quarterly summary report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


def generate_product_analysis_report(product_name: str, analysis_focus: str = "") -> str:
    product_name = _clean_text(product_name)
    query = f"Analyze the performance and marketing of {product_name}"
    logger.info("Generating product analysis report — Query: %s", query)
    try:
        # product-oriented reports benefit from combined context unless you have a dedicated product collection
        return _generate(query, report_type="combined", n_results=8, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate product analysis report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


def generate_regional_analysis_report(region: str, analysis_focus: str = "") -> str:
    region = _clean_text(region)
    query = f"Analyze sales and marketing performance in {region}"
    logger.info("Generating regional analysis report — Query: %s", query)
    try:
        return _generate(query, report_type="combined", n_results=8, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate regional analysis report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


def generate_custom_analysis_report(custom_query: str, analysis_focus: str = "") -> str:
    custom_query = _clean_text(custom_query)
    logger.info("Generating custom analysis report — Query: %s", custom_query)
    try:
        # Preserve the existing behavior of using the report pipeline.
        return _generate(custom_query, report_type="combined", n_results=8, analysis_focus=analysis_focus)
    except Exception as e:
        logger.exception("Failed to generate custom analysis report: %s", e)
        return f"ERROR: Failed to generate report — {e}"


# Alternate names some codebases expect

def generate_sales_report(*args, **kwargs):
    return generate_sales_performance_report(*args, **kwargs)


def generate_marketing_report(*args, **kwargs):
    return generate_marketing_campaign_report(*args, **kwargs)


def generate_quarterly_report(*args, **kwargs):
    return generate_quarterly_summary_report(*args, **kwargs)


# -------------------------
# File utilities
# -------------------------

def _sanitize_filename_component(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("._")


def _normalize_output_path(filename: str, folder: Optional[str] = None) -> str:
    """Preserve full paths when the caller already provided them.

    app.py passes a full path via `filename=path`; this function keeps that working.
    """
    filename = _clean_text(filename)
    if not filename:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    # If an absolute or relative path with directories is provided, preserve it.
    has_dir = os.path.dirname(filename) not in ("", ".")
    if has_dir:
        path = filename
    else:
        path = _sanitize_filename_component(filename)

    if folder:
        os.makedirs(folder, exist_ok=True)
        base = os.path.basename(path)
        path = os.path.join(folder, base)
    else:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    return path


def save_report_to_file(report: Any, filename: Optional[str] = None, folder: Optional[str] = None) -> str:
    path = _normalize_output_path(filename or "", folder=folder)
    try:
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(report, (dict, list)):
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                f.write(str(report))
        logger.info("Report saved to: %s", path)
        return path
    except Exception as e:
        logger.exception("Failed to save report to file: %s", e)
        raise


# Backward-compatible alias for callers expecting a slightly different helper name
save_text_report_to_file = save_report_to_file


def get_available_report_types() -> Dict[str, str]:
    return {
        "sales_performance": "Sales performance analysis by region/quarter",
        "marketing_campaign": "Marketing campaign performance analysis",
        "quarterly_summary": "Comprehensive quarterly summary",
        "product_analysis": "Product-specific performance analysis",
        "regional_analysis": "Regional sales and marketing analysis",
        "custom": "Custom analysis based on your query",
    }


# -------------------------
# CLI
# -------------------------

def _build_report(args) -> str:
    t = args.type
    analysis_focus = getattr(args, "analysis_focus", "") or ""

    if t == "sales_performance":
        return generate_sales_performance_report(region=args.region, quarter=args.quarter, analysis_focus=analysis_focus)
    if t == "marketing_campaign":
        return generate_marketing_campaign_report(channel=args.channel, quarter=args.quarter, analysis_focus=analysis_focus)
    if t == "quarterly_summary":
        if not args.quarter:
            raise ValueError("quarter is required for quarterly_summary")
        return generate_quarterly_summary_report(args.quarter, analysis_focus=analysis_focus)
    if t == "product_analysis":
        if not args.product:
            raise ValueError("product is required for product_analysis")
        return generate_product_analysis_report(args.product, analysis_focus=analysis_focus)
    if t == "regional_analysis":
        if not args.region:
            raise ValueError("region is required for regional_analysis")
        return generate_regional_analysis_report(args.region, analysis_focus=analysis_focus)
    if t == "custom":
        if not args.query:
            raise ValueError("query is required for custom report")
        return generate_custom_analysis_report(args.query, analysis_focus=analysis_focus)
    raise ValueError(f"Unknown report type: {t}")


def _cli():
    p = argparse.ArgumentParser(description="Generate reports using agent + RAG")
    p.add_argument("--type", required=True, choices=list(get_available_report_types().keys()), help="Report type")
    p.add_argument("--region", help="Region (for sales/regional reports)")
    p.add_argument("--quarter", help="Quarter string (e.g. 'Q1 2024')")
    p.add_argument("--channel", help="Marketing channel (for marketing report)")
    p.add_argument("--product", help="Product name (for product analysis)")
    p.add_argument("--query", help="Custom query (for custom report)")
    p.add_argument("--analysis-focus", dest="analysis_focus", help="Optional analysis focus / instruction")
    p.add_argument("--out", help="Output filename (optional)")
    p.add_argument("--out-folder", help="Output folder (optional)")
    args = p.parse_args()

    try:
        report = _build_report(args)
        print("\n" + "=" * 80)
        print("REPORT OUTPUT:")
        print("=" * 80 + "\n")
        print(report)
        if args.out or args.out_folder:
            filename = args.out or f"report_{args.type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            saved_path = save_report_to_file(report, filename=filename, folder=args.out_folder)
            print(f"\nSaved report to: {saved_path}")
    except Exception as e:
        logger.exception("Report generation failed: %s", e)
        print("ERROR:", e)


if __name__ == "__main__":
    _cli()
