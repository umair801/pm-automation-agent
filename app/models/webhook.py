"""
Pydantic models for all inbound capture source payloads.
Covers: Postmark, Twilio, Raycast, iOS voice memo, Granola,
        GroupMe, Slack, and OpenPhone.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Postmark (inbound email)
# ---------------------------------------------------------------------------

class PostmarkInboundPayload(BaseModel):
    """Inbound email forwarded by Postmark to the capture endpoint."""

    message_id: str = Field(..., alias="MessageID")
    from_email: str = Field(..., alias="From")
    to_email: str = Field(..., alias="To")
    subject: Optional[str] = Field(None, alias="Subject")
    text_body: Optional[str] = Field(None, alias="TextBody")
    html_body: Optional[str] = Field(None, alias="HtmlBody")
    date: Optional[str] = Field(None, alias="Date")
    reply_to: Optional[str] = Field(None, alias="ReplyTo")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Twilio (SMS bot)
# ---------------------------------------------------------------------------

class TwilioInboundSMS(BaseModel):
    """Inbound SMS delivered by Twilio webhook."""

    message_sid: str = Field(..., alias="MessageSid")
    from_number: str = Field(..., alias="From")
    to_number: str = Field(..., alias="To")
    body: str = Field(..., alias="Body")
    num_media: Optional[str] = Field(None, alias="NumMedia")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Raycast (hotkey JSON POST)
# ---------------------------------------------------------------------------

class RaycastCapturePayload(BaseModel):
    """Quick-capture payload sent from a Raycast hotkey extension."""

    text: str = Field(..., description="Raw text captured via Raycast")
    source: str = Field(default="raycast", description="Always 'raycast'")
    tags: Optional[list[str]] = Field(default=None, description="Optional tags from the extension")
    project_hint: Optional[str] = Field(None, description="Optional project name hint from the user")


# ---------------------------------------------------------------------------
# iOS Shortcut (voice memo — Whisper transcription handled upstream)
# ---------------------------------------------------------------------------

class iOSVoiceMemoPayload(BaseModel):
    """
    Metadata payload accompanying an iOS Shortcut voice memo upload.
    The audio file is sent as multipart/form-data; this model covers
    the JSON fields that arrive alongside it.
    """

    source: str = Field(default="ios_voice_memo", description="Always 'ios_voice_memo'")
    title: Optional[str] = Field(None, description="Optional title from the Shortcut")
    project_hint: Optional[str] = Field(None, description="Optional project name hint")
    recorded_at: Optional[str] = Field(None, description="ISO 8601 timestamp from device")


# ---------------------------------------------------------------------------
# Granola (meeting transcript ingest)
# ---------------------------------------------------------------------------

class GranolaTranscriptPayload(BaseModel):
    """Meeting transcript payload pushed from Granola."""

    meeting_id: str = Field(..., description="Granola meeting UUID")
    title: Optional[str] = Field(None, description="Meeting title")
    transcript: str = Field(..., description="Full meeting transcript text")
    attendees: Optional[list[str]] = Field(default=None, description="List of attendee names or emails")
    started_at: Optional[str] = Field(None, description="Meeting start time ISO 8601")
    ended_at: Optional[str] = Field(None, description="Meeting end time ISO 8601")
    source: str = Field(default="granola", description="Always 'granola'")


# ---------------------------------------------------------------------------
# GroupMe (webhook)
# ---------------------------------------------------------------------------

class GroupMeWebhookPayload(BaseModel):
    """Inbound message event from a GroupMe bot webhook."""

    id: str = Field(..., description="GroupMe message ID")
    text: Optional[str] = Field(None, description="Message text body")
    name: Optional[str] = Field(None, description="Sender display name")
    user_id: Optional[str] = Field(None, description="Sender user ID")
    group_id: Optional[str] = Field(None, description="GroupMe group ID")
    created_at: Optional[int] = Field(None, description="Unix timestamp of message")
    sender_type: Optional[str] = Field(None, description="'user' or 'bot'")
    source: str = Field(default="groupme", description="Always 'groupme'")


# ---------------------------------------------------------------------------
# Slack (event webhook)
# ---------------------------------------------------------------------------

class SlackEventPayload(BaseModel):
    """
    Slack Events API payload.
    Covers both the url_verification challenge and standard event callbacks.
    """

    token: Optional[str] = None
    type: str = Field(..., description="'url_verification' or 'event_callback'")
    challenge: Optional[str] = Field(None, description="Present only during Slack URL verification")
    event: Optional[dict[str, Any]] = Field(None, description="The nested event object for event_callback")
    team_id: Optional[str] = None
    api_app_id: Optional[str] = None


# ---------------------------------------------------------------------------
# OpenPhone (webhook)
# ---------------------------------------------------------------------------

class OpenPhoneWebhookPayload(BaseModel):
    """Inbound call or SMS event from OpenPhone webhook."""

    id: str = Field(..., description="OpenPhone event ID")
    type: str = Field(..., description="Event type, e.g. 'message.received' or 'call.completed'")
    data: dict[str, Any] = Field(..., description="Full event data object from OpenPhone")
    created_at: Optional[str] = Field(None, description="ISO 8601 event timestamp")
    source: str = Field(default="openphone", description="Always 'openphone'")
