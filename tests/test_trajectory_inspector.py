# tests/test_trajectory_inspector.py

import pytest

from agents.trajectory_inspector import TrajectoryInspector
from core.models import ConversationTrace, TraceEvent


def test_trajectory_inspector_detects_repeated_tool_calls():
    """Test that TrajectoryInspector detects when the same tool is called multiple times with identical args."""
    # Create a trace with repeated tool calls
    events = [
        TraceEvent(role="user", content="What is the weather?"),
        TraceEvent(
            role="tool_call",
            tool_name="weather_api",
            args={"city": "New York", "state": "NY"},
        ),
        TraceEvent(
            role="tool_result",
            tool_name="weather_api",
            result={"temperature": "72°F"},
        ),
        TraceEvent(
            role="tool_call",
            tool_name="weather_api",
            args={"city": "New York", "state": "NY"},  # Same args as before
        ),
        TraceEvent(
            role="tool_result",
            tool_name="weather_api",
            result={"temperature": "72°F"},
        ),
        TraceEvent(
            role="tool_call",
            tool_name="weather_api",
            args={"city": "New York", "state": "NY"},  # Same args again
        ),
        TraceEvent(
            role="tool_result",
            tool_name="weather_api",
            result={"temperature": "72°F"},
        ),
        TraceEvent(role="assistant", content="The weather is 72°F."),
    ]

    trace = ConversationTrace(
        conversation_id="test_repeated_calls",
        events=events,
        metadata={},
    )

    # Run the inspector
    inspector = TrajectoryInspector()
    analysis = inspector.analyze(trace)

    # Assert that at least one issue with code "REPEATED_TOOL_CALL" is present
    repeated_issues = [
        issue for issue in analysis.issues if issue.code == "REPEATED_TOOL_CALL"
    ]
    assert len(repeated_issues) > 0, "Expected at least one REPEATED_TOOL_CALL issue"

    # Verify the issue details
    issue = repeated_issues[0]
    assert issue.code == "REPEATED_TOOL_CALL"
    assert "weather_api" in issue.description
    assert len(issue.step_indices) >= 2, "Expected at least 2 step indices for repeated calls"

