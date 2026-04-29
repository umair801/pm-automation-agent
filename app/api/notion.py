"""
Notion router.
Exposes endpoints for Notion workspace interaction and agent-triggered workflows.

  GET  /notion/items              — query Items DB with optional filters
  POST /notion/ask                — on-demand Q&A via Project Assistant Agent
  POST /notion/digest/daily       — trigger daily pruner digest
  POST /notion/digest/weekly      — trigger weekly review digest
  POST /notion/scorecard          — write a Scorecard DB entry from Make.com data
"""

import structlog
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field

from app.clients.notion_client import NotionClient, NotionClientError
from app.agents.project_assistant_agent import ProjectAssistantAgent
from app.services.digest_service import DigestService, DigestServiceError
from app.services.scorecard_service import ScorecardService, ScorecardServiceError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/notion", tags=["Notion"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    """Request body for the on-demand project assistant Q&A endpoint."""

    question: str = Field(..., description="Natural language question about the workspace")
    project_filter: Optional[str] = Field(
        None,
        description="Optional project name to scope the context query",
    )


class ScorecardRequest(BaseModel):
    """
    Request body for the scorecard write endpoint.
    Make.com aggregates REIReply and OpenPhone data and posts it here weekly.
    """

    week_label: Optional[str] = Field(
        None,
        description="ISO week label, e.g. '2026-W18'. Defaults to current week.",
    )
    reireply_data: Optional[dict] = Field(
        None,
        description=(
            "REIReply summary payload. Expected keys: "
            "leads_added, deals_closed, follow_ups_sent, appointments_set."
        ),
    )
    openphone_data: Optional[dict] = Field(
        None,
        description=(
            "OpenPhone summary payload. Expected keys: "
            "calls_made, calls_answered, sms_sent, "
            "voicemails_left, avg_call_duration_seconds."
        ),
    )


# ---------------------------------------------------------------------------
# Items query
# ---------------------------------------------------------------------------

@router.get("/items")
async def list_items(
    source: Optional[str] = Query(None, description="Filter by capture source"),
    priority: Optional[str] = Query(None, description="Filter by priority level"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page_size: int = Query(50, ge=1, le=100, description="Number of results to return"),
) -> dict:
    """
    Query the Notion Items DB with optional filters.
    Returns a flat list of item summaries suitable for a dashboard or digest.
    """
    logger.info("notion_list_items", source=source, priority=priority, status=status)

    filter_conditions = []

    if source:
        filter_conditions.append({
            "property": "Source",
            "select": {"equals": source},
        })
    if priority:
        filter_conditions.append({
            "property": "Priority",
            "select": {"equals": priority},
        })
    if status:
        filter_conditions.append({
            "property": "Status",
            "status": {"equals": status},
        })

    filter_payload: Optional[dict] = None
    if len(filter_conditions) == 1:
        filter_payload = filter_conditions[0]
    elif len(filter_conditions) > 1:
        filter_payload = {"and": filter_conditions}

    try:
        notion = NotionClient()
        pages = await notion.query_items(
            filter_payload=filter_payload,
            sorts=[{"property": "Priority", "direction": "descending"}],
            page_size=page_size,
        )
    except NotionClientError as e:
        logger.error("notion_list_items_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Notion query failed: {e}")

    items = [_summarize_page(page) for page in pages]

    return {"count": len(items), "items": items}


# ---------------------------------------------------------------------------
# Project Assistant Q&A
# ---------------------------------------------------------------------------

@router.post("/ask")
async def ask_project_assistant(body: AskRequest) -> dict:
    """
    Answer a natural language question using live Notion workspace context.
    Powered by the Project Assistant Agent.
    """
    logger.info("notion_ask", question_length=len(body.question))

    try:
        agent = ProjectAssistantAgent()
        answer = await agent.run(
            question=body.question,
            project_filter=body.project_filter,
        )
    except Exception as e:
        logger.error("notion_ask_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Project assistant failed: {e}")

    return {"answer": answer}


# ---------------------------------------------------------------------------
# Daily digest trigger
# ---------------------------------------------------------------------------

@router.post("/digest/daily")
async def trigger_daily_digest() -> dict:
    """
    Trigger the daily pruner digest pipeline.
    Called by Make.com on a daily schedule.
    Runs the Daily Pruner Agent, saves to Supabase, and delivers via Postmark.
    """
    logger.info("notion_digest_daily_trigger")

    try:
        service = DigestService()
        result = await service.run_daily_digest()
    except DigestServiceError as e:
        logger.error("notion_digest_daily_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Daily digest failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Weekly digest trigger
# ---------------------------------------------------------------------------

@router.post("/digest/weekly")
async def trigger_weekly_digest() -> dict:
    """
    Trigger the weekly review digest pipeline.
    Called by Make.com on a weekly schedule.
    Runs the Weekly Reviewer Agent, saves to Supabase, and delivers via Postmark.
    """
    logger.info("notion_digest_weekly_trigger")

    try:
        service = DigestService()
        result = await service.run_weekly_digest()
    except DigestServiceError as e:
        logger.error("notion_digest_weekly_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Weekly digest failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Scorecard write
# ---------------------------------------------------------------------------

@router.post("/scorecard")
async def write_scorecard(body: ScorecardRequest) -> dict:
    """
    Compute EOS scorecard metrics and write a new entry to the Notion Scorecard DB.
    Called by Make.com weekly after aggregating REIReply and OpenPhone data.
    """
    logger.info("notion_scorecard_trigger", week_label=body.week_label)

    try:
        service = ScorecardService()
        result = await service.run(
            reireply_data=body.reireply_data,
            openphone_data=body.openphone_data,
            week_label=body.week_label,
        )
    except ScorecardServiceError as e:
        logger.error("notion_scorecard_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Scorecard write failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Page summary helper
# ---------------------------------------------------------------------------

def _summarize_page(page: dict) -> dict:
    """
    Extract a flat summary dict from a Notion Items DB page object.

    Args:
        page: A raw Notion page object from the API.

    Returns:
        Flat dict with title, status, priority, assignee, project, and due date.
    """
    props = page.get("properties", {})

    def title() -> str:
        try:
            return "".join(
                p["plain_text"] for p in props["Name"]["title"]
            ).strip() or "Untitled"
        except (KeyError, TypeError):
            return "Untitled"

    def select(key: str) -> Optional[str]:
        try:
            return props[key]["select"]["name"]
        except (KeyError, TypeError):
            return None

    def rich_text(key: str) -> Optional[str]:
        try:
            return "".join(
                p["plain_text"] for p in props[key]["rich_text"]
            ).strip() or None
        except (KeyError, TypeError):
            return None

    def date(key: str) -> Optional[str]:
        try:
            return props[key]["date"]["start"]
        except (KeyError, TypeError):
            return None

    return {
        "notion_page_id": page.get("id"),
        "title": title(),
        "status": select("Status"),
        "priority": select("Priority"),
        "item_type": select("Item Type"),
        "source": select("Source"),
        "assignee": rich_text("Assignee"),
        "project": rich_text("Project"),
        "due_date": date("Due Date"),
        "last_edited": page.get("last_edited_time"),
    }
