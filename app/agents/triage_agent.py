"""
Triage Agent.
Classifies incoming captured items by type, extracts key metadata,
and returns a validated TriageResult. First agent in the pipeline.
"""

import structlog
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.models.qualification import (
    TriageResult,
    ItemType,
    CaptureSource,
)

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """
You are a triage agent for a project management system.
Your job is to analyze a captured item and extract structured metadata from it.

You must return ONLY a valid JSON object with no preamble, no explanation, and no markdown fences.

The JSON must contain exactly these fields:

{
  "item_type": one of ["action_item", "decision", "question", "fyi", "meeting_note", "sop_update", "scorecard_update", "unknown"],
  "title": a short descriptive title, maximum 80 characters,
  "summary": one to two sentences summarizing what the item is about,
  "project_hint": the project name if mentioned or inferable, or null,
  "assignee_hint": the person name if mentioned or inferable, or null,
  "due_date_hint": a due date in ISO 8601 format if mentioned, or null,
  "tags": an array of short relevant tags (max 5), or an empty array,
  "confidence": a float from 0.0 to 1.0 representing your classification confidence
}

Rules:
- Be conservative with confidence. Use 0.9+ only when the item type is completely unambiguous.
- Extract assignee_hint from phrases like "assign to", "cc:", "for X to handle", or direct name mentions.
- Extract project_hint from explicit project names, folder names, or strong contextual clues.
- Extract due_date_hint from phrases like "by Friday", "EOD", "before the 15th". Convert to ISO 8601 using today's date as reference if needed.
- Tags should be lowercase, single words or short hyphenated phrases.
- Never invent information not present or strongly inferable from the content.
""".strip()


class TriageAgent:
    """
    Classifies a captured item and extracts structured metadata.
    Uses Claude via ClaudeClient with JSON-only output mode.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()

    async def run(
        self,
        raw_content: str,
        source: CaptureSource,
    ) -> TriageResult:
        """
        Run triage classification on a single captured item.

        Args:
            raw_content: The raw text content of the captured item.
            source: The CaptureSource enum value identifying where it came from.

        Returns:
            A validated TriageResult Pydantic model.

        Raises:
            ClaudeClientError: If the Claude API call fails.
            ValueError: If the response cannot be parsed into TriageResult.
        """
        logger.info("triage_agent_start", source=source.value, content_length=len(raw_content))

        user_message = f"Source: {source.value}\n\nContent:\n{raw_content}"

        try:
            result_dict = await self._claude.call_with_json_output(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=512,
                temperature=0.1,
                metadata={"agent": "triage", "source": source.value},
            )
        except ClaudeClientError:
            logger.error("triage_agent_claude_error", source=source.value)
            raise

        try:
            triage_result = TriageResult(
                item_type=ItemType(result_dict.get("item_type", "unknown")),
                source=source,
                title=result_dict.get("title", "Untitled Item"),
                summary=result_dict.get("summary", ""),
                project_hint=result_dict.get("project_hint"),
                assignee_hint=result_dict.get("assignee_hint"),
                due_date_hint=result_dict.get("due_date_hint"),
                tags=result_dict.get("tags", []),
                raw_content=raw_content,
                confidence=float(result_dict.get("confidence", 0.5)),
            )
        except Exception as e:
            logger.error("triage_agent_parse_error", error=str(e), raw=result_dict)
            raise ValueError(f"Failed to parse triage result: {e}") from e

        logger.info(
            "triage_agent_complete",
            item_type=triage_result.item_type.value,
            confidence=triage_result.confidence,
            title=triage_result.title,
        )
        return triage_result
