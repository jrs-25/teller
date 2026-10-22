"""Data shapes from RFC §5. Nothing past the ticketing adapter sees vendor JSON."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Action = Literal["draft_response", "route_with_package", "escalate", "none"]
Stage = Literal["off", "shadow", "suggest", "act", "send"]
ComplianceZone = Literal["clear", "gray", "not_compliance", "unknown"]


class Member(BaseModel):
    member_id: str
    auth_level: str
    products: list[str] = []


class Intake(BaseModel):
    """What the ticketing adapter produces. `body` is raw: only the redactor reads it."""

    ticket_id: str
    ticket_version: str
    member: Member
    channel: str
    subject: str
    body: str
    created_by_member: bool
    has_attachments: bool
    language: str
    created_at: datetime
    tags: list[str] = []


class CategoryPolicy(BaseModel):
    """One file in config/categories/. Owned by the team named in `owner`."""

    id: str
    description: str
    hints: list[str] = []
    action: Literal["draft_response", "route_with_package", "escalate"]
    member_response_allowed: bool
    destination: str | None
    package_fields: list[str] = []
    confidence_threshold: float
    precedence: int
    rollout_stage: Stage
    owner: str


class Decision(BaseModel):
    """The triage result, and also the decision record. Never holds raw text."""

    decision_id: str = Field(default_factory=lambda: f"d-{uuid4().hex[:8]}")
    ticket_id: str
    ticket_version: str
    eligible: bool = True
    category: str | None = None
    action: Action = "none"
    confidence: float | None = None
    confidence_tier: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    compliance_zone: ComplianceZone = "unknown"
    compliance_signals: list[str] = []
    draft: str | None = None
    package: dict | None = None
    destination: str | None = None
    sources: list[str] = []
    requires_human_approval: bool = True
    rollout_stage: Stage | None = None
    reasons: list[str] = []
    config_version: str = ""
    model_version: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TicketUpdate(BaseModel):
    """The single, all-or-nothing write Teller makes to a ticket (RFC §3)."""

    ticket_id: str
    if_version: str
    internal_note: str | None = None
    add_tags: list[str] = []
    move_to: str | None = None


class Article(BaseModel):
    article_id: str
    title: str
    url: str
    updated_at: datetime
    text: str
    relevance: float = 0.0
