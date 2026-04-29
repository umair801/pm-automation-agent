"""
Notion API client wrapper.
Handles all read/write operations across the 6 Notion databases.
No agent or router calls the Notion SDK directly.
"""

import structlog
from typing import Any, Optional
from notion_client import AsyncClient
from notion_client.errors import APIResponseError
from app.utils.config import settings

logger = structlog.get_logger(__name__)


class NotionClientError(Exception):
    """Raised when a Notion API operation fails."""
    pass


class NotionClient:
    """
    Async wrapper around the notion-client SDK.
    Exposes typed read/write methods for each of the 6 Notion databases.
    """

    def __init__(self) -> None:
        self._client = AsyncClient(auth=settings.NOTION_API_KEY)

    # ------------------------------------------------------------------
    # ITEMS DB
    # ------------------------------------------------------------------

    async def create_item(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new page in the Items database.

        Args:
            properties: Notion property payload for the new page.

        Returns:
            The created Notion page object.
        """
        return await self._create_page(settings.NOTION_ITEMS_DB_ID, properties)

    async def update_item(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing page in the Items database.

        Args:
            page_id: The Notion page ID to update.
            properties: Partial property payload with updated values.

        Returns:
            The updated Notion page object.
        """
        return await self._update_page(page_id, properties)

    async def query_items(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        sorts: Optional[list[dict[str, Any]]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the Items database with optional filters and sorts.

        Args:
            filter_payload: Notion filter object.
            sorts: Notion sorts array.
            page_size: Number of results per page (max 100).

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_ITEMS_DB_ID,
            filter_payload=filter_payload,
            sorts=sorts,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # PROJECTS DB
    # ------------------------------------------------------------------

    async def query_projects(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the Projects database.

        Args:
            filter_payload: Optional Notion filter object.
            page_size: Number of results per page.

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_PROJECTS_DB_ID,
            filter_payload=filter_payload,
            page_size=page_size,
        )

    async def get_project_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """
        Find a project page by its title property.

        Args:
            name: The project name to search for.

        Returns:
            The first matching Notion page object, or None.
        """
        results = await self.query_projects(
            filter_payload={
                "property": "Name",
                "title": {"equals": name},
            }
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # PEOPLE DB
    # ------------------------------------------------------------------

    async def query_people(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the People database.

        Args:
            filter_payload: Optional Notion filter object.
            page_size: Number of results per page.

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_PEOPLE_DB_ID,
            filter_payload=filter_payload,
            page_size=page_size,
        )

    async def get_person_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """
        Find a person page by their name property.

        Args:
            name: The person's name to search for.

        Returns:
            The first matching Notion page object, or None.
        """
        results = await self.query_people(
            filter_payload={
                "property": "Name",
                "title": {"equals": name},
            }
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # DECISIONS DB
    # ------------------------------------------------------------------

    async def create_decision(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new page in the Decisions database.

        Args:
            properties: Notion property payload for the new page.

        Returns:
            The created Notion page object.
        """
        return await self._create_page(settings.NOTION_DECISIONS_DB_ID, properties)

    async def query_decisions(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the Decisions database.

        Args:
            filter_payload: Optional Notion filter object.
            page_size: Number of results per page.

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_DECISIONS_DB_ID,
            filter_payload=filter_payload,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # SOPS DB
    # ------------------------------------------------------------------

    async def query_sops(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the SOPs database.

        Args:
            filter_payload: Optional Notion filter object.
            page_size: Number of results per page.

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_SOPS_DB_ID,
            filter_payload=filter_payload,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # SCORECARD DB
    # ------------------------------------------------------------------

    async def create_scorecard_entry(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new page in the Scorecard database.

        Args:
            properties: Notion property payload for the new page.

        Returns:
            The created Notion page object.
        """
        return await self._create_page(settings.NOTION_SCORECARD_DB_ID, properties)

    async def query_scorecard(
        self,
        filter_payload: Optional[dict[str, Any]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query the Scorecard database.

        Args:
            filter_payload: Optional Notion filter object.
            page_size: Number of results per page.

        Returns:
            List of Notion page objects.
        """
        return await self._query_database(
            settings.NOTION_SCORECARD_DB_ID,
            filter_payload=filter_payload,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # GENERIC PAGE RETRIEVAL
    # ------------------------------------------------------------------

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """
        Retrieve a single Notion page by its ID.

        Args:
            page_id: The Notion page UUID.

        Returns:
            The Notion page object.
        """
        try:
            logger.info("notion_get_page", page_id=page_id)
            return await self._client.pages.retrieve(page_id=page_id)
        except APIResponseError as e:
            logger.error("notion_get_page_error", page_id=page_id, error=str(e))
            raise NotionClientError(f"Failed to retrieve page {page_id}: {e}") from e

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    async def _create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a new page in any Notion database.

        Args:
            database_id: Target Notion database ID.
            properties: Notion-formatted property payload.

        Returns:
            The created Notion page object.
        """
        try:
            logger.info("notion_create_page", database_id=database_id)
            response = await self._client.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )
            logger.info("notion_page_created", page_id=response.get("id"))
            return response
        except APIResponseError as e:
            logger.error("notion_create_page_error", database_id=database_id, error=str(e))
            raise NotionClientError(f"Failed to create page in {database_id}: {e}") from e

    async def _update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update properties on an existing Notion page.

        Args:
            page_id: The Notion page UUID.
            properties: Partial Notion-formatted property payload.

        Returns:
            The updated Notion page object.
        """
        try:
            logger.info("notion_update_page", page_id=page_id)
            response = await self._client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info("notion_page_updated", page_id=page_id)
            return response
        except APIResponseError as e:
            logger.error("notion_update_page_error", page_id=page_id, error=str(e))
            raise NotionClientError(f"Failed to update page {page_id}: {e}") from e

    async def _query_database(
        self,
        database_id: str,
        filter_payload: Optional[dict[str, Any]] = None,
        sorts: Optional[list[dict[str, Any]]] = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query any Notion database and return all matching pages.
        Handles pagination automatically.

        Args:
            database_id: Target Notion database ID.
            filter_payload: Optional Notion filter object.
            sorts: Optional Notion sorts array.
            page_size: Results per page (max 100).

        Returns:
            Flat list of all matching Notion page objects.
        """
        try:
            logger.info("notion_query_database", database_id=database_id)

            kwargs: dict[str, Any] = {
                "database_id": database_id,
                "page_size": page_size,
            }
            if filter_payload:
                kwargs["filter"] = filter_payload
            if sorts:
                kwargs["sorts"] = sorts

            results: list[dict[str, Any]] = []
            has_more = True
            start_cursor: Optional[str] = None

            while has_more:
                if start_cursor:
                    kwargs["start_cursor"] = start_cursor

                response = await self._client.databases.query(**kwargs)
                results.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            logger.info(
                "notion_query_complete",
                database_id=database_id,
                result_count=len(results),
            )
            return results

        except APIResponseError as e:
            logger.error("notion_query_error", database_id=database_id, error=str(e))
            raise NotionClientError(f"Failed to query database {database_id}: {e}") from e
