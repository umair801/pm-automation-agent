"""
Tests for FastAPI webhook and capture endpoints.
Validates payload parsing, routing, and response codes for all capture sources.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def postmark_payload() -> dict:
    return {
        "MessageID": "msg-001",
        "From": "sender@example.com",
        "To": "inbound@datawebify.com",
        "Subject": "Follow up on project Alpha",
        "TextBody": "Please review the deliverables by Friday.",
        "HtmlBody": "<p>Please review the deliverables by Friday.</p>",
        "Date": "2026-04-29T10:00:00Z",
        "ReplyTo": "sender@example.com",
    }


@pytest.fixture
def groupme_payload() -> dict:
    return {
        "id": "gm-msg-001",
        "text": "Can someone handle the hospital report today?",
        "name": "Sarah",
        "user_id": "user_001",
        "group_id": "group_001",
        "created_at": 1714380000,
        "sender_type": "user",
        "source": "groupme",
    }


@pytest.fixture
def groupme_bot_payload() -> dict:
    return {
        "id": "gm-msg-002",
        "text": "I am a bot reply.",
        "name": "BotUser",
        "user_id": "bot_001",
        "group_id": "group_001",
        "created_at": 1714380001,
        "sender_type": "bot",
        "source": "groupme",
    }


@pytest.fixture
def openphone_payload() -> dict:
    return {
        "id": "op-event-001",
        "type": "message.received",
        "data": {
            "from": "+14155559876",
            "to": "+14155550000",
            "body": "Confirming our meeting tomorrow at 10am.",
        },
        "created_at": "2026-04-29T10:00:00Z",
        "source": "openphone",
    }


@pytest.fixture
def raycast_payload() -> dict:
    return {
        "text": "Review Q2 budget proposal before Monday",
        "source": "raycast",
        "tags": ["budget", "review"],
        "project_hint": "Finance",
    }


@pytest.fixture
def granola_payload() -> dict:
    return {
        "meeting_id": "gran-001",
        "title": "Weekly Sync",
        "transcript": "We discussed the deployment timeline and agreed to ship by end of month.",
        "attendees": ["Alice", "Bob", "Charlie"],
        "started_at": "2026-04-29T09:00:00Z",
        "ended_at": "2026-04-29T09:45:00Z",
        "source": "granola",
    }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def mock_capture_pipeline(return_value: dict):
    """Patch the full capture pipeline so no real agents or APIs are called."""
    return patch(
        "app.api.capture._run_capture_pipeline",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def mock_audit_log():
    """Patch SupabaseClient.write_audit_log for webhook endpoint tests."""
    return patch(
        "app.api.webhooks.SupabaseClient.write_audit_log",
        new_callable=AsyncMock,
        return_value=None,
    )


def mock_dev_env():
    """Override APP_ENV to development to bypass signature verification in tests."""
    mock_settings = MagicMock()
    mock_settings.APP_ENV = "development"
    mock_settings.SLACK_SIGNING_SECRET = "test_secret"
    mock_settings.OPENPHONE_WEBHOOK_SECRET = "test_secret"
    return patch("app.api.webhooks.settings", mock_settings)


CAPTURE_RESPONSE = {
    "status": "captured",
    "source": "test",
    "notion_page_id": "page-001",
    "item_type": "action_item",
    "priority_level": "high",
    "title": "Test item",
}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health check endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_is_healthy(self, client: TestClient) -> None:
        """Health check should return status: healthy."""
        response = client.get("/health")
        assert response.json()["status"] == "healthy"

    def test_health_has_brand(self, client: TestClient) -> None:
        """Health check should include Datawebify brand field."""
        response = client.get("/health")
        assert response.json()["brand"] == "Datawebify"

    def test_health_project_name(self, client: TestClient) -> None:
        """Health check project field should reflect PM Automation Agent."""
        response = client.get("/health")
        assert "PM Automation Agent" in response.json()["project"]


# ---------------------------------------------------------------------------
# GroupMe webhook
# ---------------------------------------------------------------------------

class TestGroupMeWebhook:

    def test_groupme_user_message_accepted(
        self, client: TestClient, groupme_payload: dict
    ) -> None:
        """GroupMe user message should return 200 with status received."""
        with mock_audit_log():
            response = client.post("/webhooks/groupme", json=groupme_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_groupme_bot_message_ignored(
        self, client: TestClient, groupme_bot_payload: dict
    ) -> None:
        """GroupMe bot messages should be ignored, not processed."""
        response = client.post("/webhooks/groupme", json=groupme_bot_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert response.json()["reason"] == "bot_message"

    def test_groupme_response_source(
        self, client: TestClient, groupme_payload: dict
    ) -> None:
        """GroupMe webhook response should identify source as groupme."""
        with mock_audit_log():
            response = client.post("/webhooks/groupme", json=groupme_payload)
        assert response.json()["source"] == "groupme"


# ---------------------------------------------------------------------------
# OpenPhone webhook
# ---------------------------------------------------------------------------

class TestOpenPhoneWebhook:

    def test_openphone_accepted_in_development(
        self, client: TestClient, openphone_payload: dict
    ) -> None:
        """
        OpenPhone webhook should return 200 in development mode
        (signature verification is skipped when APP_ENV=development).
        """
        with mock_dev_env(), mock_audit_log():
            response = client.post("/webhooks/openphone", json=openphone_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_openphone_returns_event_type(
        self, client: TestClient, openphone_payload: dict
    ) -> None:
        """OpenPhone response should echo back the event type."""
        with mock_dev_env(), mock_audit_log():
            response = client.post("/webhooks/openphone", json=openphone_payload)
        assert response.json()["event_type"] == "message.received"

    def test_openphone_response_source(
        self, client: TestClient, openphone_payload: dict
    ) -> None:
        """OpenPhone webhook response should identify source as openphone."""
        with mock_dev_env(), mock_audit_log():
            response = client.post("/webhooks/openphone", json=openphone_payload)
        assert response.json()["source"] == "openphone"


# ---------------------------------------------------------------------------
# Slack webhook
# ---------------------------------------------------------------------------

class TestSlackWebhook:

    def test_slack_url_verification(self, client: TestClient) -> None:
        """Slack URL verification challenge should be echoed back."""
        payload = {
            "type": "url_verification",
            "challenge": "test_challenge_string_abc123",
            "token": "test_token",
        }
        with mock_dev_env():
            response = client.post("/webhooks/slack", json=payload)
        assert response.status_code == 200
        assert response.json()["challenge"] == "test_challenge_string_abc123"

    def test_slack_event_callback_accepted(self, client: TestClient) -> None:
        """Slack event_callback should return 200 in development mode."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "api_app_id": "A123",
            "event": {
                "type": "message",
                "text": "Deploy the new build today",
                "user": "U123",
            },
        }
        with mock_dev_env(), mock_audit_log():
            response = client.post("/webhooks/slack", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "received"


# ---------------------------------------------------------------------------
# Capture endpoints
# ---------------------------------------------------------------------------

class TestCaptureEndpoints:

    def test_postmark_capture_accepted(
        self, client: TestClient, postmark_payload: dict
    ) -> None:
        """Postmark capture endpoint should return 200 with captured status."""
        with mock_capture_pipeline(CAPTURE_RESPONSE):
            response = client.post("/capture/postmark", json=postmark_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "captured"

    def test_raycast_capture_accepted(
        self, client: TestClient, raycast_payload: dict
    ) -> None:
        """Raycast capture endpoint should return 200 with captured status."""
        with mock_capture_pipeline(CAPTURE_RESPONSE):
            response = client.post("/capture/raycast", json=raycast_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "captured"

    def test_granola_capture_accepted(
        self, client: TestClient, granola_payload: dict
    ) -> None:
        """Granola capture endpoint should return 200 with captured status."""
        with mock_capture_pipeline(CAPTURE_RESPONSE):
            response = client.post("/capture/granola", json=granola_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "captured"

    def test_capture_response_has_notion_page_id(
        self, client: TestClient, raycast_payload: dict
    ) -> None:
        """Capture response should include notion_page_id field."""
        with mock_capture_pipeline(CAPTURE_RESPONSE):
            response = client.post("/capture/raycast", json=raycast_payload)
        assert "notion_page_id" in response.json()

    def test_capture_response_has_priority_level(
        self, client: TestClient, raycast_payload: dict
    ) -> None:
        """Capture response should include priority_level field."""
        with mock_capture_pipeline(CAPTURE_RESPONSE):
            response = client.post("/capture/raycast", json=raycast_payload)
        assert "priority_level" in response.json()

    def test_postmark_missing_required_field_returns_422(
        self, client: TestClient
    ) -> None:
        """Postmark payload missing MessageID should return 422."""
        bad_payload = {
            "From": "sender@example.com",
            "To": "inbound@datawebify.com",
            "Subject": "Test",
        }
        response = client.post("/capture/postmark", json=bad_payload)
        assert response.status_code == 422

    def test_granola_missing_transcript_returns_422(
        self, client: TestClient
    ) -> None:
        """Granola payload missing transcript should return 422."""
        bad_payload = {
            "meeting_id": "gran-001",
            "title": "Sync",
            "source": "granola",
        }
        response = client.post("/capture/granola", json=bad_payload)
        assert response.status_code == 422
