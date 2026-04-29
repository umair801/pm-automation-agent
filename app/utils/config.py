"""
Application configuration loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """All application settings loaded from .env file."""

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key for Claude agents")

    # Notion
    NOTION_API_KEY: str = Field(..., description="Notion integration token")
    NOTION_ITEMS_DB_ID: str = Field(..., description="Notion Items database ID")
    NOTION_PROJECTS_DB_ID: str = Field(..., description="Notion Projects database ID")
    NOTION_PEOPLE_DB_ID: str = Field(..., description="Notion People database ID")
    NOTION_DECISIONS_DB_ID: str = Field(..., description="Notion Decisions database ID")
    NOTION_SOPS_DB_ID: str = Field(..., description="Notion SOPs database ID")
    NOTION_SCORECARD_DB_ID: str = Field(..., description="Notion Scorecard database ID")

    # Supabase
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_KEY: str = Field(..., description="Supabase anon/service key")

    # Postmark
    POSTMARK_INBOUND_TOKEN: str = Field(..., description="Postmark inbound webhook token")

    # Twilio
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio account SID")
    TWILIO_AUTH_TOKEN: str = Field(..., description="Twilio auth token")
    TWILIO_PHONE_NUMBER: str = Field(..., description="Twilio sending phone number")

    # OpenPhone
    OPENPHONE_WEBHOOK_SECRET: str = Field(..., description="OpenPhone webhook signing secret")

    # GroupMe
    GROUPME_BOT_ID: str = Field(..., description="GroupMe bot ID for webhook verification")

    # Slack
    SLACK_SIGNING_SECRET: str = Field(..., description="Slack signing secret for request verification")

    # OpenAI (Whisper only)
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key used exclusively for Whisper transcription")

    # App
    APP_ENV: str = Field(default="development")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
