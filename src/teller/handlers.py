"""The fixed set of action handlers (RFC §1). Config picks one; it never adds code.

Handlers only see redacted text. They fill in the draft, package, destination,
and sources on a Decision; the safety gate checks the result afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from teller.config import TellerConfig
from teller.drafting import Drafter
from teller.errors import DependencyError
from teller.knowledge_base import KnowledgeBase
from teller.models import CategoryPolicy, Decision


@dataclass
class HandlerContext:
    redacted_subject: str
    redacted_body: str
    policy: CategoryPolicy
    decision: Decision
    config: TellerConfig
    knowledge_base: KnowledgeBase
    drafter: Drafter

    @property
    def redacted_text(self) -> str:
        return f"{self.redacted_subject}\n{self.redacted_body}"


# Each package field is built from redacted data only. config.SAFE_PACKAGE_FIELDS
# must match these keys; the safety floor rejects any other field name.
PACKAGE_BUILDERS = {
    "category": lambda ctx: ctx.policy.id,
    "summary": lambda ctx: ctx.redacted_body[:280],
    "compliance_signals": lambda ctx: list(ctx.decision.compliance_signals),
    "intake_ref": lambda ctx: ctx.decision.ticket_id,
}


def build_package(ctx: HandlerContext) -> dict:
    """Built field by field from the allowlist, never by stripping fields out."""
    return {field: PACKAGE_BUILDERS[field](ctx) for field in ctx.policy.package_fields}


def draft_response(ctx: HandlerContext) -> None:
    d = ctx.decision
    try:
        results = ctx.knowledge_base.search(ctx.redacted_text)
    except DependencyError:
        _escalate(d, "kb_unavailable")
        return
    min_relevance = ctx.config.settings.knowledge_base.min_relevance
    articles = [a for a in results if a.relevance >= min_relevance]
    if not articles:
        _escalate(d, "no_kb_answer")  # no article, no draft
        return
    try:
        d.draft = ctx.drafter.answer(ctx.redacted_text, articles[:3])
    except DependencyError:
        _escalate(d, "drafter_unavailable")
        return
    d.sources = [a.article_id for a in articles[:3]]
    d.action = "draft_response"


def route_with_package(ctx: HandlerContext) -> None:
    d = ctx.decision
    d.action = "route_with_package"
    d.destination = ctx.policy.destination
    d.package = build_package(ctx)
    if ctx.policy.member_response_allowed:
        try:
            d.draft = ctx.drafter.thank_you(ctx.redacted_text)
        except DependencyError:
            d.reasons.append("thank_you_skipped:drafter_unavailable")


def escalate(ctx: HandlerContext) -> None:
    _escalate(ctx.decision, "category_policy:escalate")


def _escalate(decision: Decision, reason: str) -> None:
    decision.action = "escalate"
    decision.draft = None
    decision.package = None
    decision.destination = None
    decision.sources = []
    decision.reasons.append(reason)


HANDLERS = {
    "draft_response": draft_response,
    "route_with_package": route_with_package,
    "escalate": escalate,
}
