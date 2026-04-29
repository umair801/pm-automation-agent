"""
Weekly Reviewer Agent.
Queries all active items from the Notion Items DB, groups them by project,
and generates a structured weekly digest. Triggered by Make.com on a schedule.
"""

import structlog
from typing import Any
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.clients.notion_client import NotionClient, NotionClientError

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """
You are a weekly review agent for a project management system.
Your job is to analyze a snapshot of all active work items grouped by project
and produce a concise, structured weekly digest in markdown format.

The digest must follow this exact structure:

# Weekly Digest

## Summary
One to three sentences giving the overall state of work across all projects.

## By Project

### [Project Name]
- **Completed this week:** bullet list of done items, or "None" if empty
- **In progress:** bullet list of active items with assignee in parentheses
- **Blocked:** bullet list of blocked items with reason, or "None" if empty
- **Needs attention:** bullet list of items that are overdue, unassigned, or critical priority

## Top Priorities for Next Week
Numbered list of the 3 to 5 most important items across all projects.

## Flags
Bullet list of anything that needs a human decision: unresolved blockers,
unassigned critical items, stale items older than 7 days, or conflicting priorities.
Write "None" if there are no flags.

Rules:
- Be concise. Each bullet should be one line.
- Do not invent items. Only use what is provided in the input.
- If a project has no active items, omit it from the By Project section.
- Preserve assignee names exactly as provided.
- Use plain markdown only. No HTML. No tables.
""".strip()


class WeeklyReviewerAgent:
    """
    Generates a weekly digest across all active Notion Items DB entries.
    Queries Notion directly and passes a structured snapshot to Claude.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()
        self._notion = NotionClient()

    async def run(self) -> str:
        """
        Generate the weekly digest.

        Returns:
            A markdown-formatted weekly digest string.

        Raises:
            NotionClientError: If the Items DB cannot be queried.
            ClaudeClientError: If the Claude API call fails.
        """
        logger.info("weekly_reviewer_agent_start")

        # Query all non-archived items from Notion
        try:
            items = await self._notion.query_items(
                filter_payload={
                    "property": "Status",
                    "status": {
                        "does_not_equal": "Archived",
                    },
                },
                sorts=[{"property": "Priority", "direction": "descending"}],
                page_size=100,
            )
        except NotionClientError as e:
            logger.error("weekly_reviewer_notion_error", error=str(e))
            raise

        if not items:
            logger.info("weekly_reviewer_no_items")
            return "# Weekly Digest\n\nNo active items found in the workspace this week."

        # Build grouped snapshot string for Claude
        snapshot = _build_snapshot(items)

        logger.info("weekly_reviewer_snapshot_built", item_count=len(items))

        try:
            digest = await self._claude.call(
                system_prompt=SYSTEM_PROMPT,
                user_message=f"Active items snapshot:\n\n{snapshot}",
                max_tokens=2048,
                temperature=0.3,
                metadata={"agent": "weekly_reviewer", "item_count": len(items)},
            )
        except ClaudeClientError:
            logger.error("weekly_reviewer_claude_error")
            raise

        logger.info("weekly_reviewer_agent_complete", digest_length=len(digest))
        return digest


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

def _build_snapshot(items: list[dict[str, Any]]) -> str:
    """
    Convert a flat list of Notion item pages into a grouped plain-text
    snapshot string organized by project for Claude to process.

    Args:
        items: List of Notion page objects from the Items DB.

    Returns:
        A plain-text snapshot string grouped by project name.
    """
    from collections import defaultdict

    grouped: dict[str, list[str]] = defaultdict(list)

    for page in items:
        props = page.get("properties", {})

        title = _extract_title_prop(props)
        status = _extract_select(props, "Status") or "Unknown"
        priority = _extract_select(props, "Priority") or "Unknown"
        assignee = _extract_rich_text_prop(props, "Assignee") or "Unassigned"
        project = _extract_rich_text_prop(props, "Project") or "No Project"
        due_date = _extract_date(props, "Due Date") or "No due date"
        blocked = _extract_checkbox(props, "Blocked")

        line = (
            f"  - [{priority}] {title} "
            f"| Status: {status} "
            f"| Assignee: {assignee} "
            f"| Due: {due_date}"
        )
        if blocked:
            line += " | BLOCKED"

        grouped[project].append(line)

    sections: list[str] = []
    for project, lines in sorted(grouped.items()):
        sections.append(f"Project: {project}")
        sections.extend(lines)
        sections.append("")

    return "\n".join(sections)


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


def _extract_date(props: dict, key: str) -> str | None:
    """Extract the start date string from a Notion date property."""
    try:
        return props[key]["date"]["start"]
    except (KeyError, TypeError):
        return None


def _extract_checkbox(props: dict, key: str) -> bool:
    """Extract the value of a Notion checkbox property."""
    try:
        return bool(props[key]["checkbox"])
    except (KeyError, TypeError):
        return False
