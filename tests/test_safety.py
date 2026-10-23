"""The CI safety test (RFC §2, rules S1-S17 in RFC §5).

Every breach fails the build automatically. Each assertion names the rule it guards.
"""

import json
import logging

import pytest
from conftest import FIXTURES, by_id, with_stage

from teller import build_mock_teller
from teller.errors import LockedOperation
from teller.telemetry import log_event
from teller.ticketing import ALLOWED_WRITES, TicketingAdapter

# Fake sensitive values planted in the fixtures. They must never appear in any output.
CANARIES = ["4417-2290-1183", "441722901183", "078-05-1120", "4111 1111 1111 1111", "4111111111111111"]

COMPLIANCE_FIXTURES = ["compliance_explicit", "compliance_disguised", "compliance_gray"]


class MisbehavingClassifier:
    """A broken model: calls everything a routine question, with total confidence."""

    version = "misbehaving-0"

    def scores(self, redacted_text, categories):
        return {cid: (0.99 if cid == "general_qa" else 0.0) for cid in categories}


class TokenLeakingDrafter:
    """A broken drafter that repeats the member's (redacted) account number."""

    version = "leaky-0"

    def answer(self, redacted_text, articles):
        return f"Hi, about your account [ACCOUNT_NUMBER_1]: {articles[0].text}"

    def thank_you(self, redacted_text):
        return "Thanks!"


def run_all(teller):
    return {name: teller.process(str(raw["ticket"]["id"])) for name, raw in FIXTURES.items()}


# -- S1-S4, S6: compliance never gets a draft ------------------------------------

@pytest.mark.parametrize("name", COMPLIANCE_FIXTURES)
def test_s1_no_draft_for_compliance_or_gray_even_with_a_broken_classifier(teller, name):
    teller.classifier = MisbehavingClassifier()
    d = teller.process(by_id(name))
    assert d.draft is None, "S1: compliance or gray-zone decision carried a member-facing draft"
    assert d.compliance_zone in ("clear", "gray")


def test_s1_gate_catches_a_handler_that_drafts_for_compliance(teller, monkeypatch):
    from teller import pipeline

    def buggy_route(ctx):  # a code bug: drafts for every routed category
        ctx.decision.action = "route_with_package"
        ctx.decision.destination = ctx.policy.destination
        ctx.decision.draft = "We're sorry. Here's what happened..."

    monkeypatch.setitem(pipeline.HANDLERS, "route_with_package", buggy_route)
    d = teller.process(by_id("compliance_explicit"))
    assert d.draft is None, "S1: the safety gate let a compliance draft through"
    assert "gate:draft_where_no_reply_allowed" in d.reasons


def test_s2_keyword_match_is_always_compliance(teller):
    teller.classifier = MisbehavingClassifier()
    d = teller.process(by_id("compliance_explicit"))
    assert d.category == "compliance", "S2: keyword tripwire was overridden by the classifier"
    assert "keyword:cfpb" in d.compliance_signals


def test_s3_disguised_complaint_is_caught_by_the_compliance_check(teller):
    d = teller.process(by_id("compliance_disguised"))
    assert d.category == "compliance", "S3: disguised compliance complaint was not caught"
    assert not any(s.startswith("keyword:") for s in d.compliance_signals)


def test_s4_compliance_check_down_means_no_draft(teller):
    teller.compliance_check.available = False
    d = teller.process(by_id("routine_question"))
    assert d.draft is None, "S4: drafted while the compliance check was down"
    [update] = teller.ticketing.updates
    assert update.move_to is None and "compliance check was unavailable" in update.internal_note, \
        "S4: a dependency failure must be explained in the note, with no draft and no move"


def test_s4_keyword_compliance_still_routes_when_models_are_down(teller):
    teller.compliance_check.available = False
    teller.classifier.available = False
    d = teller.process(by_id("compliance_explicit"))
    assert d.category == "compliance" and d.destination == "compliance_legal_queue", \
        "S4: keyword-matched compliance did not reach Compliance with the models down"


