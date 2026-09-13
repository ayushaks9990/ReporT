from __future__ import annotations
from typing import Optional, Any
import os
import time
import traceback # error Then The debuggings
import json
import asyncio

# Load env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# HTTP client
try:
    import requests
    from requests.exceptions import RequestException, Timeout as RequestsTimeout
except Exception:
    requests = None
    RequestException = RequestsTimeout = Exception

# RAG retrieval (your module)
try:
    from rag_retrieval import retrieve_combined_data, retrieve_sales_data, retrieve_marketing_data
except Exception:
    # placeholder fallbacks in case import fails at runtime
    def retrieve_combined_data(q, n_results=5):
        return f"[RAG missing] {q}"

    def retrieve_sales_data(q, n_results=5):
        return f"[RAG missing] {q}"

    def retrieve_marketing_data(q, n_results=5):
        return f"[RAG missing] {q}"

# Config
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or None
# You can keep using the full chat/completions URL, but we also derive base_url for AutoGen.
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    os.getenv("MODEL_NAME", "llama-3.3-70b-versatile"),
).strip()

TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
RETRY_COUNT = int(os.getenv("OPENAI_RETRY_COUNT", "3"))
RETRY_BACKOFF = float(os.getenv("OPENAI_RETRY_BACKOFF", "2.0"))

# fallback models list (optional override via GROQ_FALLBACK_MODELS)
fallback_env = os.getenv("GROQ_FALLBACK_MODELS", "")
if fallback_env.strip():
    GROQ_FALLBACK_MODELS = [m.strip() for m in fallback_env.split(",") if m.strip()]
else:
    GROQ_FALLBACK_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "groq/compound",
        "groq/compound-mini",
    ]

# AutoGen detection (new AgentChat API)
AUTOGEN_AVAILABLE = False
AssistantAgent = None
OpenAIChatCompletionClient = None
try:
    from autogen_agentchat.agents import AssistantAgent  # type: ignore
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # type: ignore
    AUTOGEN_AVAILABLE = True
    print("[agent] AutoGen import succeeded")
except Exception:
    print("[agent] AutoGen not importable; will use GROQ fallback if configured")


