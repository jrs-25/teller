"""One pipeline for every ticket (RFC §1).

fetch → eligibility → redact → compliance checks → classify → RESOLVE POLICY (the seam)
→ action handler → safety gate → one conditional ticket update → decision record

Everything here is shared code. Per-category behavior comes only from config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from teller import gate
from teller.classifier import Classifier
from teller.compliance import ComplianceCheck, assess
from teller.config import COMPLIANCE, TellerConfig
from teller.drafting import Drafter
from teller.errors import DependencyError, LockedOperation, VersionConflict
from teller.handlers import HANDLERS, HandlerContext, _escalate
from teller.knowledge_base import KnowledgeBase
from teller.models import CategoryPolicy, Decision, Intake, TicketUpdate
from teller.note import article_dates, render_note
from teller.redaction import redact
from teller.telemetry import log_event
from teller.ticketing import PROCESSED_TAG, TicketingAdapter

# Escalations where a note helps the CSR. Dependency failures write nothing (RFC §4).
NOTE_WORTHY = {"below_threshold", "no_category", "compliance_gray", "no_kb_answer", "gate_rejected"}


@dataclass
class Teller:
    config: TellerConfig
    ticketing: TicketingAdapter
    knowledge_base: KnowledgeBase
    classifier: Classifier
    compliance_check: ComplianceCheck
    drafter: Drafter
    decisions: list[Decision] = field(default_factory=list)  # the decision record store

    def process(self, ticket_id: str) -> Decision:
        attempts = self.config.settings.max_write_attempts
        for attempt in range(1, attempts + 1):
            try:
                intake = self.ticketing.get_ticket(ticket_id)
            except DependencyError:
                return self._record(Decision(ticket_id=ticket_id, ticket_version="unknown",
                                             reasons=["ticketing_read_unavailable"]))

            decision, update = self._decide(intake)
            if update is None:
                return self._record(decision)
            try:
                self.ticketing.apply_update(update)
            except VersionConflict:
                log_event("version_conflict", ticket_id=ticket_id, attempt=attempt)
                continue  # the ticket changed since we read it: read again, decide again
            except DependencyError:
                decision.reasons.append("ticketing_write_unavailable")
                return self._record(decision)
            self._maybe_send(decision)
            return self._record(decision)

        return self._record(Decision(ticket_id=ticket_id, ticket_version="unknown",
                                     reasons=["version_conflict_gave_up"]))

    # -- deciding ---------------------------------------------------------------

    def _decide(self, intake: Intake) -> tuple[Decision, TicketUpdate | None]:
        d = Decision(
            ticket_id=intake.ticket_id,
            ticket_version=intake.ticket_version,
            config_version=self.config.version,
            model_version=f"{self.classifier.version}/{self.compliance_check.version}/{self.drafter.version}",
        )
        if PROCESSED_TAG in intake.tags:
            d.reasons.append("already_processed")
            return d, None

        ineligible = self._eligibility(intake)
        if ineligible:
            d.eligible = False
            d.reasons += ineligible
            return d, None

        # Redaction first: nothing below this line sees raw text.
        subject, body = redact(intake.subject), redact(intake.body)
        text = f"{subject.text}\n{body.text}"

        d.compliance_zone, d.compliance_signals = assess(
            text, self.config.compliance_keywords, self.compliance_check,
            self.config.settings.compliance_check,
        )
        if d.compliance_zone == "unknown":
            _escalate(d, "compliance_check_unavailable")  # fail closed, write nothing
            return d, None

        try:
            scores = self.classifier.scores(text, self.config.categories)
        except DependencyError:
            scores = {}
            if d.compliance_zone != "clear":
                _escalate(d, "classifier_unavailable")
                return d, None

        policy = self._resolve_policy(d, scores)
        if policy is not None and d.action == "none":
            ctx = HandlerContext(subject.text, body.text, policy, d, self.config,
                                 self.knowledge_base, self.drafter)
            HANDLERS[policy.action](ctx)

        gate.enforce(d, policy)
        d.rollout_stage = policy.rollout_stage if policy else self.config.settings.uncategorized_stage
        found_sensitive = subject.found_sensitive_data or body.found_sensitive_data
        return d, self._build_update(d, intake, policy, found_sensitive)

    def _eligibility(self, intake: Intake) -> list[str]:
        reasons = []
        if intake.member.auth_level != "verified":
            reasons.append("ineligible:unverified_member")
        if not intake.created_by_member:
            reasons.append("ineligible:not_created_by_member")
        if not intake.language.lower().startswith("en"):
            reasons.append("ineligible:not_english")
        if intake.has_attachments:
            reasons.append("ineligible:has_attachments")
        return reasons

    def _resolve_policy(self, d: Decision, scores: dict[str, float]) -> CategoryPolicy | None:
        """THE SEAM: from "what is this?" to "what do we do?". Precedence, thresholds,
        and the compliance override are applied here; the model never picks the action."""
        cats = self.config.categories

        if d.compliance_zone == "clear":
            d.category = COMPLIANCE
            d.confidence = max(scores.get(COMPLIANCE, 0.0), 0.9)
            d.confidence_tier = "HIGH"
            return cats[COMPLIANCE]

        above = [cats[c] for c, s in scores.items() if c in cats and s >= cats[c].confidence_threshold]
        best_guess = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else None

        if d.compliance_zone == "gray":
            d.category = best_guess
            _escalate(d, "compliance_gray")
            return cats.get(best_guess) if best_guess else None

        if not above:
            d.category = best_guess
            if best_guess:
                d.confidence = scores[best_guess]
                d.confidence_tier = _tier(d.confidence)
            _escalate(d, "below_threshold" if best_guess else "no_category")
            return cats.get(best_guess) if best_guess else None

        policy = max(above, key=lambda p: p.precedence)
        d.category = policy.id
        d.confidence = scores[policy.id]
        d.confidence_tier = _tier(d.confidence)
        return policy

    # -- writing ----------------------------------------------------------------

    def _build_update(self, d: Decision, intake: Intake, policy: CategoryPolicy | None,
                      found_sensitive: bool) -> TicketUpdate | None:
        stage = d.rollout_stage
        if stage == "off":
            d.reasons.append("stage:off")
            return None
        if d.action == "escalate" and not (NOTE_WORTHY & set(d.reasons)):
            return None  # a dependency failed: write nothing, the ticket stays manual
        if stage == "shadow":
            return TicketUpdate(ticket_id=d.ticket_id, if_version=d.ticket_version,
                                add_tags=[PROCESSED_TAG])

        label = policy.id if policy else "uncategorized"
        note = render_note(d, intake, stage, label, found_sensitive,
                           article_dates(self.knowledge_base, d),
                           self.config.settings.knowledge_base.stale_after_days)
        move = d.destination if stage in ("act", "send") and d.action == "route_with_package" else None
        return TicketUpdate(ticket_id=d.ticket_id, if_version=d.ticket_version,
                            internal_note=note, add_tags=[PROCESSED_TAG], move_to=move)

    def _maybe_send(self, d: Decision) -> None:
        if d.rollout_stage != "send" or not d.draft:
            return
        try:
            self.ticketing.send_public_reply(d.ticket_id, d.draft, d.category, self.config)
            d.requires_human_approval = False
        except LockedOperation as locked:
            d.reasons.append(f"send_locked:{str(locked).split(':')[0]}")

    def _record(self, d: Decision) -> Decision:
        self.decisions.append(d)
        log_event("decision", ticket_id=d.ticket_id, decision_id=d.decision_id,
                  category=d.category, action=d.action, confidence=d.confidence,
                  zone=d.compliance_zone, stage=d.rollout_stage, reasons=d.reasons)
        return d


def _tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "HIGH"
    if confidence >= 0.6:
        return "MEDIUM"
    return "LOW"
