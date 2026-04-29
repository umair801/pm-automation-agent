"""
Pydantic models for project management triage and priority data structures.
Used by the Triage Agent and Prioritizer Agent.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ItemType(str, Enum):
    """Classification of the captured item."""
    ACTION_ITEM = "action_item"
    DECISION = "decision"
    QUESTION = "question"
    FYI = "fyi"
    MEETING_NOTE = "meeting_note"
    SOP_UPDATE = "sop_update"
    SCORECARD_UPDATE = "scorecard_update"
    UNKNOWN = "unknown"


class CaptureSource(str, Enum):
    """The source system that produced the item."""
    GMAIL = "gmail"
    HOSPITAL_EMAIL = "hospital_email"
    GROUPME = "groupme"
    SLACK = "slack"
    GOOGLE_CALENDAR = "google_calendar"
    OPENPHONE = "openphone"
    ASANA = "asana"
    REIREPLY = "reireply"
    POSTMARK = "postmark"
    TWILIO = "twilio"
    RAYCAST = "raycast"
    IOS_VOICE_MEMO = "ios_voice_memo"
    GRANOLA = "granola"
    UNKNOWN = "unknown"


class PriorityLevel(str, Enum):
    """Four-level priority scale assigned by the Prioritizer Agent."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Triage models
# ---------------------------------------------------------------------------

class TriageResult(BaseModel):
    """
    Output produced by the Triage Agent for a single captured item.
    Identifies what the item is, where it came from, and what it is about.
    """

    item_type: ItemType = Field(..., description="Classified item type")
    source: CaptureSource = Field(..., description="Originating capture source")
    title: str = Field(..., description="Short generated title for the item (max 80 chars)")
    summary: str = Field(..., description="One to two sentence summary of the item content")
    project_hint: Optional[str] = Field(None, description="Project name extracted or inferred from content")
    assignee_hint: Optional[str] = Field(None, description="Person name extracted or inferred from content")
    due_date_hint: Optional[str] = Field(None, description="Due date extracted from content, ISO 8601 if present")
    tags: list[str] = Field(default_factory=list, description="Relevant tags extracted from content")
    raw_content: str = Field(..., description="Original unmodified content passed to the agent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent confidence score for the classification")


# ---------------------------------------------------------------------------
# Priority models
# ---------------------------------------------------------------------------

class PriorityDimension(BaseModel):
    """A single scoring dimension used by the Prioritizer Agent."""

    score: int = Field(..., ge=0, le=10, description="Score from 0 to 10")
    reasoning: str = Field(..., description="Why this score was assigned")


class PriorityResult(BaseModel):
    """
    Output produced by the Prioritizer Agent for a single triage result.
    Scores urgency and importance independently, then assigns a final level.
    """

    urgency: PriorityDimension = Field(..., description="Time sensitivity of the item")
    importance: PriorityDimension = Field(..., description="Business impact of the item")
    total_score: int = Field(..., ge=0, le=20, description="Sum of urgency and importance scores")
    priority_level: PriorityLevel = Field(..., description="Final assigned priority level")
    reasoning: str = Field(..., description="Overall reasoning for the assigned priority level")


# ---------------------------------------------------------------------------
# Combined pipeline model
# ---------------------------------------------------------------------------

class TriagePipelineResult(BaseModel):
    """
    Full result after both the Triage Agent and Prioritizer Agent have run.
    This is what gets written to the Notion Items DB.
    """

    triage: TriageResult
    priority: PriorityResult
    notion_page_id: Optional[str] = Field(None, description="Notion page ID after write, populated post-insert")
