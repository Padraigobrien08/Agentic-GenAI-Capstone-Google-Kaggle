# api/service.py

from typing import Optional

from core.models import QaRequest, QaReport
from agents.orchestrator import QaOrchestrator


class QaService:
    """
    Lightweight service wrapper around QaOrchestrator.

    This allows Agent QA Mentor to be called as:

    - an HTTP API,
    - an internal microservice,
    - or from another agent (agent-to-agent call).
    """

    def __init__(self, orchestrator: Optional[QaOrchestrator] = None):
        """
        Initialize the QA service.

        Args:
            orchestrator: Optional QaOrchestrator instance. If None, creates a new one
                         when needed.
        """
        self.orchestrator = orchestrator

    def run_qa(self, request: QaRequest) -> QaReport:
        """
        Run QA analysis on the given trace and return a QaReport.

        If request.session_id is provided, it will be used; otherwise the
        orchestrator falls back to trace metadata or conversation_id.

        Args:
            request: QaRequest containing the trace and optional session_id

        Returns:
            QaReport with trajectory analysis, judgment, and prompt improvement
        """
        if self.orchestrator is not None:
            orch = self.orchestrator
            # If a session_id is provided on the request, override the orchestrator's session_id.
            if request.session_id is not None:
                orch.session_id = request.session_id
        else:
            orch = QaOrchestrator(session_id=request.session_id)

        return orch.run_analysis(request.trace)


# Optional FastAPI integration
try:
    from fastapi import FastAPI
except ImportError:
    FastAPI = None  # FastAPI is optional; the core library does not depend on it.


def create_app() -> "FastAPI":
    """
    Optional FastAPI app exposing Agent QA Mentor as an HTTP API.

    Usage:
        uvicorn api.service:create_app

    Returns:
        FastAPI application instance

    Raises:
        RuntimeError: If FastAPI is not installed
    """
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Please `pip install fastapi uvicorn`.")

    app = FastAPI(title="Agent QA Mentor", version="0.1.0")

    service = QaService()

    @app.post("/api/v1/qa", response_model=QaReport)
    def analyze(request: QaRequest) -> QaReport:
        """
        Analyze a conversation trace and return a QA report.

        Args:
            request: QaRequest containing the trace and optional session_id

        Returns:
            QaReport with analysis results
        """
        return service.run_qa(request)

    return app

