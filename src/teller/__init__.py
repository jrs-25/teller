"""Teller: prototype support triage & resolution agent. See RFC.md."""

from __future__ import annotations

from teller.classifier import RulesClassifier
from teller.compliance import RulesComplianceCheck
from teller.config import load_config
from teller.drafting import TemplateDrafter
from teller.knowledge_base import MockKnowledgeBase
from teller.pipeline import Teller
from teller.ticketing import MockZendesk


def build_mock_teller(tickets: dict[str, dict], config=None) -> Teller:
    """Teller wired to in-memory mocks of every external system. No API keys needed."""
    return Teller(
        config=config or load_config(),
        ticketing=MockZendesk(tickets),
        knowledge_base=MockKnowledgeBase(),
        classifier=RulesClassifier(),
        compliance_check=RulesComplianceCheck(),
        drafter=TemplateDrafter(),
    )
