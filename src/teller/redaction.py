"""Redaction runs first; only this module ever reads raw member text (RFC §2).

Sensitive values become typed, numbered tokens like [ACCOUNT_NUMBER_1]. The
patterns are deliberately simple for the prototype; production gets a proper
redaction service (RFC §2 handoff).
"""

from __future__ import annotations

import re

# Order matters: more specific patterns run first.
PATTERNS = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CARD_NUMBER", re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")),
    ("ACCOUNT_NUMBER", re.compile(r"\b\d(?:[ -]?\d){7,16}\b")),
]

TOKEN_RE = re.compile(r"\[[A-Z_]+_\d+\]")


class Redacted:
    """Redacted text plus how many values of each type were replaced."""

    def __init__(self, text: str, counts: dict[str, int]):
        self.text = text
        self.counts = counts

    @property
    def found_sensitive_data(self) -> bool:
        return any(self.counts.values())


def redact(raw: str) -> Redacted:
    text = raw
    counts: dict[str, int] = {}
    for label, pattern in PATTERNS:
        def _token(_match, label=label):
            counts[label] = counts.get(label, 0) + 1
            return f"[{label}_{counts[label]}]"

        text = pattern.sub(_token, text)
    return Redacted(text, counts)


def contains_token(text: str) -> bool:
    return bool(TOKEN_RE.search(text))
