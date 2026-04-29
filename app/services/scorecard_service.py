"""
Scorecard service.
Auto-populates the Notion Scorecard DB with EOS-style metrics
derived from REIReply CRM and OpenPhone call/SMS data.
Called on a schedule by Make.com via the /notion/scorecard endpoint.
"""

import structlog
from datetime import datetime, timezone
from typing import Any, Optional

from app.clients.notion_client import NotionClient, NotionClientError
from app.clients.supabase_client import SupabaseClient

logger = structlog.get_logger(__name__)


class ScorecardServiceError(Exception):
    """Raised when scorecard computation or Notion write fails."""
    pass


class ScorecardService:
    """
    Computes EOS-style scorecard metrics from REIReply and OpenPhone
    event payloads and writes a weekly entry to the Notion Scorecard DB.
    """

    def __init__(self) -> None:
        self._notion = NotionClient()
        self._db = SupabaseClient()

    async def run(
        self,
        reireply_data: Optional[dict[str, Any]] = None,
        openphone_data: Optional[dict[str, Any]] = None,
        week_label: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Compute metrics and write a Scorecard entry to Notion.

        Args:
            reireply_data: Raw summary payload from REIReply via Make.com.
                           Expected keys: leads_added, deals_closed,
                           follow_ups_sent, appointments_set.
            openphone_data: Raw summary payload from OpenPhone via Make.com.
                            Expected keys: calls_made, calls_answered,
                            sms_sent, voicemails_left, avg_call_duration_seconds.
            week_label: Human-readable week label, e.g. "2026-W18".
                        Defaults to the current ISO week if not provided.

        Returns:
            Dict with the created Notion page ID and computed metrics.

        Raises:
            ScorecardServiceError: If the Notion write fails.
        """
        if week_label is None:
            week_label = _current_week_label()

        logger.info("scorecard_service_start", week_label=week_label)

        metrics = _compute_metrics(
            reireply_data=reireply_data or {},
            openphone_data=openphone_data or {},
        )

        notion_properties = _build_notion_properties(
            week_label=week_label,
            metrics=metrics,
        )

        try:
            page = await self._notion.create_scorecard_entry(notion_properties)
            page_id = page.get("id")
            logger.info("scorecard_notion_entry_created", page_id=page_id, week_label=week_label)
        except NotionClientError as e:
            logger.error("scorecard_notion_error", error=str(e))
            raise ScorecardServiceError(f"Failed to write scorecard to Notion: {e}") from e

        await self._db.write_audit_log(
            event_type="scorecard_entry_created",
            source="scorecard_service",
            status="success",
            payload={"week_label": week_label, "metrics": metrics, "page_id": page_id},
        )

        return {
            "page_id": page_id,
            "week_label": week_label,
            "metrics": metrics,
        }


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def _compute_metrics(
    reireply_data: dict[str, Any],
    openphone_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute EOS-style scorecard metrics from raw REIReply and OpenPhone payloads.

    Args:
        reireply_data: Raw REIReply summary dict from Make.com.
        openphone_data: Raw OpenPhone summary dict from Make.com.

    Returns:
        Flat dict of computed metric values ready for Notion property mapping.
    """
    # REIReply metrics
    leads_added: int = int(reireply_data.get("leads_added", 0))
    deals_closed: int = int(reireply_data.get("deals_closed", 0))
    follow_ups_sent: int = int(reireply_data.get("follow_ups_sent", 0))
    appointments_set: int = int(reireply_data.get("appointments_set", 0))

    # OpenPhone metrics
    calls_made: int = int(openphone_data.get("calls_made", 0))
    calls_answered: int = int(openphone_data.get("calls_answered", 0))
    sms_sent: int = int(openphone_data.get("sms_sent", 0))
    voicemails_left: int = int(openphone_data.get("voicemails_left", 0))
    avg_call_duration_seconds: int = int(openphone_data.get("avg_call_duration_seconds", 0))

    # Derived metrics
    call_answer_rate: float = round(
        (calls_answered / calls_made * 100) if calls_made > 0 else 0.0, 1
    )
    avg_call_duration_minutes: float = round(avg_call_duration_seconds / 60, 1)

    return {
        # REIReply
        "leads_added": leads_added,
        "deals_closed": deals_closed,
        "follow_ups_sent": follow_ups_sent,
        "appointments_set": appointments_set,
        # OpenPhone
        "calls_made": calls_made,
        "calls_answered": calls_answered,
        "sms_sent": sms_sent,
        "voicemails_left": voicemails_left,
        "avg_call_duration_minutes": avg_call_duration_minutes,
        # Derived
        "call_answer_rate_pct": call_answer_rate,
    }


# ---------------------------------------------------------------------------
# Notion property builder
# ---------------------------------------------------------------------------

def _build_notion_properties(
    week_label: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the Notion property payload for a Scorecard DB page.

    Property names here must match the exact column names in the
    client's Notion Scorecard DB. Update if the schema changes.

    Args:
        week_label: ISO week label string, e.g. "2026-W18".
        metrics: Computed metrics dict from _compute_metrics.

    Returns:
        Notion-formatted properties dict ready for pages.create().
    """
    return {
        "Name": {
            "title": [{"text": {"content": f"Scorecard — {week_label}"}}]
        },
        "Week": {
            "rich_text": [{"text": {"content": week_label}}]
        },
        "Leads Added": {
            "number": metrics["leads_added"]
        },
        "Deals Closed": {
            "number": metrics["deals_closed"]
        },
        "Follow-Ups Sent": {
            "number": metrics["follow_ups_sent"]
        },
        "Appointments Set": {
            "number": metrics["appointments_set"]
        },
        "Calls Made": {
            "number": metrics["calls_made"]
        },
        "Calls Answered": {
            "number": metrics["calls_answered"]
        },
        "Call Answer Rate (%)": {
            "number": metrics["call_answer_rate_pct"]
        },
        "SMS Sent": {
            "number": metrics["sms_sent"]
        },
        "Voicemails Left": {
            "number": metrics["voicemails_left"]
        },
        "Avg Call Duration (min)": {
            "number": metrics["avg_call_duration_minutes"]
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_week_label() -> str:
    """
    Return the current ISO week label in YYYY-WWW format.

    Returns:
        Week label string, e.g. "2026-W18".
    """
    now = datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"
