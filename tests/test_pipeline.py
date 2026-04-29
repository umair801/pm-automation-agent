"""
Tests for PM agent logic, models, and pipeline behavior.
Validates triage classification, priority scoring, and data model integrity.
"""

import pytest
from app.models.qualification import (
    TriageResult,
    PriorityResult,
    PriorityDimension,
    TriagePipelineResult,
    ItemType,
    CaptureSource,
    PriorityLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def map_score_to_priority(total_score: int) -> PriorityLevel:
    """
    Mirror the scoring thresholds defined in the Prioritizer Agent system prompt.
    17-20 = critical, 12-16 = high, 7-11 = medium, 0-6 = low.
    """
    if total_score >= 17:
        return PriorityLevel.CRITICAL
    elif total_score >= 12:
        return PriorityLevel.HIGH
    elif total_score >= 7:
        return PriorityLevel.MEDIUM
    else:
        return PriorityLevel.LOW


def make_triage_result(
    item_type: ItemType = ItemType.ACTION_ITEM,
    source: CaptureSource = CaptureSource.RAYCAST,
    title: str = "Test item",
    summary: str = "A test summary.",
    confidence: float = 0.9,
    tags: list[str] | None = None,
    project_hint: str | None = None,
    assignee_hint: str | None = None,
    due_date_hint: str | None = None,
) -> TriageResult:
    """Build a TriageResult for use in tests."""
    return TriageResult(
        item_type=item_type,
        source=source,
        title=title,
        summary=summary,
        project_hint=project_hint,
        assignee_hint=assignee_hint,
        due_date_hint=due_date_hint,
        tags=tags or [],
        raw_content="Raw test content.",
        confidence=confidence,
    )


def make_priority_result(
    urgency: int = 8,
    importance: int = 8,
    priority_level: PriorityLevel = PriorityLevel.HIGH,
) -> PriorityResult:
    """Build a PriorityResult for use in tests."""
    return PriorityResult(
        urgency=PriorityDimension(score=urgency, reasoning="Test urgency reasoning."),
        importance=PriorityDimension(score=importance, reasoning="Test importance reasoning."),
        total_score=urgency + importance,
        priority_level=priority_level,
        reasoning="Test overall reasoning.",
    )


# ---------------------------------------------------------------------------
# Priority score mapping tests
# ---------------------------------------------------------------------------

class TestPriorityScoreMapping:

    def test_score_17_to_20_is_critical(self) -> None:
        """Scores 17 through 20 should map to critical."""
        for score in [17, 18, 19, 20]:
            assert map_score_to_priority(score) == PriorityLevel.CRITICAL

    def test_score_12_to_16_is_high(self) -> None:
        """Scores 12 through 16 should map to high."""
        for score in [12, 13, 14, 15, 16]:
            assert map_score_to_priority(score) == PriorityLevel.HIGH

    def test_score_7_to_11_is_medium(self) -> None:
        """Scores 7 through 11 should map to medium."""
        for score in [7, 8, 9, 10, 11]:
            assert map_score_to_priority(score) == PriorityLevel.MEDIUM

    def test_score_0_to_6_is_low(self) -> None:
        """Scores 0 through 6 should map to low."""
        for score in [0, 1, 3, 5, 6]:
            assert map_score_to_priority(score) == PriorityLevel.LOW

    def test_boundary_critical_high(self) -> None:
        """Score of exactly 17 should be critical, 16 should be high."""
        assert map_score_to_priority(17) == PriorityLevel.CRITICAL
        assert map_score_to_priority(16) == PriorityLevel.HIGH

    def test_boundary_high_medium(self) -> None:
        """Score of exactly 12 should be high, 11 should be medium."""
        assert map_score_to_priority(12) == PriorityLevel.HIGH
        assert map_score_to_priority(11) == PriorityLevel.MEDIUM

    def test_boundary_medium_low(self) -> None:
        """Score of exactly 7 should be medium, 6 should be low."""
        assert map_score_to_priority(7) == PriorityLevel.MEDIUM
        assert map_score_to_priority(6) == PriorityLevel.LOW

    def test_perfect_score_is_critical(self) -> None:
        """Maximum score of 20 should be critical."""
        assert map_score_to_priority(20) == PriorityLevel.CRITICAL

    def test_zero_score_is_low(self) -> None:
        """Minimum score of 0 should be low."""
        assert map_score_to_priority(0) == PriorityLevel.LOW


# ---------------------------------------------------------------------------
# TriageResult model tests
# ---------------------------------------------------------------------------

class TestTriageResultModel:

    def test_valid_triage_result(self) -> None:
        """TriageResult should store all fields correctly."""
        result = make_triage_result(
            item_type=ItemType.DECISION,
            source=CaptureSource.SLACK,
            title="Approve new vendor",
            confidence=0.85,
        )
        assert result.item_type == ItemType.DECISION
        assert result.source == CaptureSource.SLACK
        assert result.title == "Approve new vendor"
        assert result.confidence == 0.85

    def test_triage_result_defaults(self) -> None:
        """TriageResult tags should default to empty list."""
        result = make_triage_result()
        assert result.tags == []

    def test_triage_result_with_tags(self) -> None:
        """TriageResult should store tags list correctly."""
        result = make_triage_result(tags=["urgent", "finance"])
        assert "urgent" in result.tags
        assert "finance" in result.tags

    def test_triage_result_with_optional_hints(self) -> None:
        """TriageResult should store optional hint fields correctly."""
        result = make_triage_result(
            project_hint="Alpha",
            assignee_hint="Alice",
            due_date_hint="2026-05-01",
        )
        assert result.project_hint == "Alpha"
        assert result.assignee_hint == "Alice"
        assert result.due_date_hint == "2026-05-01"

    def test_triage_confidence_bounds(self) -> None:
        """TriageResult confidence must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            make_triage_result(confidence=1.5)

    def test_triage_result_requires_raw_content(self) -> None:
        """TriageResult should fail without raw_content."""
        with pytest.raises(Exception):
            TriageResult(
                item_type=ItemType.ACTION_ITEM,
                source=CaptureSource.RAYCAST,
                title="Test",
                summary="Test summary.",
                confidence=0.9,
            )

    def test_all_item_types_are_valid(self) -> None:
        """All ItemType enum values should be accepted by the model."""
        for item_type in ItemType:
            result = make_triage_result(item_type=item_type)
            assert result.item_type == item_type

    def test_all_capture_sources_are_valid(self) -> None:
        """All CaptureSource enum values should be accepted by the model."""
        for source in CaptureSource:
            result = make_triage_result(source=source)
            assert result.source == source


# ---------------------------------------------------------------------------
# PriorityResult model tests
# ---------------------------------------------------------------------------

class TestPriorityResultModel:

    def test_valid_priority_result(self) -> None:
        """PriorityResult should store urgency, importance, and total correctly."""
        result = make_priority_result(urgency=9, importance=8)
        assert result.urgency.score == 9
        assert result.importance.score == 8
        assert result.total_score == 17

    def test_total_score_equals_sum(self) -> None:
        """total_score should equal urgency + importance."""
        for u, i in [(5, 5), (10, 10), (3, 7), (0, 0)]:
            result = make_priority_result(urgency=u, importance=i)
            assert result.total_score == u + i

    def test_urgency_score_bounds(self) -> None:
        """Urgency score must be between 0 and 10."""
        with pytest.raises(Exception):
            PriorityResult(
                urgency=PriorityDimension(score=11, reasoning="Over limit"),
                importance=PriorityDimension(score=5, reasoning="Fine"),
                total_score=16,
                priority_level=PriorityLevel.HIGH,
                reasoning="Test",
            )

    def test_importance_score_bounds(self) -> None:
        """Importance score must be between 0 and 10."""
        with pytest.raises(Exception):
            PriorityResult(
                urgency=PriorityDimension(score=5, reasoning="Fine"),
                importance=PriorityDimension(score=-1, reasoning="Under limit"),
                total_score=4,
                priority_level=PriorityLevel.LOW,
                reasoning="Test",
            )

    def test_all_priority_levels_valid(self) -> None:
        """All PriorityLevel enum values should be accepted by the model."""
        for level in PriorityLevel:
            result = make_priority_result(priority_level=level)
            assert result.priority_level == level


# ---------------------------------------------------------------------------
# TriagePipelineResult combined model tests
# ---------------------------------------------------------------------------

class TestTriagePipelineResult:

    def test_pipeline_result_stores_both(self) -> None:
        """TriagePipelineResult should store both triage and priority results."""
        triage = make_triage_result()
        priority = make_priority_result()
        pipeline = TriagePipelineResult(triage=triage, priority=priority)
        assert pipeline.triage.title == "Test item"
        assert pipeline.priority.total_score == 16

    def test_pipeline_result_notion_id_defaults_none(self) -> None:
        """notion_page_id should default to None before Notion write."""
        triage = make_triage_result()
        priority = make_priority_result()
        pipeline = TriagePipelineResult(triage=triage, priority=priority)
        assert pipeline.notion_page_id is None

    def test_pipeline_result_notion_id_set(self) -> None:
        """notion_page_id should store the Notion page ID after write."""
        triage = make_triage_result()
        priority = make_priority_result()
        pipeline = TriagePipelineResult(
            triage=triage,
            priority=priority,
            notion_page_id="page-abc-123",
        )
        assert pipeline.notion_page_id == "page-abc-123"