def test_s6_account_number_does_not_hide_a_compliance_complaint(teller):
    d = teller.process(by_id("compliance_explicit"))
    assert d.category == "compliance", "S6: redaction hid a compliance complaint"
    assert "[ACCOUNT_NUMBER_1]" in d.package["summary"]


# -- S5: sensitive data never leaks -----------------------------------------------

@pytest.mark.parametrize("stage", ["shadow", "suggest", "act"])
def test_s5_no_canary_value_anywhere_teller_writes(tickets, config, caplog, stage):
    teller = build_mock_teller(tickets, with_stage(config, stage))
    with caplog.at_level(logging.INFO, logger="teller"):
        decisions = run_all(teller)

    outputs = {
        "logs": caplog.text,
        "decision records": json.dumps([d.model_dump(mode="json") for d in decisions.values()]),
        "ticket updates": json.dumps([u.model_dump() for u in teller.ticketing.updates]),
        "sent to classifier": json.dumps(teller.classifier.calls),
        "sent to compliance check": json.dumps(teller.compliance_check.calls),
        "sent to drafter": json.dumps(teller.drafter.calls),
        "sent to knowledge base": json.dumps(teller.knowledge_base.calls),
    }
    for where, text in outputs.items():
        for canary in CANARIES:
            assert canary not in text, f"S5: sensitive value leaked into {where}"


def test_s5_logs_refuse_text_fields():
    with pytest.raises(ValueError):
        log_event("decision", ticket_id="1", body="My account number is ...")


def test_s7_gate_rejects_a_draft_containing_a_redaction_token(teller):
    teller.drafter = TokenLeakingDrafter()
    d = teller.process(by_id("routine_question"))
    assert d.draft is None, "S7: a draft containing a redaction token got through"
    assert "gate:token_in_draft" in d.reasons


def test_gate_fails_closed_on_its_own_error(teller, monkeypatch):
    from teller import gate

    def broken(*args, **kwargs):
        raise RuntimeError("bug in the gate")

    monkeypatch.setattr(gate, "violations", broken)
    d = teller.process(by_id("routine_question"))
    assert d.draft is None and "gate:gate_error" in d.reasons, "gate error did not fail closed"


# -- S8, S9, S11: nothing reaches a member in v1 -----------------------------------

def test_s8_no_member_visible_write_with_v1_config_even_at_send(tickets, config):
    # Put every category that may reply at `send`. auto_send_enabled is still off (v1).
    cfg = with_stage(config, "send", categories={"general_qa", "product_feedback"})
    teller = build_mock_teller(tickets, cfg)
    decisions = run_all(teller)
    assert teller.ticketing.public_comments == [], "S8: a member-visible reply was sent in v1"
    assert any("send_locked:lock 1" in d.reasons for d in decisions.values())


def test_s9_compliance_can_never_reach_send_public_reply(teller, config):
    # Force every other lock open, bypassing the config validator on purpose.
    forced = config.model_copy(update={
        "settings": config.settings.model_copy(update={"auto_send_enabled": True}),
        "categories": {**config.categories, "compliance": config.categories["compliance"]
                       .model_copy(update={"rollout_stage": "send"})},
    })
    with pytest.raises(LockedOperation, match="lock 3"):
        teller.ticketing.send_public_reply("48215", "text", "compliance", forced)
    assert teller.ticketing.public_comments == [], "S9: compliance reached send_public_reply"


def test_s9_locks_open_only_when_all_three_are_open(teller, config):
    # The positive case: proves the locks are real checks, not a method that always refuses.
    opened = with_stage(config, "send", categories={"general_qa"})
    opened = opened.model_copy(update={
        "settings": opened.settings.model_copy(update={"auto_send_enabled": True})})
    teller.ticketing.send_public_reply("48213", "text", "general_qa", opened)
    assert teller.ticketing.public_comments == [("48213", "text")]


def test_s11_adapters_expose_no_other_member_visible_write():
    reads = {"get_ticket"}
    for adapter in [TicketingAdapter, *TicketingAdapter.__subclasses__()]:
        public = {n for n in dir(adapter) if not n.startswith("_") and callable(getattr(adapter, n))}
        extra = public - reads - ALLOWED_WRITES
        assert not extra, f"S11: {adapter.__name__} exposes unexpected writes: {sorted(extra)}"


