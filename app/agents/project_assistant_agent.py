"""
Project Assistant Agent.
On-demand Q&A against the Notion workspace.
Answers natural language questions grounded in live Notion data.
"""

import structlog
from typing import Any, Optional
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.clients.notion_client import NotionClient, NotionClientError

logger = structlog.get_logger(__name__)

# Maximum number of pages fetched per database for context building.
# Keeps token usage predictable on large workspaces.
MAX_ITEMS_PER_DB = 50

SYSTEM_PROMPT = """
You are a project assistant agent with read-only access to a Notion workspace.
Your job is to answer questions about the current state of projects, tasks,
decisions, people, and SOPs based strictly on the context provided to you.

Rules:
- Only use information present in the provided context. Never invent project state.
- If the answer is not in the context, say so clearly and suggest where the user might find it.
- Be concise. Prefer bullet points for lists of items.
- When referencing items, include their title, status, and assignee where available.
- Do not speculate about future outcomes or decisions not recorded in the workspace.
- If the question is ambiguous, answer the most likely interpretation and note the ambiguity.
""".strip()


class ProjectAssistantAgent:
    """
    Answers natural language questions about the Notion workspace.
    Fetches live context from Items, Projects, Decisions, and SOPs DBs.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()
        self._notion = NotionClient()

    async def run(
        self,
        question: str,
        project_filter: Optional[str] = None,
    ) -> str:
        """
        Answer a natural language question using live Notion workspace context.

        Args:
            question: The user's natural language question.
            project_filter: Optional project name to scope the context query.

        Returns:
            A plain text answer grounded in the Notion workspace.

        Raises:
            NotionClientError: If any Notion DB query fails.
            ClaudeClientError: If the Claude API call fails.
        """
        logger.info(
            "project_assistant_start",
            question_length=len(question),
            project_filter=project_filter,
        )

        context = await self._build_context(project_filter)

        if not context.strip():
            return (
                "I was unable to find any relevant content in the Notion workspace "
                "to answer your question. The workspace may be empty or the filter "
                "returned no results."
            )

        user_message = (
            f"Question: {question}\n\n"
            f"Workspace context:\n{context}"
        )

        try:
            answer = await self._claude.call(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=1024,
                temperature=0.2,
                metadata={"agent": "project_assistant", "project_filter": project_filter},
            )
        except ClaudeClientError:
            logger.error("project_assistant_claude_error")
            raise

        logger.info("project_assistant_complete", answer_length=len(answer))
        return answer

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    async def _build_context(self, project_filter: Optional[str]) -> str:
        """
        Fetch and format context from all relevant Notion databases.

        Args:
            project_filter: Optional project name to scope item queries.

        Returns:
            A plain-text context block for inclusion in the Claude prompt.
        """
        sections: list[str] = []

        # Items DB
        try:
            item_filter: Optional[dict] = None
            if project_filter:
                item_filter = {
                    "property": "Project",
                    "rich_text": {"contains": project_filter},
                }
            items = await self._notion.query_items(
                filter_payload=item_filter,
                page_size=MAX_ITEMS_PER_DB,
            )
            if items:
                sections.append("## Active Items\n" + _format_items(items))
        except NotionClientError as e:
            logger.warning("project_assistant_items_error", error=str(e))

        # Projects DB
        try:
            project_filter_payload: Optional[dict] = None
            if project_filter:
                project_filter_payload = {
                    "property": "Name",
                    "title": {"contains": project_filter},
                }
            projects = await self._notion.query_projects(
                filter_payload=project_filter_payload,
                page_size=MAX_ITEMS_PER_DB,
            )
            if projects:
                sections.append("## Projects\n" + _format_pages(projects))
        except NotionClientError as e:
            logger.warning("project_assistant_projects_error", error=str(e))

        # Decisions DB
        try:
            decisions = await self._notion.query_decisions(
                page_size=MAX_ITEMS_PER_DB,
            )
            if decisions:
                sections.append("## Decisions\n" + _format_pages(decisions))
        except NotionClientError as e:
            logger.warning("project_assistant_decisions_error", error=str(e))

        # SOPs DB
        try:
            sops = await self._notion.query_sops(
                page_size=MAX_ITEMS_PER_DB,
            )
            if sops:
                sections.append("## SOPs\n" + _format_pages(sops))
        except NotionClientError as e:
            logger.warning("project_assistant_sops_error", error=str(e))

        return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_items(pages: list[dict[str, Any]]) -> str:
    """
    Format a list of Items DB pages into a readable plain-text block.

    Args:
        pages: List of Notion page objects from the Items DB.

    Returns:
        A plain-text formatted string of item entries.
    """
    lines: list[str] = []
    for page in pages:
        props = page.get("properties", {})
        title = _extract_title_prop(props)
        status = _extract_select(props, "Status") or "Unknown"
        priority = _extract_select(props, "Priority") or "Unknown"
        assignee = _extract_rich_text_prop(props, "Assignee") or "Unassigned"
        project = _extract_rich_text_prop(props, "Project") or "No Project"
        due = _extract_date(props, "Due Date") or "No due date"
        lines.append(
            f"- [{priority}] {title} | Project: {project} | "
            f"Status: {status} | Assignee: {assignee} | Due: {due}"
        )
    return "\n".join(lines)


def _format_pages(pages: list[dict[str, Any]]) -> str:
    """
    Format a generic list of Notion pages by title only.

    Args:
        pages: List of Notion page objects.

    Returns:
        A plain-text bullet list of page titles.
    """
    lines: list[str] = []
    for page in pages:
        props = page.get("properties", {})
        title = _extract_title_prop(props)
        lines.append(f"- {title}")
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


def _extract_date(props: dict, key: str) -> str | None:
    """Extract the start date string from a Notion date property."""
    try:
        return props[key]["date"]["start"]
    except (KeyError, TypeError):
        return None
