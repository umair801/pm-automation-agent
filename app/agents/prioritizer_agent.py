"""
Prioritizer Agent.
Scores a triaged item on urgency and importance, then assigns
a final PriorityLevel. Second agent in the pipeline.
"""

import structlog
from app.clients.claude_client import ClaudeClient, ClaudeClientError
from app.models.qualification import (
    PriorityResult,
    PriorityDimension,
    PriorityLevel,
    TriageResult,
)

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """
You are a prioritization agent for a project management system.
Your job is to score a captured and triaged item on two dimensions: urgency and importance.

You must return ONLY a valid JSON object with no preamble, no explanation, and no markdown fences.

The JSON must contain exactly these fields:

{
  "urgency": {
    "score": integer from 0 to 10,
    "reasoning": one sentence explaining the urgency score
  },
  "importance": {
    "score": integer from 0 to 10,
    "reasoning": one sentence explaining the importance score
  },
  "total_score": integer from 0 to 20 (sum of urgency and importance),
  "priority_level": one of ["critical", "high", "medium", "low"],
  "reasoning": one to two sentences summarizing the overall priority decision
}

Scoring rules:
- Urgency (time sensitivity): 0 = no deadline, 10 = must be done immediately or consequences are severe.
- Importance (business impact): 0 = trivial, 10 = directly affects revenue, operations, or key relationships.
- Priority level mapping:
    17-20 = critical
    12-16 = high
    7-11  = medium
    0-6   = low
- total_score must equal urgency.score + importance.score exactly.
- Never assign critical unless both urgency and importance are genuinely high (>=8 each).
""".strip()


class PrioritizerAgent:
    """
    Scores a TriageResult on urgency and importance and assigns a PriorityLevel.
    Uses Claude via ClaudeClient with JSON-only output mode.
    """

    def __init__(self) -> None:
        self._claude = ClaudeClient()

    async def run(self, triage_result: TriageResult) -> PriorityResult:
        """
        Run prioritization scoring on a triaged item.

        Args:
            triage_result: The validated TriageResult from the Triage Agent.

        Returns:
            A validated PriorityResult Pydantic model.

        Raises:
            ClaudeClientError: If the Claude API call fails.
            ValueError: If the response cannot be parsed into PriorityResult.
        """
        logger.info(
            "prioritizer_agent_start",
            item_type=triage_result.item_type.value,
            title=triage_result.title,
        )

        user_message = (
            f"Item type: {triage_result.item_type.value}\n"
            f"Source: {triage_result.source.value}\n"
            f"Title: {triage_result.title}\n"
            f"Summary: {triage_result.summary}\n"
            f"Due date hint: {triage_result.due_date_hint or 'none'}\n"
            f"Tags: {', '.join(triage_result.tags) if triage_result.tags else 'none'}\n\n"
            f"Original content:\n{triage_result.raw_content}"
        )

        try:
            result_dict = await self._claude.call_with_json_output(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=512,
                temperature=0.1,
                metadata={"agent": "prioritizer", "item_type": triage_result.item_type.value},
            )
        except ClaudeClientError:
            logger.error("prioritizer_agent_claude_error", title=triage_result.title)
            raise

        try:
            urgency_raw = result_dict.get("urgency", {})
            importance_raw = result_dict.get("importance", {})

            priority_result = PriorityResult(
                urgency=PriorityDimension(
                    score=int(urgency_raw.get("score", 0)),
                    reasoning=urgency_raw.get("reasoning", ""),
                ),
                importance=PriorityDimension(
                    score=int(importance_raw.get("score", 0)),
                    reasoning=importance_raw.get("reasoning", ""),
                ),
                total_score=int(result_dict.get("total_score", 0)),
                priority_level=PriorityLevel(result_dict.get("priority_level", "low")),
                reasoning=result_dict.get("reasoning", ""),
            )
        except Exception as e:
            logger.error("prioritizer_agent_parse_error", error=str(e), raw=result_dict)
            raise ValueError(f"Failed to parse priority result: {e}") from e

        logger.info(
            "prioritizer_agent_complete",
            priority_level=priority_result.priority_level.value,
            total_score=priority_result.total_score,
        )
        return priority_result
