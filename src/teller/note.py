"""The one internal note Teller adds to a ticket (RFC §3). Built for a fast, trusted review."""

from __future__ import annotations

from datetime import datetime, timezone

from teller.knowledge_base import KnowledgeBase
from teller.models import Decision, Intake

# One short "why" per outcome (RFC §3). Every note leads with it.
SKIP_TEXT = {
    "ineligible:has_attachments": "it has an attachment Teller can't read. Check the attachment before replying.",
    "ineligible:unverified_member": "the member isn't verified (not logged in).",
    "ineligible:not_created_by_member": "it was created by an agent, not the member.",
    "ineligible:not_english": "it isn't in English.",
}
FAILURE_TEXT = {
    "compliance_check_unavailable": "the compliance check was unavailable, and Teller never drafts without it",
    "classifier_unavailable": "the classifier was unavailable",
    "kb_unavailable": "the knowledge base was unavailable",
    "drafter_unavailable": "the drafting model was unavailable",
}


def why(decision: Decision, category_label: str, stage: str) -> str:
    d, r = decision, set(decision.reasons)
    signals = ", ".join(s for s in d.compliance_signals if not s.startswith("check:unavailable"))
    if not d.eligible:
        skips = [SKIP_TEXT[x] for x in d.reasons if x in SKIP_TEXT]
        return "Teller skipped this ticket: " + " Also, ".join(skips)
    for reason, text in FAILURE_TEXT.items():
        if reason in r:
            return f"Teller couldn't finish: {text}. No draft. Handle as usual."
    if "gate_rejected" in r:
        rules = ", ".join(x.split(":", 1)[1] for x in d.reasons if x.startswith("gate:"))
        return f"Teller's draft failed a safety check ({rules}), so there's no draft."
    if "compliance_gray" in r:
        return f"POSSIBLE COMPLIANCE CONCERN ({signals}). No draft. Review carefully."
    if "below_threshold" in r:
        return (f"Teller isn't confident about the category (best guess {d.category}, "
                f"{d.confidence:.2f}). No draft.")
    if "no_category" in r:
        return "This doesn't match any category Teller handles. No draft."
    if "no_kb_answer" in r:
        return "Routine question, but no knowledge base article answers it. No draft."
    verb = "Routed" if stage in ("act", "send") else "Suggest routing"
    if d.category == "compliance":
        return (f"Compliance concern ({signals}). {verb} to Compliance & Legal. "
                "No reply drafted. Either check alone is enough.")
    if d.action == "route_with_package":
        extra = ", with a thank-you draft for the member" if d.draft else ""
        label = category_label.replace("_", " ").capitalize()
        return f"{label}: {verb.lower()} to {d.destination} with a summary{extra}."
    if d.action == "draft_response":
        return (f"Routine question, answered from knowledge base article {', '.join(d.sources)} "
                f"(confidence {d.confidence_tier}).")
    return "Teller reviewed this ticket and took no action."


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
        f"WHY: {why(decision, category_label, stage)}",
        "",
        f"Based on the member's message(s) as of {intake.ticket_version}. If the member has",
        "written since, this may be out of date.",
        "",
    ]
    if decision.draft:
        lines += ["DRAFT REPLY (review before sending)", _indent(decision.draft), ""]
    if decision.package:
        lines += ["CONTEXT FOR THE RECEIVING TEAM"]
        lines += [f"  {k}: {v}" for k, v in decision.package.items()] + [""]

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
