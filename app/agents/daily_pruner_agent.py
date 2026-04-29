"""
Daily Pruner Agent.
Identifies stale and duplicate items in the Notion Items DB and
returns structured recommendations. Does not modify Notion directly.
Triggered by Make.com on a daily schedule.
"""

import structlog
from typing import Any
from datetime import datetime, timezone
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.clients.notion_client import NotionClient, NotionClientError

logger = structlog.get_logger(__name__)

# Items not updated within this many days are considered stale candidates.
STALE_THRESHOLD_DAYS = 7

SYSTEM_PROMPT = """
You are a daily pruner agent for a project management system.
Your job is to review a list of potentially stale or duplicate work items
and recommend an action for each one.

You must return ONLY a valid JSON array with no preamble, no explanation, and no markdown fences.

Each element in the array must be an object with exactly these fields:

{
  "item_id": the Notion page ID string as provided,
  "title": the item title as provided,
  "recommended_action": one of ["archive", "merge", "keep"],
  "reason": one sentence explaining the recommendation,
  "merge_target_id": the Notion page ID of the item to merge into, or null if not applicable
}

Rules:
- Recommend "archive" if the item appears abandoned, completed with no status update, or fully superseded.
- Recommend "merge" if the item is clearly a duplicate or near-duplicate of another item in the list.
  Set merge_target_id to the page ID of the item that should be kept.
- Recommend "keep" if the item is legitimately stale but still relevant and actionable.
- Never recommend archive for critical or high priority items unless they are clear duplicates.
- Be conservative. When in doubt, recommend "keep".
- Return an empty array [] if no action is needed for any item.
""".strip()


class DailyPrunerAgent:
    """
    Flags stale and duplicate items in the Notion Items DB.
    Returns recommendations without modifying Notion directly.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()
        self._notion = NotionClient()

    async def run(self) -> list[dict[str, Any]]:
        """
        Identify stale and duplicate items and return pruning recommendations.

        Returns:
            A list of recommendation dicts, each containing:
                - item_id (str)
                - title (str)
                - recommended_action (str): "archive", "merge", or "keep"
                - reason (str)
                - merge_target_id (str or None)

        Raises:
            NotionClientError: If the Items DB cannot be queried.
            ClaudeClientError: If the Claude API call fails.
        """
        logger.info("daily_pruner_agent_start")

        try:
            items = await self._notion.query_items(
                filter_payload={
                    "and": [
                        {
                            "property": "Status",
                            "status": {"does_not_equal": "Archived"},
                        },
                        {
                            "property": "Status",
                            "status": {"does_not_equal": "Done"},
                        },
                    ]
                },
                sorts=[{"timestamp": "last_edited_time", "direction": "ascending"}],
                page_size=100,
            )
        except NotionClientError as e:
            logger.error("daily_pruner_notion_error", error=str(e))
            raise

        if not items:
            logger.info("daily_pruner_no_items")
            return []

        # Filter to stale candidates only
        stale_items = _filter_stale(items, STALE_THRESHOLD_DAYS)

        if not stale_items:
            logger.info(
                "daily_pruner_no_stale_items",
                total_items=len(items),
                threshold_days=STALE_THRESHOLD_DAYS,
            )
            return []

        logger.info(
            "daily_pruner_stale_found",
            stale_count=len(stale_items),
            total_items=len(items),
        )

        snapshot = _build_pruner_snapshot(stale_items)

        try:
            result = await self._claude.call_with_json_output(
                system_prompt=SYSTEM_PROMPT,
                user_message=f"Items to review:\n\n{snapshot}",
                max_tokens=2048,
                temperature=0.1,
                metadata={
                    "agent": "daily_pruner",
                    "stale_count": len(stale_items),
                },
            )
        except ClaudeClientError:
            logger.error("daily_pruner_claude_error")
            raise

        # Claude returns a list directly; handle both list and dict-wrapped responses
        if isinstance(result, dict):
            recommendations = result.get("recommendations", result.get("items", []))
        elif isinstance(result, list):
            recommendations = result
        else:
            logger.warning("daily_pruner_unexpected_response_type", result_type=type(result).__name__)
            recommendations = []

        logger.info(
            "daily_pruner_agent_complete",
            recommendation_count=len(recommendations),
        )
        return recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter_stale(
    items: list[dict[str, Any]],
    threshold_days: int,
) -> list[dict[str, Any]]:
    """
    Filter Notion pages to those not edited within the threshold window.

    Args:
        items: List of Notion page objects.
        threshold_days: Number of days without an edit to qualify as stale.

    Returns:
        Filtered list of stale Notion page objects.
    """
    now = datetime.now(timezone.utc)
    stale: list[dict[str, Any]] = []

    for page in items:
        last_edited_raw = page.get("last_edited_time", "")
        try:
            last_edited = datetime.fromisoformat(
                last_edited_raw.replace("Z", "+00:00")
            )
            days_since_edit = (now - last_edited).days
            if days_since_edit >= threshold_days:
                stale.append(page)
        except (ValueError, AttributeError):
            # If we cannot parse the timestamp, include it as a stale candidate.
            stale.append(page)

    return stale


def _build_pruner_snapshot(items: list[dict[str, Any]]) -> str:
    """
    Build a plain-text snapshot of stale items for Claude to review.

    Args:
        items: List of stale Notion page objects.

    Returns:
        A plain-text snapshot string with one item per block.
    """
    lines: list[str] = []

    for page in items:
        props = page.get("properties", {})
        page_id = page.get("id", "unknown")

        title = _extract_title_prop(props)
        status = _extract_select(props, "Status") or "Unknown"
        priority = _extract_select(props, "Priority") or "Unknown"
        assignee = _extract_rich_text_prop(props, "Assignee") or "Unassigned"
        last_edited = page.get("last_edited_time", "Unknown")

        lines.append(
            f"ID: {page_id}\n"
            f"Title: {title}\n"
            f"Status: {status}\n"
            f"Priority: {priority}\n"
            f"Assignee: {assignee}\n"
            f"Last edited: {last_edited}\n"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Notion property extraction helpers
# ---------------------------------------------------------------------------

def _extract_title_prop(props: dict) -> str:
    """Extract plain text from a Notion title property."""
    try:
        parts = props["Name"]["title"]
        return "".join(p["plain_text"] for p in parts).strip() or "Untitled"
    except (KeyError, TypeError):
        return "Untitled"


def _extract_select(props: dict, key: str) -> str | None:
    """Extract the name value from a Notion select property."""
    try:
        return props[key]["select"]["name"]
    except (KeyError, TypeError):
        return None


def _extract_rich_text_prop(props: dict, key: str) -> str | None:
    """Extract plain text from a Notion rich_text property."""
    try:
        parts = props[key]["rich_text"]
        return "".join(p["plain_text"] for p in parts).strip() or None
    except (KeyError, TypeError):
        return None
