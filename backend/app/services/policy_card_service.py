"""Policy card service — builds structured policy matching result cards.

Assembles knowledge search results + LLM judgment into the policy_card SSE event format.
"""

from typing import Any


def build_policy_card(
    search_results: dict,
    llm_judgment: dict | None = None,
) -> dict:
    """Build a policy_card event payload.

    Args:
        search_results: Output from search_knowledge tool
        llm_judgment: Optional LLM judgment with verdict + breakdown (from agent's synthesis)

    Returns:
        Dict matching the policy_card SSE event format
    """
    # Extract snippets from search results
    policy_refs: list[dict] = []
    for r in (search_results.get("results") or [])[:5]:
        policy_refs.append({
            "source": r.get("filename", "未知文档"),
            "snippet": r.get("snippet", ""),
            "kb_name": r.get("kb_name", "未知知识库"),
            "score": r.get("score", 0),
        })

    # Default judgment when LLM hasn't provided one yet
    judgment = llm_judgment or {}

    return {
        "type": "policy_card",
        "data": {
            "verdict": judgment.get("verdict", "in_scope"),
            "summary": judgment.get("summary", ""),
            "policy_refs": policy_refs,
            "breakdown": judgment.get("breakdown"),
            "total_results": search_results.get("total_results", 0),
        },
    }


def build_policy_card_out_of_scope(
    search_results: dict,
    reason: str,
    invoice_fields: dict | None = None,
) -> dict:
    """Build a policy_card for out-of-scope invoices.

    Args:
        search_results: Output from search_knowledge tool
        reason: Why the invoice is out of scope
        invoice_fields: Current invoice field values (for correction context)

    Returns:
        Dict matching the policy_card SSE event format (verdict: out_of_scope)
    """
    card = build_policy_card(search_results)
    card["data"]["verdict"] = "out_of_scope"
    card["data"]["summary"] = f"该用途不在公司报销范围内。{reason}"
    card["data"]["invoice_fields"] = invoice_fields
    return card
