# agents/trajectory_inspector.py

import re
from typing import List, Optional, Set, Tuple

from core.models import (
    ConversationTrace,
    TrajectoryAnalysis,
    TrajectoryIssue,
    TraceEvent,
)


def _find_last_user_and_assistant(
    events: list[TraceEvent],
) -> Tuple[Optional[int], Optional[int]]:
    """
    Returns indices of the last user message and the last assistant message
    where the assistant comes after the user. If not found, returns (None, None).
    """
    last_user_idx: Optional[int] = None
    last_assistant_idx: Optional[int] = None

    for idx, ev in enumerate(events):
        if ev.role == "user":
            last_user_idx = idx
        elif ev.role == "assistant":
            last_assistant_idx = idx

    if (
        last_user_idx is None
        or last_assistant_idx is None
        or last_assistant_idx < last_user_idx
    ):
        return None, None

    return last_user_idx, last_assistant_idx


def _tokenize(text: str) -> List[str]:
    """Tokenize text into words (alphanumeric sequences)."""
    return re.findall(r"\b\w+\b", text.lower())


class TrajectoryInspector:
    """Analyzes conversation traces to detect trajectory issues."""

    def analyze(self, trace: ConversationTrace) -> TrajectoryAnalysis:
        """
        Analyze a conversation trace and return a TrajectoryAnalysis.

        Detects:
        - Repeated identical tool calls
        - Tool calls with empty args
        - Final answer missing key terms from last user query
        """
        issues: List[TrajectoryIssue] = []
        events = trace.events

        # Detect repeated identical tool calls
        repeated_issues = self._detect_repeated_tool_calls(events)
        issues.extend(repeated_issues)

        # Detect tool calls with empty args
        empty_args_issues = self._detect_empty_tool_args(events)
        issues.extend(empty_args_issues)

        # Detect missing key terms in final answer
        missing_terms_issues = self._detect_missing_key_terms(trace)
        issues.extend(missing_terms_issues)

        # Generate summary
        summary = self._generate_summary(events, issues)

        return TrajectoryAnalysis(
            ordered_events=events,
            issues=issues,
            summary=summary,
        )

    def _detect_repeated_tool_calls(
        self, events: List[TraceEvent]
    ) -> List[TrajectoryIssue]:
        """Detect tool calls that are repeated identically."""
        issues: List[TrajectoryIssue] = []
        seen_calls: List[Tuple[int, str, dict]] = []  # (index, tool_name, args)

        for idx, event in enumerate(events):
            if event.role == "tool_call" and event.tool_name and event.args:
                call_signature = (event.tool_name, tuple(sorted(event.args.items())))
                # Check if we've seen this exact call before
                for prev_idx, prev_tool, prev_args in seen_calls:
                    prev_signature = (prev_tool, tuple(sorted(prev_args.items())))
                    if call_signature == prev_signature:
                        # Found a repeat
                        step_indices = [prev_idx, idx]
                        issues.append(
                            TrajectoryIssue(
                                code="REPEATED_TOOL_CALL",
                                description=(
                                    f"Tool '{event.tool_name}' called twice with "
                                    f"identical arguments at steps {prev_idx} and {idx}"
                                ),
                                step_indices=step_indices,
                            )
                        )
                        break
                seen_calls.append((idx, event.tool_name, event.args))

        return issues

    def _detect_empty_tool_args(
        self, events: List[TraceEvent]
    ) -> List[TrajectoryIssue]:
        """Detect tool calls with empty or missing arguments."""
        issues: List[TrajectoryIssue] = []

        for idx, event in enumerate(events):
            if event.role == "tool_call":
                if event.args is None or event.args == {}:
                    issues.append(
                        TrajectoryIssue(
                            code="EMPTY_TOOL_ARGS",
                            description=(
                                f"Tool '{event.tool_name or 'unknown'}' called "
                                f"with empty or missing arguments at step {idx}"
                            ),
                            step_indices=[idx],
                        )
                    )

        return issues

    def _detect_missing_key_terms(
        self, trace: ConversationTrace
    ) -> List[TrajectoryIssue]:
        """Detect if final answer is missing key terms from last user query."""
        user_idx, asst_idx = _find_last_user_and_assistant(trace.events)
        
        # If either is None, return empty list
        if user_idx is None or asst_idx is None:
            return []
        
        user_event = trace.events[user_idx]
        asst_event = trace.events[asst_idx]
        
        # Ensure both have content
        if not user_event.content or not asst_event.content:
            return []
        
        user_text = user_event.content.lower()
        asst_text = asst_event.content.lower()
        
        # Get stopwords (reuse from _extract_key_terms)
        stopwords = self._get_stopwords()
        
        # Tokenize and build sets
        user_terms = {
            t for t in _tokenize(user_text)
            if t not in stopwords and len(t) > 2
        }
        asst_terms = {
            t for t in _tokenize(asst_text)
            if t not in stopwords and len(t) > 2
        }
        
        # Compute missing key terms
        missing_terms = sorted(user_terms - asst_terms)
        
        # Only flag if both conditions hold:
        # 1. At least 2 missing terms
        # 2. Assistant text is longer than 40 characters
        if len(missing_terms) >= 2 and len(asst_text) > 40:
            description = (
                "Final answer at step "
                f"{asst_idx} is missing key terms from last user query: "
                + ", ".join(missing_terms)
            )
            return [
                TrajectoryIssue(
                    code="MISSING_KEY_TERMS",
                    description=description,
                    step_indices=[asst_idx],
                )
            ]
        
        return []

    def _get_stopwords(self) -> Set[str]:
        """Get the set of stop words for filtering."""
        return {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "can",
            "what",
            "where",
            "when",
            "who",
            "why",
            "how",
            "which",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "and",
            "or",
            "but",
            "if",
            "then",
        }

    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Extract key terms from user query.

        Removes common stop words and extracts meaningful nouns/verbs.
        """
        stop_words = self._get_stopwords()
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter out stop words and short words
        key_terms = [
            word
            for word in words
            if word not in stop_words and len(word) > 2
        ]

        # Remove duplicates while preserving order
        seen: Set[str] = set()
        unique_terms = []
        for term in key_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)

        return unique_terms

    def _generate_summary(
        self, events: List[TraceEvent], issues: List[TrajectoryIssue]
    ) -> str:
        """Generate a summary of the trajectory analysis."""
        total_events = len(events)
        num_issues = len(issues)

        if num_issues == 0:
            return (
                f"Trajectory analysis completed. Found no issues in "
                f"{total_events} events."
            )

        issue_codes = [issue.code for issue in issues]
        unique_codes = list(set(issue_codes))

        summary_parts = [
            f"Trajectory analysis completed. Found {num_issues} issue(s) "
            f"across {total_events} events."
        ]

        if unique_codes:
            summary_parts.append(f"Issue types: {', '.join(unique_codes)}")

        return " ".join(summary_parts)

