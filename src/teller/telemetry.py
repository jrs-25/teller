"""Logs carry IDs and decision fields, never text (RFC §2).

log_event refuses any field outside the allowlist, so text can't reach logs by
accident. Traces would follow the same rule.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("teller")

ALLOWED_FIELDS = {
    "ticket_id", "decision_id", "category", "action", "confidence", "zone",
    "stage", "reasons", "attempt", "duration_ms", "error_type",
}


def log_event(event: str, **fields) -> None:
    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"log fields not allowed (no text in logs): {sorted(unknown)}")
    logger.info(json.dumps({"event": event, **fields}, default=str))
