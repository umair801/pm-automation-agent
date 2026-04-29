"""
Supabase database client.
Handles all read/write operations for captured items, audit logs,
agent results, and digest records.
"""

import structlog
from typing import Any, Optional
from supabase import create_client, Client
from app.utils.config import settings

logger = structlog.get_logger(__name__)


class SupabaseClientError(Exception):
    """Raised when a Supabase operation fails."""
    pass


class SupabaseClient:
    """Centralized Supabase database client for all pm_ table operations."""

    def __init__(self) -> None:
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
        )

    # ------------------------------------------------------------------
    # ITEMS
    # ------------------------------------------------------------------

    async def insert_item(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new captured item record into pm_items."""
        try:
            response = (
                self.client.table("pm_items")
                .insert(item_data)
                .execute()
            )
            logger.info("item_inserted", source=item_data.get("source"))
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error("item_insert_error", error=str(e))
            raise SupabaseClientError(f"Failed to insert item: {e}")

    async def get_item_by_id(self, item_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single item record by its UUID."""
        try:
            response = (
                self.client.table("pm_items")
                .select("*")
                .eq("id", item_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            logger.warning("item_not_found", item_id=item_id, error=str(e))
            return None

    async def update_item(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update specific fields on an item record."""
        try:
            response = (
                self.client.table("pm_items")
                .update(updates)
                .eq("id", item_id)
                .execute()
            )
            logger.info("item_updated", item_id=item_id)
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error("item_update_error", error=str(e))
            raise SupabaseClientError(f"Failed to update item: {e}")

    async def list_items(
        self,
        source: Optional[str] = None,
        priority_level: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List item records with optional filters.
        Used by the Daily Pruner and Weekly Reviewer agents.
        """
        try:
            query = self.client.table("pm_items").select("*")
            if source:
                query = query.eq("source", source)
            if priority_level:
                query = query.eq("priority_level", priority_level)
            response = query.limit(limit).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error("item_list_error", error=str(e))
            raise SupabaseClientError(f"Failed to list items: {e}")

    # ------------------------------------------------------------------
    # AGENT RESULTS
    # ------------------------------------------------------------------

    async def save_agent_result(self, result_data: dict[str, Any]) -> dict[str, Any]:
        """
        Persist the output of any agent run to pm_agent_results.
        Includes agent name, input reference, output payload, and status.
        """
        try:
            response = (
                self.client.table("pm_agent_results")
                .insert(result_data)
                .execute()
            )
            logger.info("agent_result_saved", agent=result_data.get("agent_name"))
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error("agent_result_save_error", error=str(e))
            raise SupabaseClientError(f"Failed to save agent result: {e}")

    # ------------------------------------------------------------------
    # DIGESTS
    # ------------------------------------------------------------------

    async def save_digest(self, digest_data: dict[str, Any]) -> dict[str, Any]:
        """Save a generated daily or weekly digest record to pm_digests."""
        try:
            response = (
                self.client.table("pm_digests")
                .insert(digest_data)
                .execute()
            )
            logger.info("digest_saved", digest_type=digest_data.get("digest_type"))
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error("digest_save_error", error=str(e))
            raise SupabaseClientError(f"Failed to save digest: {e}")

    async def get_latest_digest(self, digest_type: str) -> Optional[dict[str, Any]]:
        """Retrieve the most recent digest of a given type (daily or weekly)."""
        try:
            response = (
                self.client.table("pm_digests")
                .select("*")
                .eq("digest_type", digest_type)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error("digest_fetch_error", error=str(e))
            raise SupabaseClientError(f"Failed to fetch digest: {e}")

    # ------------------------------------------------------------------
    # AUDIT LOG
    # ------------------------------------------------------------------

    async def write_audit_log(
        self,
        event_type: str,
        source: str,
        status: str,
        item_id: Optional[str] = None,
        payload: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """Write an entry to the pm_audit_log table."""
        try:
            entry: dict[str, Any] = {
                "event_type": event_type,
                "source": source,
                "status": status,
            }
            if item_id:
                entry["item_id"] = item_id
            if payload:
                entry["payload"] = payload
            if error_message:
                entry["error_message"] = error_message

            response = (
                self.client.table("pm_audit_log")
                .insert(entry)
                .execute()
            )
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error("audit_log_error", error=str(e))
            raise SupabaseClientError(f"Failed to write audit log: {e}")