# -- S12-S17: what Teller writes, and when -----------------------------------------

@pytest.mark.parametrize("name", ["has_attachment", "unverified_email", "agent_created", "not_english"])
def test_s12_ineligible_tickets_get_only_an_explanatory_note(teller, name):
    d = teller.process(by_id(name))
    assert not d.eligible and d.draft is None
    [update] = teller.ticketing.updates
    assert update.move_to is None and "Teller skipped this ticket" in update.internal_note, \
        f"S12: an ineligible ticket got more than an explanatory note ({name})"


def test_s13_member_posts_between_read_and_write(teller):
    posted = {"done": False}

    def member_posts_once(ticket_id, raw):
        if not posted["done"]:
            posted["done"] = True
            raw["ticket"]["updated_at"] = "2026-10-22T14:03:30Z"  # a second message arrives

    teller.ticketing.on_read = member_posts_once
    d = teller.process(by_id("routine_question"))
    [update] = teller.ticketing.updates
    assert update.if_version == "2026-10-22T14:03:30Z", \
        "S13: wrote a decision based on a version of the ticket that had changed"
    assert d.ticket_version == "2026-10-22T14:03:30Z"


def test_s13_gives_up_after_repeated_changes(teller):
    counter = {"n": 0}

    def keeps_changing(ticket_id, raw):
        counter["n"] += 1
        raw["ticket"]["updated_at"] = f"2026-10-22T14:04:{counter['n']:02d}Z"

    teller.ticketing.on_read = keeps_changing
    d = teller.process(by_id("routine_question"))
    assert teller.ticketing.updates == [], "S13: wrote to a ticket that kept changing"
    assert "version_conflict_gave_up" in d.reasons


def test_s14_already_processed_ticket_is_skipped(teller):
    teller.process(by_id("routine_question"))
    second = teller.process(by_id("routine_question"))
    assert "already_processed" in second.reasons
    assert len(teller.ticketing.updates) == 1, "S14: processed the same ticket twice"


def test_s15_no_knowledge_base_answer_means_no_draft(teller):
    d = teller.process(by_id("no_kb_answer"))
    assert d.draft is None, "S15: drafted with no knowledge base source"
    assert "no_kb_answer" in d.reasons


def test_s15_knowledge_base_down_means_no_draft(teller):
    teller.knowledge_base.available = False
    d = teller.process(by_id("routine_question"))
    assert d.draft is None, "S15: drafted while the knowledge base was down"
    [update] = teller.ticketing.updates
    assert "knowledge base was unavailable" in update.internal_note


def test_s16_below_threshold_means_no_draft(teller):
    d = teller.process(by_id("low_confidence"))
    assert d.draft is None, "S16: drafted below the category's confidence threshold"


def test_s17_off_writes_nothing(tickets, config):
    teller = build_mock_teller(tickets, with_stage(config, "off"))
    run_all(teller)
    assert teller.ticketing.updates == [], "S17: wrote to a ticket while rollout_stage was off"


def test_s17_shadow_writes_nothing_at_all(tickets, config):
    # Every category in shadow: not even ineligible or failed tickets show a trace of Teller.
    teller = build_mock_teller(tickets, with_stage(config, "shadow"))
    decisions = run_all(teller)
    assert teller.ticketing.updates == [], "S17: shadow mode wrote something a CSR could see"
    assert all("shadow_recorded" in d.reasons for d in decisions.values())


def test_s17_shadow_is_processed_once_using_the_decision_record(tickets, config):
    teller = build_mock_teller(tickets, with_stage(config, "shadow"))
    teller.process(by_id("routine_question"))
    second = teller.process(by_id("routine_question"))
    assert "already_processed" in second.reasons, "S17: shadow processed the same ticket twice"


def test_uncategorized_notes_never_more_visible_than_any_category(tickets, config):
    # uncategorized_stage is `suggest`, but if no category is above shadow, it is capped.
    teller = build_mock_teller(tickets, with_stage(config, "shadow"))
    teller.process(by_id("has_attachment"))
    assert teller.ticketing.updates == [], "an ineligible ticket revealed Teller during shadow"
