"""Ticketing adapter: the only code that knows which vendor Teller talks to (RFC §3).

Teller's everyday write is one all-or-nothing, conditional TicketUpdate:
an internal note, the `teller_processed` tag, and an optional group move.
The one member-visible write, `send_public_reply`, is locked behind three checks.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Callable

from teller.config import TellerConfig
from teller.errors import DependencyError, LockedOperation, VersionConflict
from teller.models import Intake, Member, TicketUpdate

PROCESSED_TAG = "teller_processed"

# The complete write surface any ticketing adapter may expose. CI checks this (S11).
ALLOWED_WRITES = {"apply_update", "send_public_reply"}


class TicketingAdapter:
    """Vendor-neutral contract. Subclasses implement the vendor-specific parts."""

    def get_ticket(self, ticket_id: str) -> Intake:
        raise NotImplementedError

    def apply_update(self, update: TicketUpdate) -> None:
        """Note + tag + group move in one update, rejected if the ticket changed."""
        raise NotImplementedError

    def send_public_reply(
        self, ticket_id: str, text: str, category_id: str, config: TellerConfig
    ) -> None:
        """Member-visible. Every lock is checked on every call (RFC §3)."""
        policy = config.categories.get(category_id)
        if not config.settings.auto_send_enabled:
            raise LockedOperation("lock 1: auto_send_enabled is off")
        if policy is None or policy.rollout_stage != "send":
            raise LockedOperation("lock 2: category is not at rollout_stage send")
        if not policy.member_response_allowed:
            raise LockedOperation("lock 3: category does not allow member replies")
        self._post_public_comment(ticket_id, text)

    def _post_public_comment(self, ticket_id: str, text: str) -> None:
        raise NotImplementedError


class MockZendesk(TicketingAdapter):
    """In-memory stand-in for Zendesk. Takes Zendesk-shaped ticket JSON, records
    every write, and can simulate outages and a member posting mid-processing."""

    # Vendor-specific mapping lives here and nowhere else.
    FIELD_MEMBER_ID = 7001
    FIELD_AUTH_LEVEL = 7002
    FIELD_PRODUCTS = 7003
    def __init__(self, tickets: dict[str, dict], routes: dict[str, int]):
        self.routes = routes  # destination name → Zendesk group ID (config/routes.yaml)
        self.tickets = {tid: copy.deepcopy(t) for tid, t in tickets.items()}
        self.updates: list[TicketUpdate] = []        # applied writes
        self.public_comments: list[tuple[str, str]] = []
        self.read_available = True
        self.write_available = True
        self.on_read: Callable[[str, dict], None] | None = None  # test hook

    def get_ticket(self, ticket_id: str) -> Intake:
        if not self.read_available:
            raise DependencyError("ticketing API unavailable (read)")
        raw = self.tickets[ticket_id]
        intake = self._to_intake(raw)
        if self.on_read:
            self.on_read(ticket_id, raw)
        return intake

    def apply_update(self, update: TicketUpdate) -> None:
        if not self.write_available:
            raise DependencyError("ticketing API unavailable (write)")
        raw = self.tickets[update.ticket_id]["ticket"]
        if raw["updated_at"] != update.if_version:
            raise VersionConflict(update.ticket_id)
        if update.move_to and update.move_to not in self.routes:
            raise ValueError(f"no existing route named {update.move_to}")
        self.updates.append(update)
        raw["tags"] = sorted(set(raw["tags"]) | set(update.add_tags))
        if update.move_to:
            raw["group_id"] = self.routes[update.move_to]
        raw["updated_at"] = raw["updated_at"] + "+teller"

    def _post_public_comment(self, ticket_id: str, text: str) -> None:
        self.public_comments.append((ticket_id, text))

    def _to_intake(self, raw: dict) -> Intake:
        t = raw["ticket"]
        fields = {f["id"]: f["value"] for f in t.get("custom_fields", [])}
        comments = raw.get("comments", [])
        return Intake(
            ticket_id=str(t["id"]),
            ticket_version=t["updated_at"],
            member=Member(
                member_id=fields.get(self.FIELD_MEMBER_ID, ""),
                auth_level=fields.get(self.FIELD_AUTH_LEVEL, "none"),
                products=fields.get(self.FIELD_PRODUCTS, []) or [],
            ),
            channel=t["via"]["channel"],
            subject=t["subject"],
            body=t["description"],
            created_by_member=t["submitter_id"] == t["requester_id"],
            has_attachments=any(c.get("attachments") for c in comments),
            language=raw.get("requester", {}).get("locale", "en-US"),
            created_at=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            tags=t.get("tags", []),
        )
