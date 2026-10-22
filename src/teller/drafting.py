"""Drafter: writes only from the articles it is given, and cites them (RFC §3).

Deliberately a template, not a model. A real model call would sit behind the same
interface; the safety gate checks its output either way.
"""

from __future__ import annotations

from typing import Protocol

from teller.errors import DependencyError
from teller.models import Article


class Drafter(Protocol):
    version: str

    def answer(self, redacted_text: str, articles: list[Article]) -> str: ...

    def thank_you(self, redacted_text: str) -> str: ...


class TemplateDrafter:
    version = "template-drafter-0.1"

    def __init__(self, available: bool = True):
        self.available = available
        self.calls: list[str] = []

    def answer(self, redacted_text, articles):
        self.calls.append(redacted_text)
        if not self.available:
            raise DependencyError("drafter unavailable")
        best = articles[0]
        return (
            "Hi, thanks for reaching out.\n\n"
            f"{best.text}\n\n"
            f"You can read more here: {best.url}"
        )

    def thank_you(self, redacted_text):
        self.calls.append(redacted_text)
        if not self.available:
            raise DependencyError("drafter unavailable")
        return (
            "Hi, thanks for taking the time to share this. We've passed your feedback "
            "to our product team, who review every suggestion."
        )
