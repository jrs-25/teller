"""The one internal note Teller adds to a ticket (RFC §3). Built for a fast, trusted review."""

from __future__ import annotations

from datetime import datetime, timezone

from teller.knowledge_base import KnowledgeBase
from teller.models import Decision, Intake

REASON_TEXT = {
    "below_threshold": "Teller isn't confident about this one.",
    "no_category": "This doesn't match any category Teller handles.",
    "compliance_gray": "POSSIBLE COMPLIANCE CONCERN. No draft; please review carefully.",
    "no_kb_answer": "No knowledge base article answers this, so there's no draft.",
    "gate_rejected": "Teller's draft failed a safety check, so there's no draft.",
}


def render_note(
    decision: Decision,
    intake: Intake,
    stage: str,
    category_label: str,
    found_sensitive_data: bool,
    article_dates: dict[str, datetime],
    stale_after_days: int,
) -> str:
    tier = decision.confidence_tier or "n/a"
    lines = [
        f"🤖 Teller · {stage} · {category_label} · Confidence: {tier}        decision {decision.decision_id}",
        f"Based on the member's message(s) as of {intake.ticket_version}. If the member has",
        "written since, this may be out of date.",
        "",
    ]
    if decision.draft:
        lines += ["DRAFT REPLY (review before sending)", _indent(decision.draft), ""]
    if decision.destination:
        verb = "Routed to" if stage in ("act", "send") else "Suggest routing to"
        lines += [f"{verb}: {decision.destination}", ""]
    if decision.package:
        lines += ["CONTEXT FOR THE RECEIVING TEAM"]
        lines += [f"  {k}: {v}" for k, v in decision.package.items()] + [""]

    why = [REASON_TEXT[r] for r in decision.reasons if r in REASON_TEXT]
    lines += ["WHY", f"  Category: {category_label}."]
    if decision.compliance_zone in ("clear", "gray"):
        lines.append(f"  Compliance signals: {', '.join(decision.compliance_signals)}.")
        lines.append("  (Either check alone is enough. A keyword match routes here even if the check scores low.)")
    lines += [f"  {w}" for w in why] + [""]

    if decision.sources:
        lines += ["SOURCES USED"]
        lines += [f"  • KB {s} (updated {article_dates[s]:%Y-%m-%d})" for s in decision.sources]
        lines += [""]

    checks = []
    if found_sensitive_data and decision.draft:
        checks.append("The member included sensitive details. The draft doesn't repeat them.")
    now = datetime.now(timezone.utc)
    for s in decision.sources:
        age = (now - article_dates[s]).days
        if age > stale_after_days:
            checks.append(f"KB {s} is {age} days old. Confirm it's still accurate.")
    if checks:
        lines += ["CHECK BEFORE SENDING"] + [f"  • {c}" for c in checks] + [""]

    lines.append('Wrong? Use macro "Teller: flag decision".')
    return "\n".join(lines)


def article_dates(kb: KnowledgeBase, decision: Decision) -> dict:
    articles = getattr(kb, "articles", [])
    return {a.article_id: a.updated_at for a in articles if a.article_id in decision.sources}


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines())
