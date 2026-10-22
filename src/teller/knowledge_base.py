"""Knowledge base adapter: wraps the help center's existing search. No ingestion (RFC §3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from teller.errors import DependencyError
from teller.models import Article


class KnowledgeBase(Protocol):
    def search(self, query: str) -> list[Article]:
        """Most relevant first. Raises DependencyError if unavailable."""
        ...


MOCK_ARTICLES = [
    Article(
        article_id="kb-101",
        title="CD early withdrawal penalties",
        url="https://help.example.com/articles/kb-101",
        updated_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        text="If you withdraw from a certificate of deposit before it matures, an early "
        "withdrawal penalty applies. For 12-month CDs the penalty is 90 days of simple interest.",
    ),
    Article(
        article_id="kb-102",
        title="Resetting your password",
        url="https://help.example.com/articles/kb-102",
        updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        text="To reset your password, choose 'Forgot password' on the sign-in page and "
        "follow the link we email you. The link expires after 30 minutes.",
    ),
    Article(
        article_id="kb-103",
        title="How long transfers take",
        url="https://help.example.com/articles/kb-103",
        updated_at=datetime(2025, 11, 20, tzinfo=timezone.utc),  # stale on purpose
        text="Transfers between linked accounts usually arrive within 1 to 3 business days.",
    ),
]


class MockKnowledgeBase:
    """Keyword-overlap search over a few fake articles. Proves the rules, not retrieval quality."""

    STOPWORDS = {"the", "a", "an", "my", "i", "to", "of", "is", "it", "if", "do", "how",
                 "what", "can", "for", "and", "on", "in", "me", "you", "your", "out"}

    def __init__(self, articles: list[Article] | None = None, available: bool = True):
        self.articles = MOCK_ARTICLES if articles is None else articles
        self.available = available
        self.calls: list[str] = []

    def search(self, query: str) -> list[Article]:
        self.calls.append(query)
        if not self.available:
            raise DependencyError("knowledge base unavailable")
        words = self._words(query)
        results = []
        for article in self.articles:
            overlap = words & self._words(article.title + " " + article.text)
            relevance = len(overlap) / max(len(words), 1)
            if overlap:
                results.append(article.model_copy(update={"relevance": round(relevance, 2)}))
        return sorted(results, key=lambda a: a.relevance, reverse=True)

    def _words(self, text: str) -> set[str]:
        cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
        return {w for w in cleaned.split() if w not in self.STOPWORDS and len(w) > 2}
