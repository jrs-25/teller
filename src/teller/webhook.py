"""Thin webhook endpoint (RFC §3). The payload carries only the ticket ID.

Teller verifies the signature, then fetches the ticket through the API. In
production this endpoint would put the ID on a durable queue and return at once;
the prototype processes inline. The queue, sweep, and retries are handed to FDE.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from fastapi import FastAPI, Header, HTTPException, Request

from teller.pipeline import Teller


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Zendesk-style signature: base64(HMAC-SHA256(secret, timestamp + body))."""
    digest = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def create_app(teller: Teller, secret: str) -> FastAPI:
    app = FastAPI(title="Teller")

    @app.post("/webhooks/ticket-created", status_code=202)
    async def ticket_created(
        request: Request,
        x_zendesk_webhook_signature: str = Header(...),
        x_zendesk_webhook_signature_timestamp: str = Header(...),
    ):
        body = await request.body()
        expected = sign(secret, x_zendesk_webhook_signature_timestamp, body)
        if not hmac.compare_digest(expected, x_zendesk_webhook_signature):
            raise HTTPException(status_code=401, detail="bad signature")
        payload = await request.json()
        decision = teller.process(str(payload["ticket_id"]))
        return {"decision_id": decision.decision_id, "action": decision.action}

    return app