# -------------------------
# Helpers
# -------------------------
def _truncate_context(context: str, max_chars: int = 14000) -> str:
    if not context:
        return context
    if len(context) <= max_chars:
        return context
    head = context[: max_chars // 2]
    tail = context[-(max_chars // 2) :]
    return head + "\n\n[...context truncated...]\n\n" + tail


def _build_query_with_focus(query: str, analysis_focus: Optional[str] = None) -> str:
    """Build a retrieval query that includes the user's focus if present."""
    query = (query or "").strip()
    analysis_focus = (analysis_focus or "").strip()
    if not analysis_focus:
        return query
    return f"""{query}

User analysis focus:
{analysis_focus}"""


def _build_analysis_prompt(query: str, context: str, analysis_focus: Optional[str] = None) -> str:
    analysis_focus = (analysis_focus or "").strip()
    focus_block = f"\n\nUser focus / special instruction:\n{analysis_focus}\n" if analysis_focus else ""
    return f"""Based on the following verified data context, analyze and identify key insights.

Query: {query}{focus_block}
VERIFIED DATA CONTEXT:
{context}

Rules:
- Use only numbers present in the verified data context.
- Do not say information is unavailable when the context contains dataset summaries.
- If a coverage notice is present, state its limitation explicitly.

Please provide:
1. Key metrics and numbers
2. Notable trends
3. Top performers
4. Areas of concern
5. Data-driven insights"""


def _build_report_prompt(query: str, analyst_findings: str, analysis_focus: Optional[str] = None) -> str:
    analysis_focus = (analysis_focus or "").strip()
    focus_block = f"\n\nUser focus / special instruction:\n{analysis_focus}\n" if analysis_focus else ""
    return f"""Based on the data analyst's findings below, create a comprehensive professional report.

Original Query: {query}{focus_block}
Data Analyst's Findings:
{analyst_findings}

Create a detailed report with these sections:
1. Executive Summary
2. Key Findings
3. Detailed Analysis
4. Insights and Trends
5. Recommendations

Use only metrics in the analyst findings; do not invent values or claim that data is missing when findings contain metrics.
Make it professional, clear, and actionable."""


def _build_deterministic_report(query: str, context: str) -> str:
    """Return a useful data-grounded report when the external LLM is unavailable."""
    return f"""# Sales & Marketing Performance Report

## Executive Summary

This report answers: **{query}**. The figures below were calculated directly from the bundled sales and marketing JSON datasets. External AI wording was unavailable, so the verified dataset summary is provided without invented claims.

## Key Findings and Detailed Analysis

{context}

## Recommendations

1. Prioritize the products, regions, campaigns, and channels with the strongest verified totals above.
2. Investigate lower-performing segments with the same filters before reallocating budget.
3. Compare like-for-like quarters and track revenue, conversion rate, and cost per conversion over time.
""".strip()


def _build_critic_prompt(query: str, analyst_findings: str, draft_report: str, analysis_focus: Optional[str] = None) -> str:
    analysis_focus = (analysis_focus or "").strip()
    focus_block = f"\n\nUser focus / special instruction:\n{analysis_focus}\n" if analysis_focus else ""
    return f"""You are a strict but helpful senior critic for business reports.

Task:
Review the report for factual consistency with the analyst findings, missing insights, unsupported claims, clarity, professionalism, and actionable recommendations.

Original Query: {query}{focus_block}

Analyst Findings:
{analyst_findings}

Draft Report:
{draft_report}

Return your review in this exact format:

STATUS: APPROVED

or

STATUS: NEEDS_REVISION
ISSUES:
- ...
- ...
SUGGESTED_FIXES:
- ...
- ...

Be concise but specific."""


def _build_revision_prompt(query: str, analyst_findings: str, draft_report: str, critic_feedback: str, analysis_focus: Optional[str] = None) -> str:
    analysis_focus = (analysis_focus or "").strip()
    focus_block = f"\n\nUser focus / special instruction:\n{analysis_focus}\n" if analysis_focus else ""
    return f"""Revise the report using the critic feedback below.

Original Query: {query}{focus_block}

Analyst Findings:
{analyst_findings}

Draft Report:
{draft_report}

Critic Feedback:
{critic_feedback}

Rewrite the report to fix the issues while keeping it professional, clear, and actionable.
Return only the revised report."""


def _build_analyst_revision_prompt(
    query: str,
    context: str,
    analyst_findings: str,
    critic_feedback: str,
    analysis_focus: Optional[str] = None
) -> str:
    analysis_focus = (analysis_focus or "").strip()
    focus_block = f"\n\nUser focus / special instruction:\n{analysis_focus}\n" if analysis_focus else ""

    return f"""You are a senior data analyst.

The critic reviewed your previous analysis and found issues. Revise your analysis findings directly.

Original Query: {query}{focus_block}

Retrieved Context:
{context}

Your Previous Analyst Findings:
{analyst_findings}

Critic Feedback:
{critic_feedback}

Instructions:
- Fix factual gaps, weak reasoning, missing trends, or unsupported claims
- Stay grounded only in the retrieved context
- Keep the analysis clear, precise, and data-driven
- Return only the revised analyst findings
"""


def _parse_status(text: str) -> str:
    upper = (text or "").upper()
    if "STATUS: APPROVED" in upper or upper.strip() == "APPROVED":
        return "APPROVED"
    if "STATUS: NEEDS_REVISION" in upper or "NEEDS_REVISION" in upper:
        return "NEEDS_REVISION"
    return "UNKNOWN"


def _extract_result_text(result: Any) -> str:
    """Best-effort extraction from AutoGen TaskResult / message list."""
    try:
        messages = getattr(result, "messages", None)
        if messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if content is not None:
                return str(content).strip()
            if isinstance(last, dict):
                return str(last.get("content", "")).strip()
    except Exception:
        pass

    for attr in ("content", "text", "output"):
        try:
            value = getattr(result, attr, None)
            if value:
                return str(value).strip()
        except Exception:
            pass

    if isinstance(result, str):
        return result.strip()

    try:
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return str(result)


def _groq_models_list():
    """Attempt to GET /openai/v1/models from Groq (helpful when model selection fails)."""
    if requests is None:
        return None, "requests not installed", None
    parsed_url = GROQ_API_URL
    base = None
    try:
        from urllib.parse import urlparse, urljoin

        p = urlparse(parsed_url)
        base = f"{p.scheme}://{p.netloc}"
        models_url = urljoin(base, "/openai/v1/models")
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
        r = requests.get(models_url, headers=headers, timeout=20)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.status_code, body, models_url
    except Exception as e:
        return None, str(e), base

# Make Groq work with AutoGen's OpenAIChatCompletionClient, because that client expects a base URL (https://api.groq.com/openai/v1) rather than the full chat completions endpoint.
def _groq_base_url() -> str:
    """
    Derive the OpenAI-compatible base_url for AutoGen from GROQ_API_URL.
    Example:
      https://api.groq.com/openai/v1/chat/completions -> https://api.groq.com/openai/v1
    """
    api_url = (os.getenv("GROQ_API_URL", GROQ_API_URL) or "").strip()
    if not api_url:
        return "https://api.groq.com/openai/v1"
    from urllib.parse import urlparse
    p = urlparse(api_url)
    if p.scheme and p.netloc:
        base = f"{p.scheme}://{p.netloc}"
        if "/openai/v1" in p.path:
            return base + "/openai/v1"
        return api_url.rsplit("/chat/completions", 1)[0].rstrip("/")
    return "https://api.groq.com/openai/v1"

# Is responsible for creating and configuring an AutoGen model client that communicates with the Groq API.
# It acts as a bridge between your AutoGen agents and Groq's OpenAI-compatible API.
def _make_autogen_client(model: str):
    """
    Create an AutoGen OpenAI-compatible model client for Groq.
    This uses the current AgentChat API: AssistantAgent(..., model_client=client) and agent.run(task=...).
    """
    if not AUTOGEN_AVAILABLE:
        raise RuntimeError("AutoGen not available")

    base_url = _groq_base_url()
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")

    # OpenAI-compatible endpoints typically work with model_info/model_capabilities.
    # We try the most compatible shapes first.
    client_kwargs_variants = [
        {
            "model": model,
            "api_key": api_key or "placeholder",
            "base_url": base_url,
            "model_info": {
                "vision": False,
                "function_calling": False,
                "json_output": False,
                "family": "unknown",
                "structured_output": False,
            },
        },
        {
            "model": model,
            "api_key": api_key or "placeholder",
            "base_url": base_url,
            "model_capabilities": {
                "vision": False,
                "function_calling": False,
                "json_output": False,
            },
        },
        {
            "model": model,
            "api_key": api_key or "placeholder",
            "base_url": base_url,
        },
    ]

    last_exc = None
    for kwargs in client_kwargs_variants:
        try:
            return OpenAIChatCompletionClient(**kwargs)
        except Exception as e:
            last_exc = e
            continue

    raise last_exc or RuntimeError("Failed to create AutoGen model client")


async def _run_autogen_agent(agent, task: str) -> str:
    result = await agent.run(task=task)
    return _extract_result_text(result)


async def _autogen_multiagent_pipeline(
    query: str,
    report_type: str = "combined",
    n_results: int = 8,
    analysis_focus: str = "",
) -> str:
    """
    AutoGen-based pipeline using AssistantAgent.run() (current AgentChat API).
    Sequence:
      Retriever -> Analyst -> Writer -> Critic -> Analyst Revision -> Writer -> Critic
    """
    retrieval_query = _build_query_with_focus(query, analysis_focus)

    if report_type == "sales":
        context = retrieve_sales_data(retrieval_query, n_results=n_results)
    elif report_type == "marketing":
        context = retrieve_marketing_data(retrieval_query, n_results=n_results)
    else:
        context = retrieve_combined_data(retrieval_query, n_results=n_results)

    context = _truncate_context(context, max_chars=14000)

    model_candidates = [MODEL_NAME] if MODEL_NAME else []
    model_candidates += [m for m in GROQ_FALLBACK_MODELS if m not in model_candidates]
    if not model_candidates:
        model_candidates = ["llama-3.3-70b-versatile"]

    last_exc = None
    for candidate in model_candidates:
        model_client = None
        try:
            model_client = _make_autogen_client(candidate)

            analyst = AssistantAgent(
                name="data_analyst",
                model_client=model_client,
                system_message=(
                    "You are a Senior Data Analyst specializing in sales and marketing analytics. "
                    "Be precise, data-driven, and align your analysis to the user's focus."
                ),
            )
            writer = AssistantAgent(
                name="report_writer",
                model_client=model_client,
                system_message=(
                    "You are a Professional Report Writer specialized in business reporting. "
                    "Write clear, actionable executive-level reports."
                ),
            )
            critic = AssistantAgent(
                name="report_critic",
                model_client=model_client,
                system_message=(
                    "You are a strict but helpful senior critic for business reports. "
                    "Judge factual consistency, missing insights, unsupported claims, clarity, professionalism, and actionability."
                ),
            )

            # 1) Analyst creates initial findings
            analysis_prompt = _build_analysis_prompt(query, context, analysis_focus=analysis_focus)
            analyst_findings = await _run_autogen_agent(analyst, analysis_prompt)
            if not analyst_findings:
                raise RuntimeError("AutoGen analyst returned empty output")

            # 2) Writer creates initial report
            report_prompt = _build_report_prompt(query, analyst_findings, analysis_focus=analysis_focus)
            draft_report = await _run_autogen_agent(writer, report_prompt)
            if not draft_report:
                raise RuntimeError("AutoGen writer returned empty output")

            # 3) Critic reviews the report
            critic_prompt = _build_critic_prompt(query, analyst_findings, draft_report, analysis_focus=analysis_focus)
            critic_feedback = await _run_autogen_agent(critic, critic_prompt)
            if not critic_feedback:
                critic_feedback = "STATUS: UNKNOWN"

            status = _parse_status(critic_feedback)
            final_report = draft_report.strip()

            # 4) If critic rejects, send feedback back to analyst first
            if status != "APPROVED":
                analyst_revision_prompt = _build_analyst_revision_prompt(
                    query=query,
                    context=context,
                    analyst_findings=analyst_findings,
                    critic_feedback=critic_feedback,
                    analysis_focus=analysis_focus,
                )
                revised_analyst_findings = await _run_autogen_agent(analyst, analyst_revision_prompt)
                if revised_analyst_findings:
                    analyst_findings = revised_analyst_findings.strip()

                    # 5) Writer rebuilds report from revised analyst findings
                    report_prompt = _build_report_prompt(query, analyst_findings, analysis_focus=analysis_focus)
                    revised_report = await _run_autogen_agent(writer, report_prompt)
                    if revised_report:
                        final_report = revised_report.strip()

                    # 6) Critic checks again
                    critic_feedback = await _run_autogen_agent(
                        critic,
                        _build_critic_prompt(query, analyst_findings, final_report, analysis_focus=analysis_focus),
                    ) or critic_feedback

            bundle = (
                f"{final_report}\n\n"
                f"---\nCritic Review\n{critic_feedback.strip()}"
            )
            print("[ReportGen] AutoGen flow complete with critic review.")
            return bundle.strip()

        except Exception as e:
            last_exc = e
            print(f"[ReportGen] AutoGen candidate '{candidate}' failed: {e}")
            traceback.print_exc()
        finally:
            try:
                if model_client is not None and hasattr(model_client, "close"):
                    await model_client.close()
            except Exception:
                pass

    raise RuntimeError(f"AutoGen pipeline failed for all candidates. Last error: {last_exc}")


# -------------------------
# GROQ helper (OpenAI-compatible messages)
# -------------------------
def _groq_chat(prompt: str, system_message: Optional[str] = None, model: Optional[str] = MODEL_NAME) -> str:
    """
    Send an OpenAI-compatible `messages` payload to Groq.
    Automatically attempts fallback models if Groq returns model_decommissioned or model_not_found.
    """
    if requests is None:
        raise RuntimeError("requests package not installed. Install `requests` to use GROQ fallback.")
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    api_url = GROQ_API_URL or os.environ.get("GROQ_API_URL", "")
    if not api_key or not api_url:
        raise RuntimeError("GROQ_API_KEY or GROQ_API_URL not set. Put them in .env or config.py")

    if not model:
        status, body, url = _groq_models_list()
        raise RuntimeError(
            "No GROQ_MODEL configured. Set GROQ_MODEL in .env to a model you have access to.\n"
            f"Attempted models list endpoint returned status={status} body={json.dumps(body, indent=2) if isinstance(body,(dict,list)) else body}\n"
            f"Models endpoint tried: {url}"
        )

    safe_prompt = _truncate_context(prompt, max_chars=14000)
    safe_system = _truncate_context(system_message or "", max_chars=2000)
    messages = []
    if safe_system:
        messages.append({"role": "system", "content": safe_system})
    messages.append({"role": "user", "content": safe_prompt})

    # candidate models: requested model then fallback list
    candidates = [model] + [m for m in GROQ_FALLBACK_MODELS if m != model]

    last_exc = None
    for candidate in candidates:
        attempt = 0
        while attempt < RETRY_COUNT:
            attempt += 1
            payload = {
                "model": candidate,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
                if resp.status_code >= 400:
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text
                    # If model error suggests decommission or not found -> break to next candidate
                    code = None
                    if isinstance(body, dict):
                        err = body.get("error", {})
                        code = err.get("code") or err.get("type")
                    if code and ("model_decommissioned" in str(code) or "model_not_found" in str(code)):
                        print(f"[agent][_groq_chat] Groq rejected model '{candidate}': {body}")
                        break  # try next model candidate
                    raise RuntimeError(
                        f"GROQ API error: status={resp.status_code} body={json.dumps(body) if isinstance(body,(dict,list)) else body}"
                    )
                # parse success
                resp_json = resp.json()
                if isinstance(resp_json, dict) and "choices" in resp_json and isinstance(resp_json["choices"], list) and resp_json["choices"]:
                    choice = resp_json["choices"][0]
                    if isinstance(choice, dict) and "message" in choice and isinstance(choice["message"], dict):
                        return str(choice["message"].get("content", "")).strip()
                    if isinstance(choice, dict) and "text" in choice:
                        return str(choice.get("text", "")).strip()
                # alternate shapes
                if isinstance(resp_json, dict) and "outputs" in resp_json and isinstance(resp_json["outputs"], list) and resp_json["outputs"]:
                    out0 = resp_json["outputs"][0]
                    if isinstance(out0, dict):
                        for k in ("content", "text", "output"):
                            if k in out0:
                                return str(out0[k]).strip()
                return json.dumps(resp_json, indent=2)
            except (RequestsTimeout, RequestException) as e:
                last_exc = e
                print(f"[agent][_groq_chat] Attempt {attempt} transient error for model {candidate}: {e}")
                if attempt >= RETRY_COUNT:
                    break
                time.sleep(RETRY_BACKOFF ** (attempt - 1))
                continue
            except Exception as e:
                last_exc = e
                print(f"[agent][_groq_chat] Attempt {attempt} error for model {candidate}: {e}")
                if attempt >= RETRY_COUNT:
                    break
                time.sleep(RETRY_BACKOFF ** (attempt - 1))
                continue
        # next candidate
        print(f"[agent][_groq_chat] Trying next model candidate after '{candidate}' (if any)")
    # exhausted candidates; return models list for helpful error
    status, body, url = _groq_models_list()
    raise RuntimeError(
        f"GROQ: all model candidates failed. Last exception: {last_exc}\n"
        f"Attempted models: {candidates}\n"
        f"Models endpoint returned status={status} body={json.dumps(body, indent=2) if isinstance(body,(dict,list)) else body}\n"
        f"Please set GROQ_MODEL to a model you have access to (update .env)."
    )


# -------------------------
# Main multi-agent flow
# -------------------------
def generate_report_with_autogen_multiagent(
    query: str,
    report_type: str = "combined",
    n_results: int = 8,
    analysis_focus: str = "",
) -> str:
    """
    Best-effort multi-agent report generation.

    Preferred path:
      AutoGen AgentChat AssistantAgent.run()  -> Analyst -> Writer -> Critic -> Analyst revision -> Writer -> Critic

    Fallback:
      Groq chat completions path with the same analyst/writer/critic stages
    """
    print("\n[ReportGen] Starting Multi-Agent Analysis...")

    query = (query or "").strip()
    if not query:
        raise ValueError("A report query is required.")

    # 1) Try current AutoGen AgentChat API first
    if AUTOGEN_AVAILABLE and (GROQ_API_KEY or os.environ.get("GROQ_API_KEY")):
        try:
            return asyncio.run(
                _autogen_multiagent_pipeline(
                    query=query,
                    report_type=report_type,
                    n_results=n_results,
                    analysis_focus=analysis_focus,
                )
            )
        except Exception as e:
            print(f"[ReportGen] AutoGen pipeline failed (falling back to GROQ): {e}")
            traceback.print_exc()

    # 2) GROQ fallback
    print("[ReportGen] Using GROQ fallback for analysis + report generation...")
    retrieval_query = _build_query_with_focus(query, analysis_focus)

    if report_type == "sales":
        context = retrieve_sales_data(retrieval_query, n_results=n_results)
    elif report_type == "marketing":
        context = retrieve_marketing_data(retrieval_query, n_results=n_results)
    else:
        context = retrieve_combined_data(retrieval_query, n_results=n_results)

    context = _truncate_context(context, max_chars=14000)

    if not (GROQ_API_KEY or os.environ.get("GROQ_API_KEY")):
        print("[ReportGen] GROQ_API_KEY is not configured; returning verified local-data report.")
        return _build_deterministic_report(query, context)

    try:
        analyst_system = "You are a Senior Data Analyst specializing in sales and marketing analytics. Be precise and analytical."
        analysis_prompt = _build_analysis_prompt(query, context, analysis_focus=analysis_focus)

        analyst_findings = _groq_chat(analysis_prompt, system_message=analyst_system, model=MODEL_NAME)
        if not analyst_findings:
            raise RuntimeError("GROQ returned empty analyst findings")

        writer_system = "You are a Professional Report Writer specialized in business reporting. Write clear, actionable executive-level reports."
        report_prompt = _build_report_prompt(query, analyst_findings, analysis_focus=analysis_focus)

        final_report = _groq_chat(report_prompt, system_message=writer_system, model=MODEL_NAME)
        if not final_report:
            raise RuntimeError("GROQ returned empty final report")

        critic_system = "You are a strict but helpful senior critic for business reports."
        critic_prompt = _build_critic_prompt(query, analyst_findings, final_report, analysis_focus=analysis_focus)
        critic_feedback = _groq_chat(critic_prompt, system_message=critic_system, model=MODEL_NAME)
        if not critic_feedback:
            critic_feedback = "STATUS: UNKNOWN"

        # critic -> analyst revision -> writer rebuild -> critic recheck
        if _parse_status(critic_feedback) != "APPROVED":
            analyst_revision_prompt = _build_analyst_revision_prompt(
                query=query,
                context=context,
                analyst_findings=analyst_findings,
                critic_feedback=critic_feedback,
                analysis_focus=analysis_focus,
            )
            revised_analyst_findings = _groq_chat(analyst_revision_prompt, system_message=analyst_system, model=MODEL_NAME)
            if revised_analyst_findings:
                analyst_findings = revised_analyst_findings.strip()

                report_prompt = _build_report_prompt(query, analyst_findings, analysis_focus=analysis_focus)
                revised_report = _groq_chat(report_prompt, system_message=writer_system, model=MODEL_NAME)
                if revised_report:
                    final_report = revised_report.strip()

                critic_feedback = _groq_chat(
                    _build_critic_prompt(query, analyst_findings, final_report, analysis_focus=analysis_focus),
                    system_message=critic_system,
                    model=MODEL_NAME,
                ) or critic_feedback

        print("[ReportGen] GROQ flow complete with critic review.")
        return f"{final_report}\n\n---\nCritic Review\n{critic_feedback.strip()}"
    except Exception as exc:
        print(f"[ReportGen] GROQ generation failed; returning verified local-data report: {exc}")
        return _build_deterministic_report(query, context)


# Backwards-compatible wrapper expected by older code
def generate_report_with_rag(
    query: str,
    report_type: str = "combined",
    n_results: int = 5,
    analysis_focus: str = "",
) -> str:
    return generate_report_with_autogen_multiagent(
        query,
        report_type=report_type,
        n_results=n_results,
        analysis_focus=analysis_focus,
    )


def generate_custom_report(prompt_with_context: str, analysis_focus: str = "") -> str:
    """Single-step custom prompt (analyst-like)."""
    prompt_with_context = (prompt_with_context or "").strip()
    analysis_focus = (analysis_focus or "").strip()

    if analysis_focus:
        prompt_with_context = f"""{prompt_with_context}

User focus / special instruction:
{analysis_focus}"""

    # Prefer AutoGen if available; otherwise fall back to Groq.
    if AUTOGEN_AVAILABLE:
        try:
            async def _run() -> str:
                client = _make_autogen_client(MODEL_NAME or GROQ_FALLBACK_MODELS[0])
                try:
                    analyst = AssistantAgent(
                        name="data_analyst",
                        model_client=client,
                        system_message="You are a data analyst. Be precise and base your analysis on the context.",
                    )
                    return await _run_autogen_agent(analyst, prompt_with_context)
                finally:
                    try:
                        if hasattr(client, "close"):
                            await client.close()
                    except Exception:
                        pass

            return asyncio.run(_run())
        except Exception:
            pass

    return _groq_chat(
        prompt_with_context,
        system_message="You are a data analyst. Be precise and base your analysis on the context.",
        model=MODEL_NAME,
    )


# Quick test when run directly
if __name__ == "__main__":
    q = "Analyze the top performing products and their sales trends"
    try:
        print(generate_report_with_rag(q, report_type="sales", n_results=5, analysis_focus="Focus on enterprise customers."))
    except Exception as e:
        print("Error:", e)
