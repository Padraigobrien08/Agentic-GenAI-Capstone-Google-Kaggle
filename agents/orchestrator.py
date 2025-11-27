# agents/orchestrator.py

from typing import List, Optional

from core.llm import LLMClient
from core.models import (
    ConversationTrace,
    JudgeResult,
    QaReport,
    TrajectoryAnalysis,
    compute_overall_quality_score,
)
from memory.store import MemoryStore

from .judge import JudgeAgent
from .prompt_rewriter import PromptRewriter
from .trajectory_inspector import TrajectoryInspector


class QaOrchestrator:
    """Orchestrates the QA pipeline: inspection, judgment, and prompt improvement."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        memory_store: Optional[MemoryStore] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize the QA orchestrator.

        Args:
            llm_client: Optional LLM client. If None, creates a new one.
            memory_store: Optional memory store. If None, creates a new one.
            session_id: Optional session ID to group memory entries. If None, will be
                       derived from trace metadata or conversation_id when writing entries.
        """
        self.llm_client = llm_client or LLMClient()
        self.memory_store = memory_store or MemoryStore()
        self.session_id = session_id

        # Initialize agents
        self.trajectory_inspector = TrajectoryInspector()
        self.judge_agent = JudgeAgent(self.llm_client)
        self.prompt_rewriter = PromptRewriter(
            self.llm_client, memory=self.memory_store
        )

    def run_analysis(self, trace: ConversationTrace) -> QaReport:
        """
        Run the complete QA analysis pipeline.

        Args:
            trace: The conversation trace to analyze

        Returns:
            QaReport with trajectory analysis, judgment, and prompt improvement
        """
        # Step 1: Analyze trajectory
        trajectory = self.trajectory_inspector.analyze(trace)

        # Step 2: Judge the conversation
        judgment = self.judge_agent.judge(trace, trajectory)

        # Step 2.5: Filter out false positive MISSING_KEY_TERMS if judge scores perfect
        trajectory = self._filter_false_positive_missing_terms(trajectory, judgment)

        # Step 3: Get original system prompt from trace metadata
        original_prompt = trace.metadata.get(
            "system_prompt", "No system prompt provided."
        )

        # Step 4: Load memory snippets based on detected issues
        # Use issue codes from judgment to find relevant snippets
        # Note: We store entries with a session_id, but retrieval is still primarily
        # by issue_codes (session-agnostic). This keeps the memory layer "framework-agnostic".
        issue_codes = judgment.issues
        memory_snippets = self.memory_store.get_snippets_for_issues(issue_codes)
        # Fallback to general snippets if no issue-specific ones found
        if not memory_snippets:
            memory_snippets = self.memory_store.get_snippets(limit=5)

        # Step 5: Rewrite the prompt (with memory snippets)
        prompt_improvement = self.prompt_rewriter.rewrite(
            original_prompt=original_prompt,
            judge_result=judgment,
            memory_snippets=memory_snippets if memory_snippets else None,
        )

        # Step 6: Update memory with the analysis
        # Extract agent name from trace metadata
        agent_name = trace.metadata.get("agent_name", "unknown_agent")
        # Collect all issue codes from judgment
        all_issue_codes = judgment.issues
        
        # Extract 1-2 meaningful lines from the improved prompt as helpful snippets
        helpful_snippets = self._extract_helpful_snippets(
            prompt_improvement.improved_prompt, prompt_improvement.changes_explained
        )

        # Derive effective session_id: use orchestrator's session_id, or trace metadata, or conversation_id
        effective_session_id = (
            self.session_id
            or trace.metadata.get("session_id")
            or trace.conversation_id
        )

        self.memory_store.add_analysis(
            agent_name=agent_name,
            issue_codes=all_issue_codes,
            helpful_snippets=helpful_snippets,
            session_id=effective_session_id,
        )

        # Step 7: Compute overall quality score
        overall_score = compute_overall_quality_score(judgment.scores)

        # Step 8: Return the complete report
        return QaReport(
            trajectory=trajectory,
            judgment=judgment,
            prompt_improvement=prompt_improvement,
            overall_score=overall_score,
        )

    def _extract_helpful_snippets(
        self, improved_prompt: str, changes_explained: List[str]
    ) -> List[str]:
        """
        Extract 1-2 short lines from improved_prompt containing strong rules.

        Filters to lines containing strong rules (e.g. "MUST", "NEVER", "refuse", "safety")
        and returns up to 2 lines, stripped of whitespace.

        Args:
            improved_prompt: The full improved prompt
            changes_explained: List of changes that were made (unused, kept for compatibility)

        Returns:
            List of 1-2 short, useful prompt snippets with strong rules
        """
        snippets = []
        
        # Split improved_prompt into lines
        lines = improved_prompt.split("\n")
        
        # Filter to lines containing strong rules
        strong_rule_keywords = [
            "MUST",
            "NEVER",
            "refuse",
            "safety",
            "must not",
            "do not",
            "always",
            "required",
            "never",
            "avoid",
            "ignore",
            "don't know",
            "I don't know",
        ]
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, very short lines, or very long lines
            if not line or len(line) < 20 or len(line) > 200:
                continue
            
            # Check if line contains strong rule keywords
            line_lower = line.lower()
            if any(keyword.lower() in line_lower for keyword in strong_rule_keywords):
                snippets.append(line)
                if len(snippets) >= 2:
                    break
        
        # If we didn't find enough strong rule lines, take first substantial lines
        if len(snippets) < 2:
            for line in lines:
                line = line.strip()
                if line and 20 <= len(line) <= 200 and line not in snippets:
                    snippets.append(line)
                    if len(snippets) >= 2:
                        break
        
        return snippets[:2]  # Return at most 2 snippets

    def _filter_false_positive_missing_terms(
        self,
        trajectory: TrajectoryAnalysis,
        judgment: JudgeResult,
    ) -> TrajectoryAnalysis:
        """
        Removes MISSING_KEY_TERMS issues when the judge scores the run as
        perfectly successful and correct. This prevents noisy false positives
        from the simple keyword heuristic.
        """
        scores = judgment.scores
        if scores.task_success == 5 and scores.correctness == 5:
            trajectory.issues = [
                issue
                for issue in trajectory.issues
                if issue.code != "MISSING_KEY_TERMS"
            ]
        return trajectory

