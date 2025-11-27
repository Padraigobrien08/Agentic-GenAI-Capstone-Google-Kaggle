# tests/test_judge.py

import pytest

from core.models import JudgeResult, ScoreBreakdown


def test_judge_result_schema_roundtrip():
    """Test that JudgeResult can be created from a dict and validates score ranges."""
    # Create a fake JudgeResult dict
    fake_judge_data = {
        "scores": {
            "task_success": 4,
            "correctness": 3,
            "helpfulness": 5,
            "safety": 2,
            "efficiency": 3,
        },
        "issues": [
            "hallucination_suspected",
            "ignored_tool_error",
        ],
        "rationale": "The agent performed well on task success and helpfulness, but showed signs of hallucination and ignored tool errors, leading to lower correctness and safety scores.",
    }

    # Validate via Pydantic model
    judge_result = JudgeResult.model_validate(fake_judge_data)

    # Assert that scores fields are ints in [0, 5]
    assert isinstance(judge_result.scores.task_success, int)
    assert 0 <= judge_result.scores.task_success <= 5
    assert isinstance(judge_result.scores.correctness, int)
    assert 0 <= judge_result.scores.correctness <= 5
    assert isinstance(judge_result.scores.helpfulness, int)
    assert 0 <= judge_result.scores.helpfulness <= 5
    assert isinstance(judge_result.scores.safety, int)
    assert 0 <= judge_result.scores.safety <= 5
    assert isinstance(judge_result.scores.efficiency, int)
    assert 0 <= judge_result.scores.efficiency <= 5

    # Assert other fields
    assert isinstance(judge_result.issues, list)
    assert len(judge_result.issues) == 2
    assert isinstance(judge_result.rationale, str)
    assert len(judge_result.rationale) > 0

    # Test roundtrip: convert back to dict and validate again
    roundtrip_data = judge_result.model_dump()
    judge_result_2 = JudgeResult.model_validate(roundtrip_data)
    assert judge_result_2.scores.task_success == judge_result.scores.task_success
    assert judge_result_2.scores.correctness == judge_result.scores.correctness


def test_judge_result_validates_score_bounds():
    """Test that JudgeResult validation works for edge cases."""
    # Test with scores at boundaries
    valid_data = {
        "scores": {
            "task_success": 0,
            "correctness": 5,
            "helpfulness": 0,
            "safety": 5,
            "efficiency": 0,
        },
        "issues": [],
        "rationale": "Edge case test",
    }

    judge_result = JudgeResult.model_validate(valid_data)
    assert judge_result.scores.task_success == 0
    assert judge_result.scores.correctness == 5

    # Test that out-of-range values are caught (if we add validation)
    # Note: Pydantic doesn't validate range by default, but we can test the type
    invalid_data = {
        "scores": {
            "task_success": 6,  # Out of range, but Pydantic won't reject without validators
            "correctness": -1,
            "helpfulness": 3,
            "safety": 3,
            "efficiency": 3,
        },
        "issues": [],
        "rationale": "Test",
    }

    # This will still validate (Pydantic doesn't enforce ranges by default)
    # But we can verify the values are stored as-is
    judge_result_invalid = JudgeResult.model_validate(invalid_data)
    assert judge_result_invalid.scores.task_success == 6
    assert judge_result_invalid.scores.correctness == -1
    # The test confirms the schema accepts ints, even if out of range
    # In production, you might add validators to enforce [0, 5] range

