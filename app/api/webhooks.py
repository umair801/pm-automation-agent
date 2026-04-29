"""
FastAPI router for inbound webhook events.
Covers: GroupMe, Slack, OpenPhone.
Postmark, Twilio, Raycast, Granola, and iOS voice memo
are handled in app/api/capture.py.
"""

import hmac
import hashlib
import time
import structlog
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional

from app.models.webhook import (
    GroupMeWebhookPayload,
    SlackEventPayload,
    OpenPhoneWebhookPayload,
)
from app.clients.supabase_client import SupabaseClient
from app.utils.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------

def _verify_slack_signature(
    raw_body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify a Slack request signature using HMAC-SHA256.
    Rejects requests with a timestamp older than 5 minutes.
    """
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
        base = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            secret.encode("utf-8"),
            base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def _verify_openphone_signature(
    raw_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify an OpenPhone webhook HMAC-SHA256 signature."""
    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GroupMe
# ---------------------------------------------------------------------------

@router.post("/groupme")
async def receive_groupme_webhook(payload: GroupMeWebhookPayload) -> dict:
    """
    Receive a GroupMe bot callback.
    GroupMe does not sign requests; we filter out bot messages
    to avoid processing our own replies.
    """
    if payload.sender_type == "bot":
        return {"status": "ignored", "reason": "bot_message"}

    logger.info(
        "groupme_message_received",
        group_id=payload.group_id,
        sender=payload.name,
    )

    db = SupabaseClient()
    await db.write_audit_log(
        event_type="groupme_message",
        source="groupme",
        status="received",
        payload=payload.model_dump(),
    )

    return {"status": "received", "source": "groupme"}


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

@router.post("/slack")
async def receive_slack_webhook(
    request: Request,
    x_slack_request_timestamp: Optional[str] = Header(None),
    x_slack_signature: Optional[str] = Header(None),
) -> dict:
    """
    Receive a Slack Events API callback.
    Handles the url_verification challenge and standard event callbacks.
    Verifies the Slack signing secret on all non-development requests.
    """
    raw_body = await request.body()

    if settings.APP_ENV != "development":
        if not x_slack_request_timestamp or not x_slack_signature:
            raise HTTPException(status_code=401, detail="Missing Slack signature headers")
        if not _verify_slack_signature(
            raw_body,
            x_slack_request_timestamp,
            x_slack_signature,
            settings.SLACK_SIGNING_SECRET,
        ):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

    try:
        payload_dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    payload = SlackEventPayload(**payload_dict)

    # Slack URL verification handshake
    if payload.type == "url_verification":
        return {"challenge": payload.challenge}

    event_type = payload.event.get("type") if payload.event else "unknown"
    logger.info("slack_event_received", event_type=event_type, team_id=payload.team_id)

    db = SupabaseClient()
    await db.write_audit_log(
        event_type=f"slack_{event_type}",
        source="slack",
        status="received",
        payload=payload_dict,
    )

    return {"status": "received", "source": "slack", "event_type": event_type}


# ---------------------------------------------------------------------------
# OpenPhone
# ---------------------------------------------------------------------------

@router.post("/openphone")
async def receive_openphone_webhook(
    request: Request,
    x_openphone_signature: Optional[str] = Header(None),
) -> dict:
    """
    Receive an OpenPhone event webhook.
    Verifies HMAC signature on all non-development requests.
    """
    raw_body = await request.body()

    if settings.APP_ENV != "development":
        if not x_openphone_signature:
            raise HTTPException(status_code=401, detail="Missing OpenPhone signature")
        if not _verify_openphone_signature(
            raw_body,
            x_openphone_signature,
            settings.OPENPHONE_WEBHOOK_SECRET,
        ):
            raise HTTPException(status_code=401, detail="Invalid OpenPhone signature")

    try:
        payload_dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    payload = OpenPhoneWebhookPayload(**payload_dict)

    logger.info(
        "openphone_event_received",
        event_id=payload.id,
        event_type=payload.type,
    )

    db = SupabaseClient()
    await db.write_audit_log(
        event_type=f"openphone_{payload.type}",
        source="openphone",
        status="received",
        payload=payload_dict,
    )

    return {"status": "received", "source": "openphone", "event_type": payload.type}
