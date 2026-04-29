"""
Delegator Agent.
Assigns a triaged and prioritized item to a person from the Notion People DB.
Third agent in the pipeline.
"""

import structlog
from typing import Optional
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.clients.notion_client import NotionClient, NotionClientError
from app.models.qualification import TriageResult, PriorityResult

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """
You are a delegation agent for a project management system.
Your job is to assign a captured work item to the most appropriate person from a provided team roster.

You must return ONLY a valid JSON object with no preamble, no explanation, and no markdown fences.

The JSON must contain exactly these fields:

{
  "assignee_name": the exact name string from the provided roster, or null if no suitable match exists,
  "confidence": a float from 0.0 to 1.0 representing your assignment confidence,
  "reasoning": one to two sentences explaining why this person was chosen
}

Rules:
- Only use names from the provided roster. Never invent names.
- If the item already has an assignee_hint, prefer that person if they appear in the roster.
- If no person is a good fit, return null for assignee_name and explain why in reasoning.
- Consider the item type, project hint, tags, and summary when making the assignment.
- If multiple people are equally suitable, prefer the one whose role or department best matches the item.
""".strip()


class DelegatorAgent:
    """
    Assigns a work item to a person from the Notion People DB.
    Fetches the live people roster from Notion before each call.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()
        self._notion = NotionClient()

    async def run(
        self,
        triage_result: TriageResult,
        priority_result: PriorityResult,
    ) -> dict:
        """
        Assign the item to a person from the People DB.

        Args:
            triage_result: The validated TriageResult from the Triage Agent.
            priority_result: The validated PriorityResult from the Prioritizer Agent.

        Returns:
            A dict with keys:
                - assignee_name (str or None)
                - assignee_notion_id (str or None)
                - confidence (float)
                - reasoning (str)

        Raises:
            NotionClientError: If the People DB cannot be queried.
            ClaudeClientError: If the Claude API call fails.
        """
        logger.info(
            "delegator_agent_start",
            title=triage_result.title,
            priority=priority_result.priority_level.value,
        )

        # Fetch live roster from Notion People DB
        try:
            people_pages = await self._notion.query_people()
        except NotionClientError as e:
            logger.error("delegator_agent_notion_error", error=str(e))
            raise

        # Build a name -> page_id map and a plain roster string for Claude
        people_map: dict[str, str] = {}
        roster_lines: list[str] = []

        for page in people_pages:
            name = _extract_title(page)
            page_id = page.get("id", "")
            role = _extract_rich_text(page, "Role")
            department = _extract_rich_text(page, "Department")

            if name:
                people_map[name] = page_id
                line = f"- {name}"
                if role:
                    line += f" | Role: {role}"
                if department:
                    line += f" | Department: {department}"
                roster_lines.append(line)

        if not roster_lines:
            logger.warning("delegator_agent_empty_roster")
            return {
                "assignee_name": None,
                "assignee_notion_id": None,
                "confidence": 0.0,
                "reasoning": "People DB is empty. No assignment made.",
            }

        roster_str = "\n".join(roster_lines)

        user_message = (
            f"Item type: {triage_result.item_type.value}\n"
            f"Priority: {priority_result.priority_level.value}\n"
            f"Title: {triage_result.title}\n"
            f"Summary: {triage_result.summary}\n"
            f"Project hint: {triage_result.project_hint or 'none'}\n"
            f"Assignee hint from content: {triage_result.assignee_hint or 'none'}\n"
            f"Tags: {', '.join(triage_result.tags) if triage_result.tags else 'none'}\n\n"
            f"Team roster:\n{roster_str}"
        )

        try:
            result_dict = await self._claude.call_with_json_output(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=256,
                temperature=0.1,
                metadata={"agent": "delegator", "title": triage_result.title},
            )
        except ClaudeClientError:
            logger.error("delegator_agent_claude_error", title=triage_result.title)
            raise

        assignee_name: Optional[str] = result_dict.get("assignee_name")
        assignee_notion_id: Optional[str] = None

        if assignee_name and assignee_name in people_map:
            assignee_notion_id = people_map[assignee_name]
        elif assignee_name:
            # Claude returned a name not in the roster (violation of rules).
            # Log and discard to avoid a bad relation write.
            logger.warning(
                "delegator_agent_unknown_assignee",
                returned_name=assignee_name,
                roster_names=list(people_map.keys()),
            )
            assignee_name = None

        logger.info(
            "delegator_agent_complete",
            assignee_name=assignee_name,
            confidence=result_dict.get("confidence"),
        )

        return {
            "assignee_name": assignee_name,
            "assignee_notion_id": assignee_notion_id,
            "confidence": float(result_dict.get("confidence", 0.0)),
            "reasoning": result_dict.get("reasoning", ""),
        }


# ---------------------------------------------------------------------------
# Notion property extraction helpers
# ---------------------------------------------------------------------------

def _extract_title(page: dict) -> Optional[str]:
    """Extract the plain text value of a Notion title property."""
    try:
        title_parts = page["properties"]["Name"]["title"]
        return "".join(part["plain_text"] for part in title_parts).strip() or None
    except (KeyError, TypeError):
        return None


def _extract_rich_text(page: dict, property_name: str) -> Optional[str]:
    """Extract the plain text value of a Notion rich_text property."""
    try:
        parts = page["properties"][property_name]["rich_text"]
        return "".join(part["plain_text"] for part in parts).strip() or None
    except (KeyError, TypeError):
        return None
