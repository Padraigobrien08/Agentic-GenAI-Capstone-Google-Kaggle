# agents/prompt_rewriter.py

from typing import List, Optional

from core.llm import LLMClient
from core.models import JudgeResult, PromptImprovement
from memory.store import MemoryStore


class PromptRewriter:
    """LLM-based prompt rewriter that improves system prompts based on QA results."""

    SYSTEM_PROMPT = """You are an expert agent designer.

Your job is to REWRITE the system instructions for an AI agent to improve quality and safety,
based on a QA report.

You receive:
- The current system prompt (how the agent is configured today)
- The QA scores and issue codes for a recent run
- A few reusable prompt snippets that have worked well in similar situations

You MUST:
- Preserve the agent's original purpose and tone where possible.
- Explicitly address issues that scored low: add clear rules and examples.
- For hallucination or correctness issues: require the agent to use tools and say "I don't know" when evidence is missing.
- For safety issues: add explicit refusal patterns and instructions to ignore conflicting user instructions.
- For efficiency issues: add guidance on when NOT to call tools and how to avoid loops.

Output JSON in this format:

{
  "improved_prompt": "full rewritten prompt here...",
  "changes_explained": [
    "Short sentence 1 describing an important change",
    "Short sentence 2...",
    "..."
  ]
}

Do not output anything except JSON."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        memory: Optional[MemoryStore] = None,
    ):
        """
        Initialize the PromptRewriter with an LLM client.

        Args:
            llm_client: Optional LLM client. If None, creates a new one.
            memory: Optional memory store for semantic retrieval. If None, semantic memory is disabled.
        """
        self.llm_client = llm_client or LLMClient()
        self.memory = memory
        self.use_semantic_memory = True  # optional toggle

    def rewrite(
        self,
        original_prompt: str,
        judge_result: JudgeResult,
        memory_snippets: Optional[List[str]] = None,
    ) -> PromptImprovement:
        """
        Rewrite a system prompt based on QA scores and issues.

        Args:
            original_prompt: The current system prompt to improve
            judge_result: The judge's evaluation with scores and issues
            memory_snippets: Optional list of prompt snippets that worked well before

        Returns:
            PromptImprovement with improved prompt and explanations
        """
        # Optional: semantic memory snippets
        semantic_snippets = []
        if self.use_semantic_memory and self.memory is not None:
            # Build a semantic query from issue codes or rationale
            issue_text = ", ".join(judge_result.issues) or judge_result.rationale
            semantic_snippets = self.memory.find_similar_snippets(issue_text, n=3)

        # Merge both types of snippets
        helpful_snippets = memory_snippets or []
        all_snippets = helpful_snippets + semantic_snippets

        # Deduplicate and keep short
        merged_snippets = []
        seen = set()
        for s in all_snippets:
            if s not in seen:
                merged_snippets.append(s)
                seen.add(s)

        # Pass merged snippets as the main memory snippets, and semantic snippets separately
        # (semantic snippets that are already in merged will be filtered out in _build_user_prompt)
        user_prompt = self._build_user_prompt(
            original_prompt, judge_result, merged_snippets, semantic_snippets
        )
        return self.llm_client.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=PromptImprovement,
        )

    def _build_user_prompt(
        self,
        original_prompt: str,
        judge_result: JudgeResult,
        memory_snippets: Optional[List[str]],
        semantic_snippets: Optional[List[str]] = None,
    ) -> str:
        """Build the user prompt with context for prompt rewriting."""
        parts = []

        # Original system prompt
        parts.append("=== CURRENT SYSTEM PROMPT ===")
        parts.append(original_prompt)
        parts.append("")

        # QA Scores
        parts.append("=== QA SCORES (0-5 scale) ===")
        scores = judge_result.scores
        parts.append(f"Task Success: {scores.task_success}/5")
        parts.append(f"Correctness: {scores.correctness}/5")
        parts.append(f"Helpfulness: {scores.helpfulness}/5")
        parts.append(f"Safety: {scores.safety}/5")
        parts.append(f"Efficiency: {scores.efficiency}/5")
        parts.append("")

        # Judge's rationale
        parts.append("=== JUDGE'S RATIONALE ===")
        parts.append(judge_result.rationale)
        parts.append("")

        # Issue codes
        if judge_result.issues:
            parts.append("=== DETECTED ISSUES ===")
            for issue in judge_result.issues:
                parts.append(f"- {issue}")
            parts.append("")
        else:
            parts.append("=== DETECTED ISSUES ===")
            parts.append("None detected.")
            parts.append("")

        # Memory snippets (if provided) - explicitly incorporated
        if memory_snippets:
            parts.append("=== REUSABLE PROMPT SNIPPETS (from memory) ===")
            parts.append(
                "Here are reusable prompt snippets that have worked well in similar situations. "
                "When rewriting the system prompt, prefer to incorporate and adapt these patterns "
                "where they make sense:"
            )
            parts.append("")
            for snippet in memory_snippets:
                # Safely escape and format the snippet
                # Use triple quotes or simple quotes to handle multi-line snippets
                parts.append(f'- "{snippet}"')
            parts.append("")
            parts.append(
                "These are successful patterns we want to reuse. Incorporate them naturally "
                "into the improved prompt where relevant."
            )
            parts.append("")

        # Semantic memory suggestions (if available and not already shown)
        if semantic_snippets:
            # Filter out semantic snippets that are already in the main memory snippets
            # memory_snippets here is the merged list passed from rewrite()
            unique_semantic = [s for s in semantic_snippets if s not in (memory_snippets or [])]
            if unique_semantic:
                parts.append("=== SEMANTIC MEMORY SUGGESTIONS ===")
                parts.append(
                    "The following snippets were found via semantic search based on the detected issues. "
                    "These may be relevant even if they don't match exact issue codes:"
                )
                parts.append("")
                for snippet in unique_semantic:
                    parts.append(f'- "{snippet}"')
                parts.append("")

        parts.append(
            "Please rewrite the system prompt to address the identified issues "
            "while preserving the agent's core purpose. Output only valid JSON."
        )

        return "\n".join(parts)

