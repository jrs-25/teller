"""Classifier: answers "what is this, and how sure are we?" It never chooses the action.

It may only return category IDs that exist in config (RFC §1).
"""

from __future__ import annotations

from typing import Protocol

from teller.errors import DependencyError
from teller.models import CategoryPolicy


class Classifier(Protocol):
    version: str

    def scores(
        self, redacted_text: str, categories: dict[str, CategoryPolicy]
    ) -> dict[str, float]:
        """Confidence per category ID. Raises DependencyError if unavailable."""
        ...


class RulesClassifier:
    """Deliberately simple stand-in for a model call: counts each category's hints.
    A new category teaches it about itself through its own config file."""

    version = "rules-classifier-0.1"

    def __init__(self, available: bool = True):
        self.available = available
        self.calls: list[str] = []

    def scores(self, redacted_text, categories):
        self.calls.append(redacted_text)
        if not self.available:
            raise DependencyError("classifier unavailable")
        text = redacted_text.lower()
        result = {}
        for cat_id, policy in categories.items():
            hits = sum(1 for hint in policy.hints if hint.lower() in text)
            result[cat_id] = 0.0 if hits == 0 else min(0.95, 0.55 + 0.15 * hits)
        return result
