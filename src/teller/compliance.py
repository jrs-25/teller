"""Compliance detection: two independent checks and a gray zone (RFC §2).

Both checks only push toward compliance. Neither can move a ticket out of it.
"""

from __future__ import annotations

import re
from typing import Protocol

from teller.config import ComplianceBands
from teller.errors import DependencyError


def keyword_tripwire(redacted_text: str, keywords: list[str]) -> list[str]:
    """Deterministic. Needs no model, so it still works when the model provider is down."""
    lowered = redacted_text.lower()
    return [
        kw for kw in keywords if re.search(rf"\b{re.escape(kw.lower())}\b", lowered)
    ]


class ComplianceCheck(Protocol):
    """A separate, single-purpose model call: does this allege unfair, deceptive,
    discriminatory, or illegal treatment, or threaten legal or regulatory action?
    Returns a score from 0 to 1. Raises DependencyError if unavailable."""

    version: str

    def score(self, redacted_text: str) -> float: ...


class RulesComplianceCheck:
    """Stand-in for the model call. Catches paraphrases the keyword list misses."""

    version = "rules-compliance-0.1"

    STRONG = [
        "because of my age", "because of my race", "because i'm a woman",
        "because of my religion", "treated differently", "denied because",
        "misled", "deceptive", "illegal",
    ]
    WEAK = [
        "nobody told me", "never told", "hidden fee", "didn't disclose",
        "not disclosed", "unfair", "ripped off", "scam",
    ]

    def __init__(self, available: bool = True):
        self.available = available
        self.calls: list[str] = []

    def score(self, redacted_text: str) -> float:
        self.calls.append(redacted_text)
        if not self.available:
            raise DependencyError("compliance check unavailable")
        text = redacted_text.lower()
        if any(p in text for p in self.STRONG):
            return 0.85
        if any(p in text for p in self.WEAK):
            return 0.5
        return 0.05


def assess(
    redacted_text: str,
    keywords: list[str],
    check: ComplianceCheck,
    bands: ComplianceBands,
) -> tuple[str, list[str]]:
    """Returns (zone, signals). Zone is clear, gray, not_compliance, or unknown."""
    signals = [f"keyword:{kw}" for kw in keyword_tripwire(redacted_text, keywords)]
    try:
        score = check.score(redacted_text)
        signals.append(f"check:{score:.2f}")
    except DependencyError:
        signals.append("check:unavailable")
        score = None

    if any(s.startswith("keyword:") for s in signals):
        return "clear", signals
    if score is None:
        return "unknown", signals  # fail closed: no draft (RFC §4)
    if score >= bands.route_at:
        return "clear", signals
    if score >= bands.gray_at:
        return "gray", signals
    return "not_compliance", signals
