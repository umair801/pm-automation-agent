"""
Capture router.
Five endpoints for inbound item capture:
  POST /capture/postmark   — inbound email via Postmark
  POST /capture/twilio     — inbound SMS via Twilio
  POST /capture/raycast    — quick capture via Raycast hotkey
  POST /capture/ios-voice  — voice memo via iOS Shortcut (Whisper transcription)
  POST /capture/granola    — meeting transcript via Granola
Each endpoint runs Triage + Prioritizer agents and writes to Notion + Supabase.
"""

import structlog
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from typing import Optional

from app.models.webhook import (
    PostmarkInboundPayload,
    TwilioInboundSMS,
    RaycastCapturePayload,
    GranolaTranscriptPayload,
)
from app.models.qualification import CaptureSource, TriagePipelineResult
from app.agents.triage_agent import TriageAgent
from app.agents.prioritizer_agent import PrioritizerAgent
from app.clients.notion_client import NotionClient
from app.clients.supabase_client import SupabaseClient
from app.services.whisper_service import WhisperService, WhisperServiceError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/capture", tags=["Capture"])


# ---------------------------------------------------------------------------
# Postmark inbound email
# ---------------------------------------------------------------------------

@router.post("/postmark")
async def capture_postmark(request: Request) -> dict:
    """
    Receive an inbound email forwarded by Postmark.
    Extracts subject and body, runs triage and priority agents,
    writes result to Notion Items DB and Supabase.
    """
    try:
        payload_dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    try:
        payload = PostmarkInboundPayload(**payload_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid Postmark payload: {e}")

    raw_content = (
        f"Subject: {payload.subject or 'No subject'}\n"
        f"From: {payload.from_email}\n\n"
        f"{payload.text_body or payload.html_body or 'No body'}"
    )

    return await _run_capture_pipeline(
        raw_content=raw_content,
        source=CaptureSource.POSTMARK,
        source_meta={"message_id": payload.message_id, "from": payload.from_email},
    )


# ---------------------------------------------------------------------------
# Twilio inbound SMS
# ---------------------------------------------------------------------------

@router.post("/twilio")
async def capture_twilio(request: Request) -> dict:
    """
    Receive an inbound SMS from Twilio.
    Parses form-encoded body (Twilio sends application/x-www-form-urlencoded),
    runs triage and priority agents, writes result to Notion and Supabase.
    """
    try:
        form = await request.form()
        payload = TwilioInboundSMS(
            MessageSid=form.get("MessageSid", ""),
            From=form.get("From", ""),
            To=form.get("To", ""),
            Body=form.get("Body", ""),
            NumMedia=form.get("NumMedia"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Twilio payload: {e}")

    raw_content = (
        f"SMS from: {payload.from_number}\n\n"
        f"{payload.body}"
    )

    return await _run_capture_pipeline(
        raw_content=raw_content,
        source=CaptureSource.TWILIO,
        source_meta={"message_sid": payload.message_sid, "from": payload.from_number},
    )


# ---------------------------------------------------------------------------
# Raycast quick capture
# ---------------------------------------------------------------------------

@router.post("/raycast")
async def capture_raycast(payload: RaycastCapturePayload) -> dict:
    """
    Receive a quick-capture JSON POST from a Raycast hotkey extension.
    Runs triage and priority agents, writes result to Notion and Supabase.
    """
    raw_content = payload.text
    if payload.project_hint:
        raw_content = f"Project: {payload.project_hint}\n\n{raw_content}"
    if payload.tags:
        raw_content += f"\n\nTags: {', '.join(payload.tags)}"

    return await _run_capture_pipeline(
        raw_content=raw_content,
        source=CaptureSource.RAYCAST,
        source_meta={"project_hint": payload.project_hint, "tags": payload.tags},
    )


# ---------------------------------------------------------------------------
# iOS voice memo
# ---------------------------------------------------------------------------

@router.post("/ios-voice")
async def capture_ios_voice(
    audio: UploadFile = File(...),
    title: Optional[str] = Form(None),
    project_hint: Optional[str] = Form(None),
) -> dict:
    """
    Receive a voice memo uploaded from an iOS Shortcut.
    Transcribes audio via Whisper, then runs triage and priority agents,
    writes result to Notion and Supabase.
    """
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/m4a"
    filename = audio.filename or "memo.m4a"

    try:
        whisper = WhisperService()
        transcript = await whisper.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
        )
    except WhisperServiceError as e:
        logger.error("ios_voice_transcription_error", error=str(e))
        raise HTTPException(status_code=422, detail=f"Transcription failed: {e}")

    raw_content = transcript
    if title:
        raw_content = f"Title: {title}\n\n{raw_content}"
    if project_hint:
        raw_content = f"Project: {project_hint}\n\n{raw_content}"

    return await _run_capture_pipeline(
        raw_content=raw_content,
        source=CaptureSource.IOS_VOICE_MEMO,
        source_meta={"filename": filename, "title": title, "project_hint": project_hint},
    )


# ---------------------------------------------------------------------------
# Granola meeting transcript
# ---------------------------------------------------------------------------

@router.post("/granola")
async def capture_granola(payload: GranolaTranscriptPayload) -> dict:
    """
    Receive a meeting transcript pushed from Granola.
    Runs triage and priority agents, writes result to Notion and Supabase.
    """
    attendees_str = (
        ", ".join(payload.attendees) if payload.attendees else "Unknown"
    )

    raw_content = (
        f"Meeting: {payload.title or 'Untitled Meeting'}\n"
        f"Attendees: {attendees_str}\n"
        f"Started: {payload.started_at or 'Unknown'}\n\n"
        f"{payload.transcript}"
    )

    return await _run_capture_pipeline(
        raw_content=raw_content,
        source=CaptureSource.GRANOLA,
        source_meta={
            "meeting_id": payload.meeting_id,
            "title": payload.title,
            "attendees": payload.attendees,
        },
    )


# ---------------------------------------------------------------------------
# Shared pipeline
# ---------------------------------------------------------------------------

async def _run_capture_pipeline(
    raw_content: str,
    source: CaptureSource,
    source_meta: Optional[dict] = None,
) -> dict:
    """
    Run the full capture pipeline for any source.

    Steps:
        1. Triage Agent — classify and extract metadata.
        2. Prioritizer Agent — score urgency and importance.
        3. Write result to Notion Items DB.
        4. Write result to Supabase pm_items.
        5. Write audit log entry.

    Args:
        raw_content: The normalized plain-text content to process.
        source: CaptureSource enum value.
        source_meta: Optional dict of source-specific metadata for the audit log.

    Returns:
        Dict with notion_page_id, priority_level, item_type, and title.

    Raises:
        HTTPException 500 on agent or Notion write failure.
    """
    logger.info("capture_pipeline_start", source=source.value)

    # Step 1: Triage
    try:
        triage_result = await TriageAgent().run(
            raw_content=raw_content,
            source=source,
        )
    except Exception as e:
        logger.error("capture_triage_error", source=source.value, error=str(e))
        raise HTTPException(status_code=500, detail=f"Triage agent failed: {e}")

    # Step 2: Prioritize
    try:
        priority_result = await PrioritizerAgent().run(triage_result)
    except Exception as e:
        logger.error("capture_priority_error", source=source.value, error=str(e))
        raise HTTPException(status_code=500, detail=f"Prioritizer agent failed: {e}")

    # Step 3: Write to Notion Items DB
    notion_page_id: Optional[str] = None
    try:
        notion = NotionClient()
        notion_properties = _build_notion_item_properties(triage_result, priority_result)
        page = await notion.create_item(notion_properties)
        notion_page_id = page.get("id")
        logger.info("capture_notion_item_created", page_id=notion_page_id)
    except Exception as e:
        logger.error("capture_notion_error", source=source.value, error=str(e))
        # Non-fatal: continue to Supabase write

    # Step 4: Write to Supabase pm_items
    db = SupabaseClient()
    try:
        await db.insert_item({
            "source": source.value,
            "item_type": triage_result.item_type.value,
            "title": triage_result.title,
            "summary": triage_result.summary,
            "priority_level": priority_result.priority_level.value,
            "priority_score": priority_result.total_score,
            "project_hint": triage_result.project_hint,
            "assignee_hint": triage_result.assignee_hint,
            "due_date_hint": triage_result.due_date_hint,
            "tags": triage_result.tags,
            "notion_page_id": notion_page_id,
            "raw_content": raw_content,
        })
    except Exception as e:
        logger.error("capture_supabase_error", source=source.value, error=str(e))

    # Step 5: Audit log
    await db.write_audit_log(
        event_type="item_captured",
        source=source.value,
        status="success",
        item_id=notion_page_id,
        payload={
            "item_type": triage_result.item_type.value,
            "priority_level": priority_result.priority_level.value,
            **(source_meta or {}),
        },
    )

    logger.info(
        "capture_pipeline_complete",
        source=source.value,
        item_type=triage_result.item_type.value,
        priority=priority_result.priority_level.value,
        notion_page_id=notion_page_id,
    )

    return {
        "status": "captured",
        "source": source.value,
        "notion_page_id": notion_page_id,
        "item_type": triage_result.item_type.value,
        "priority_level": priority_result.priority_level.value,
        "title": triage_result.title,
    }


# ---------------------------------------------------------------------------
# Notion property builder for Items DB
# ---------------------------------------------------------------------------

def _build_notion_item_properties(triage_result, priority_result) -> dict:
    """
    Build the Notion property payload for a new Items DB page.

    Property names must match the client's Notion Items DB schema exactly.

    Args:
        triage_result: Validated TriageResult from the Triage Agent.
        priority_result: Validated PriorityResult from the Prioritizer Agent.

    Returns:
        Notion-formatted properties dict ready for pages.create().
    """
    properties: dict = {
        "Name": {
            "title": [{"text": {"content": triage_result.title}}]
        },
        "Source": {
            "select": {"name": triage_result.source.value}
        },
        "Item Type": {
            "select": {"name": triage_result.item_type.value}
        },
        "Priority": {
            "select": {"name": priority_result.priority_level.value}
        },
        "Summary": {
            "rich_text": [{"text": {"content": triage_result.summary}}]
        },
        "Status": {
            "status": {"name": "Not Started"}
        },
    }

    if triage_result.tags:
        properties["Tags"] = {
            "multi_select": [{"name": tag} for tag in triage_result.tags]
        }

    if triage_result.project_hint:
        properties["Project"] = {
            "rich_text": [{"text": {"content": triage_result.project_hint}}]
        }

    if triage_result.assignee_hint:
        properties["Assignee"] = {
            "rich_text": [{"text": {"content": triage_result.assignee_hint}}]
        }

    if triage_result.due_date_hint:
        properties["Due Date"] = {
            "date": {"start": triage_result.due_date_hint}
        }

    return properties
