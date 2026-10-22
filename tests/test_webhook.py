"""The thin webhook: verify the signature, take only the ticket ID, fetch the rest (RFC §3)."""

import json

from conftest import by_id
from fastapi.testclient import TestClient

from teller.webhook import create_app, sign

SECRET = "test-secret"
TIMESTAMP = "2026-10-22T14:03:11Z"


def post(client, body: bytes, signature: str):
    return client.post(
        "/webhooks/ticket-created",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Zendesk-Webhook-Signature": signature,
            "X-Zendesk-Webhook-Signature-Timestamp": TIMESTAMP,
        },
    )


def test_signed_webhook_processes_the_ticket(teller):
    client = TestClient(create_app(teller, SECRET))
    body = json.dumps({"event": "ticket.created", "ticket_id": int(by_id("routine_question"))}).encode()
    response = post(client, body, sign(SECRET, TIMESTAMP, body))
    assert response.status_code == 202
    assert response.json()["action"] == "draft_response"


def test_bad_signature_is_rejected_and_nothing_is_processed(teller):
    client = TestClient(create_app(teller, SECRET))
    body = json.dumps({"ticket_id": int(by_id("routine_question"))}).encode()
    response = post(client, body, sign("wrong-secret", TIMESTAMP, body))
    assert response.status_code == 401
    assert teller.decisions == []
