"""
Digest service.
Orchestrates daily and weekly digest generation, persistence, and delivery.
Calls WeeklyReviewerAgent and DailyPrunerAgent, saves results to Supabase,
and delivers via Postmark email.
"""

import httpx
import structlog
from datetime import datetime, timezone
from typing import Any

from app.agents.weekly_reviewer_agent import WeeklyReviewerAgent
from app.agents.daily_pruner_agent import DailyPrunerAgent
from app.clients.supabase_client import SupabaseClient
from app.utils.config import settings

logger = structlog.get_logger(__name__)

# Postmark transactional email endpoint
POSTMARK_API_URL = "https://api.postmarkapp.com/email"

# Digest delivery recipient — update to the client's email address
DIGEST_RECIPIENT = "team@example.com"
DIGEST_SENDER = "digest@datawebify.com"


class DigestServiceError(Exception):
    """Raised when digest generation or delivery fails."""
    pass


class DigestService:
    """
    Orchestrates digest generation, Supabase persistence, and Postmark delivery.
    Supports two digest types: 'daily' (pruner report) and 'weekly' (review digest).
    """

    def __init__(self) -> None:
        self._db = SupabaseClient()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def run_daily_digest(self) -> dict[str, Any]:
        """
        Run the daily pruner digest pipeline.

        Steps:
            1. Run DailyPrunerAgent to get stale item recommendations.
            2. Format recommendations into a readable email body.
            3. Save digest to Supabase pm_digests table.
            4. Deliver via Postmark.

        Returns:
            Dict with keys: digest_type, item_count, delivered, saved_id.

        Raises:
            DigestServiceError: If generation or delivery fails.
        """
        logger.info("digest_service_daily_start")

        try:
            recommendations = await DailyPrunerAgent().run()
        except Exception as e:
            raise DigestServiceError(f"Daily pruner agent failed: {e}") from e

        body_markdown = _format_pruner_digest(recommendations)
        subject = f"Daily Pruner Report — {_today_str()}"

        return await self._persist_and_deliver(
            digest_type="daily",
            subject=subject,
            body_markdown=body_markdown,
            item_count=len(recommendations),
        )

    async def run_weekly_digest(self) -> dict[str, Any]:
        """
        Run the weekly review digest pipeline.

        Steps:
            1. Run WeeklyReviewerAgent to get the markdown digest.
            2. Save digest to Supabase pm_digests table.
            3. Deliver via Postmark.

        Returns:
            Dict with keys: digest_type, item_count, delivered, saved_id.

        Raises:
            DigestServiceError: If generation or delivery fails.
        """
        logger.info("digest_service_weekly_start")

        try:
            body_markdown = await WeeklyReviewerAgent().run()
        except Exception as e:
            raise DigestServiceError(f"Weekly reviewer agent failed: {e}") from e

        subject = f"Weekly Project Digest — {_today_str()}"

        return await self._persist_and_deliver(
            digest_type="weekly",
            subject=subject,
            body_markdown=body_markdown,
            item_count=None,
        )

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    async def _persist_and_deliver(
        self,
        digest_type: str,
        subject: str,
        body_markdown: str,
        item_count: int | None,
    ) -> dict[str, Any]:
        """
        Save the digest to Supabase and deliver it via Postmark.

        Args:
            digest_type: 'daily' or 'weekly'.
            subject: Email subject line.
            body_markdown: Markdown body of the digest.
            item_count: Number of items in the digest, or None if not applicable.

        Returns:
            Dict with delivery result metadata.
        """
        # Persist to Supabase
        digest_record: dict[str, Any] = {
            "digest_type": digest_type,
            "subject": subject,
            "body": body_markdown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if item_count is not None:
            digest_record["item_count"] = item_count

        try:
            saved = await self._db.save_digest(digest_record)
            saved_id = saved.get("id")
            logger.info("digest_saved_to_supabase", digest_type=digest_type, saved_id=saved_id)
        except Exception as e:
            logger.error("digest_save_error", error=str(e))
            saved_id = None

        # Deliver via Postmark
        delivered = False
        try:
            await _send_postmark_email(
                subject=subject,
                body_text=body_markdown,
                to_email=DIGEST_RECIPIENT,
                from_email=DIGEST_SENDER,
                token=settings.POSTMARK_INBOUND_TOKEN,
            )
            delivered = True
            logger.info("digest_delivered", digest_type=digest_type, recipient=DIGEST_RECIPIENT)
        except Exception as e:
            logger.error("digest_delivery_error", error=str(e))

        await self._db.write_audit_log(
            event_type=f"{digest_type}_digest_run",
            source="digest_service",
            status="delivered" if delivered else "saved_only",
            payload={
                "subject": subject,
                "item_count": item_count,
                "delivered": delivered,
            },
        )

        return {
            "digest_type": digest_type,
            "item_count": item_count,
            "delivered": delivered,
            "saved_id": saved_id,
        }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_pruner_digest(recommendations: list[dict[str, Any]]) -> str:
    """
    Format DailyPrunerAgent recommendations into a readable markdown digest.

    Args:
        recommendations: List of recommendation dicts from DailyPrunerAgent.

    Returns:
        Markdown-formatted digest string.
    """
    if not recommendations:
        return (
            f"# Daily Pruner Report — {_today_str()}\n\n"
            "No stale or duplicate items found today. Workspace is clean."
        )

    lines = [f"# Daily Pruner Report — {_today_str()}\n"]
    lines.append(f"**{len(recommendations)} item(s) flagged for review.**\n")

    archive = [r for r in recommendations if r.get("recommended_action") == "archive"]
    merge = [r for r in recommendations if r.get("recommended_action") == "merge"]
    keep = [r for r in recommendations if r.get("recommended_action") == "keep"]

    if archive:
        lines.append("## Recommended: Archive")
        for r in archive:
            lines.append(f"- **{r.get('title', 'Untitled')}** — {r.get('reason', '')}")
        lines.append("")

    if merge:
        lines.append("## Recommended: Merge")
        for r in merge:
            lines.append(
                f"- **{r.get('title', 'Untitled')}** — {r.get('reason', '')} "
                f"(merge into: `{r.get('merge_target_id', 'unknown')}`)"
            )
        lines.append("")

    if keep:
        lines.append("## Flagged but Keep")
        for r in keep:
            lines.append(f"- **{r.get('title', 'Untitled')}** — {r.get('reason', '')}")
        lines.append("")

    return "\n".join(lines)


def _today_str() -> str:
    """Return today's date as a readable string."""
    return datetime.now(timezone.utc).strftime("%B %d, %Y")


# ---------------------------------------------------------------------------
# Postmark delivery
# ---------------------------------------------------------------------------

async def _send_postmark_email(
    subject: str,
    body_text: str,
    to_email: str,
    from_email: str,
    token: str,
) -> None:
    """
    Send a plain-text email via the Postmark transactional API.

    Args:
        subject: Email subject line.
        body_text: Plain text body (markdown rendered as text).
        to_email: Recipient email address.
        from_email: Sender email address (must be verified in Postmark).
        token: Postmark server API token.

    Raises:
        DigestServiceError: If the Postmark API returns a non-200 status.
    """
    payload = {
        "From": from_email,
        "To": to_email,
        "Subject": subject,
        "TextBody": body_text,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            POSTMARK_API_URL,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": token,
            },
        )

    if response.status_code != 200:
        raise DigestServiceError(
            f"Postmark delivery failed: {response.status_code} — {response.text}"
        )
