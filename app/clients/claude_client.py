"""
Anthropic SDK client wrapper.
All six agents use this module exclusively to call the Claude API.
No agent instantiates the Anthropic SDK directly.
"""

import structlog
from typing import Any, Optional
from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError
from app.utils.config import settings

logger = structlog.get_logger(__name__)

# Single model string used across all agents.
# Change here to update every agent at once.
CLAUDE_MODEL = "claude-sonnet-4-20250514"


class ClaudeClientError(Exception):
    """Raised when a Claude API call fails after retries."""
    pass


class ClaudeClient:
    """
    Async wrapper around the Anthropic SDK.
    Provides a single structured_call method used by all agents.
    """

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Send a single-turn prompt to Claude and return the text response.

        Args:
            system_prompt: The agent-specific system instructions.
            user_message: The user-turn content (item text, context, etc.).
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature. Keep low (0.0-0.3) for agents.
            metadata: Optional dict logged alongside the call for tracing.

        Returns:
            The assistant text response as a plain string.

        Raises:
            ClaudeClientError: On API errors or empty responses.
        """
        log = logger.bind(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            **(metadata or {}),
        )

        try:
            log.info("claude_call_start")

            response = await self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            if not response.content:
                raise ClaudeClientError("Claude returned an empty response.")

            text = response.content[0].text
            log.info(
                "claude_call_success",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text

        except APIConnectionError as e:
            log.error("claude_connection_error", error=str(e))
            raise ClaudeClientError(f"Claude API connection failed: {e}") from e

        except APIStatusError as e:
            log.error("claude_status_error", status_code=e.status_code, error=str(e))
            raise ClaudeClientError(f"Claude API error {e.status_code}: {e.message}") from e

    async def call_with_json_output(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Call Claude and parse the response as JSON.
        The system prompt must instruct the model to return only valid JSON.

        Args:
            system_prompt: Must include an explicit instruction to return only JSON.
            user_message: The user-turn content.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            metadata: Optional dict logged alongside the call for tracing.

        Returns:
            Parsed JSON response as a Python dict.

        Raises:
            ClaudeClientError: On API errors or JSON parse failures.
        """
        import json

        raw = await self.call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=metadata,
        )

        try:
            # Strip markdown code fences if the model wraps the JSON
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            logger.error("claude_json_parse_error", raw_response=raw, error=str(e))
            raise ClaudeClientError(f"Failed to parse Claude JSON response: {e}") from e
