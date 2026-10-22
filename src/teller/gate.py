"""The safety gate (RFC §2). Runs on every decision and does not trust the handler.

Any violation strips the draft and package and escalates to a human. An error
inside the gate itself is treated as a rejection (fail closed).
"""

from __future__ import annotations

from teller.handlers import _escalate
from teller.models import CategoryPolicy, Decision
from teller.redaction import contains_token


def violations(decision: Decision, policy: CategoryPolicy | None) -> list[str]:
    found = []
    if decision.draft is not None:
        if policy is None or not policy.member_response_allowed:
            found.append("draft_where_no_reply_allowed")
        if decision.compliance_zone in ("clear", "gray", "unknown"):
            found.append("draft_for_compliance_zone")
        if contains_token(decision.draft):
            found.append("token_in_draft")
        if decision.action == "draft_response" and not decision.sources:
            found.append("draft_without_sources")
    if decision.package is not None:
        allowed = set(policy.package_fields) if policy else set()
        if not set(decision.package) <= allowed:
            found.append("package_field_not_allowlisted")
    return found


def enforce(decision: Decision, policy: CategoryPolicy | None) -> Decision:
    try:
        found = violations(decision, policy)
    except Exception:
        found = ["gate_error"]
    if found:
        _escalate(decision, "gate_rejected")
        decision.reasons.extend(f"gate:{v}" for v in found)
    return decision
