# core/models.py

from datetime import datetime
from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, Field


Role = Literal["user", "assistant", "tool_call", "tool_result", "system"]


class TraceEvent(BaseModel):
    """Single event in an agent run."""

    role: Role
    content: Optional[str] = None          # user / assistant / system text
    tool_name: Optional[str] = None        # for tool_call / tool_result
    args: Optional[Dict[str, Any]] = None  # for tool_call
    result: Optional[Any] = None           # for tool_result
    timestamp: Optional[str] = None        # ISO timestamp (optional)


class ConversationTrace(BaseModel):
    """Full trace of one agent run."""

    conversation_id: str
    events: List[TraceEvent]
    metadata: Dict[str, Any] = {}


class Session(BaseModel):
    """
    Lightweight representation of an agent session.

    This is NOT a full runtime session object, just metadata we can use
    to group traces, analyses, and memory entries.
    """

    session_id: str
    agent_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    trace_ids: List[str] = Field(default_factory=list)


class TrajectoryIssue(BaseModel):
    code: str
    description: str
    step_indices: List[int]


class TrajectoryAnalysis(BaseModel):
    """Output of TrajectoryInspector."""

    ordered_events: List[TraceEvent]
    issues: List[TrajectoryIssue]
    summary: str


class ScoreBreakdown(BaseModel):
    task_success: int
    correctness: int
    helpfulness: int
    safety: int
    efficiency: int


class JudgeResult(BaseModel):
    """Output of Judge Agent (LLM-as-a-judge)."""

    scores: ScoreBreakdown
    issues: List[str]
    rationale: str


def compute_overall_quality_score(scores: ScoreBreakdown) -> float:
    """
    Compute a single overall quality score on a 0–5 scale from the
    five individual dimensions using a weighted average:

    - task_success:  0.25
    - correctness:   0.25
    - safety:        0.20
    - helpfulness:   0.15
    - efficiency:    0.15
    """
    return (
        0.25 * scores.task_success
        + 0.25 * scores.correctness
        + 0.20 * scores.safety
        + 0.15 * scores.helpfulness
        + 0.15 * scores.efficiency
    )


class PromptImprovement(BaseModel):
    improved_prompt: str
    changes_explained: List[str]


class QaRequest(BaseModel):
    """Request model for QA analysis."""

    trace: ConversationTrace
    session_id: Optional[str] = None


class QaReport(BaseModel):
    """Final combined report."""

    trajectory: TrajectoryAnalysis
    judgment: JudgeResult
    prompt_improvement: PromptImprovement
    overall_score: float

