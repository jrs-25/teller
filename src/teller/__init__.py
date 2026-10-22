"""Teller: prototype support triage & resolution agent. See RFC.md."""

from __future__ import annotations

from teller.classifier import RulesClassifier
from teller.compliance import RulesComplianceCheck
from teller.config import check_routes, load_config, load_routes
from teller.drafting import TemplateDrafter
from teller.knowledge_base import MockKnowledgeBase
from teller.pipeline import Teller
from teller.ticketing import MockZendesk


def build_mock_teller(tickets: dict[str, dict], config=None) -> Teller:
    """Teller wired to in-memory mocks of every external system. No API keys needed."""
    config = config or load_config()
    routes = load_routes("zendesk")
    check_routes(config, routes)
    return Teller(
        config=config,
        ticketing=MockZendesk(tickets, routes),
        knowledge_base=MockKnowledgeBase(),
        classifier=RulesClassifier(),
        compliance_check=RulesComplianceCheck(),
        drafter=TemplateDrafter(),
    )
