"""One pipeline, three required paths (brief, Part 2 items 1-2), plus the ticketing rules."""

from conftest import by_id, with_stage

from teller import build_mock_teller
from teller.ticketing import PROCESSED_TAG


def test_routine_question_gets_a_cited_draft(teller):
    d = teller.process(by_id("routine_question"))
    assert d.category == "general_qa"
    assert d.action == "draft_response"
    assert d.draft and "90 days" in d.draft
    assert d.sources == ["kb-101"]
    assert d.requires_human_approval


def test_product_feedback_routes_with_summary_and_thank_you(teller):
    d = teller.process(by_id("product_feedback"))
    assert d.category == "product_feedback"
    assert d.action == "route_with_package"
    assert d.destination == "product_feedback_queue"
    assert set(d.package) == {"category", "summary", "intake_ref"}
    assert d.draft and "thanks" in d.draft.lower()


def test_compliance_complaint_routes_with_no_draft(teller):
    d = teller.process(by_id("compliance_explicit"))
    assert d.category == "compliance"
    assert d.action == "route_with_package"
    assert d.destination == "compliance_legal_queue"
    assert d.draft is None


def test_one_ticket_update_with_note_tag_and_move(teller):
    teller.process(by_id("compliance_explicit"))
    [update] = teller.ticketing.updates
    assert update.add_tags == [PROCESSED_TAG]
    assert update.move_to == "compliance_legal_queue"
    assert "Teller · act · compliance" in update.internal_note


def test_suggest_stage_notes_but_does_not_move(tickets, config):
    teller = build_mock_teller(tickets, with_stage(config, "suggest"))
    teller.process(by_id("compliance_explicit"))
    [update] = teller.ticketing.updates
    assert update.move_to is None
    assert "Suggest routing to: compliance_legal_queue" in update.internal_note


def test_low_confidence_escalates_with_a_note_and_no_draft(teller):
    d = teller.process(by_id("low_confidence"))
    assert d.action == "escalate" and d.draft is None
    assert "below_threshold" in d.reasons
    assert teller.ticketing.updates  # the note still helps the CSR
