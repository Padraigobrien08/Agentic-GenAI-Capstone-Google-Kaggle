# memory/store.py

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

# Optional ChromaDB import for semantic memory
try:
    import chromadb
except ImportError:
    chromadb = None  # Semantic memory is optional


class AnalysisEntry(BaseModel):
    """
    Represents a single QA analysis stored in memory.

    session_id lets us group analyses by logical session.
    """

    agent_name: str
    issue_codes: List[str]
    helpful_snippets: List[str]
    session_id: Optional[str] = None


class MemoryStore:
    """JSON-based persistent store for past analyses and prompt snippets."""

    def __init__(self, file_path: str = "memory/analyses.json"):
        """
        Initialize the memory store.

        Args:
            file_path: Path to the JSON file for persistence.
        """
        self.file_path = Path(file_path)
        self._analyses: List[AnalysisEntry] = []
        self.load()
        
        # Initialize optional ChromaDB vector store for semantic memory
        if chromadb is not None:
            try:
                self._chroma = chromadb.Client()
                self._vector_collection = self._chroma.get_or_create_collection(
                    name="qa_memory_snippets",
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                # If ChromaDB initialization fails, continue without it
                print(f"Warning: Could not initialize ChromaDB vector store: {e}. Continuing without semantic memory.")
                self._chroma = None
                self._vector_collection = None
        else:
            self._chroma = None
            self._vector_collection = None

    def load(self) -> None:
        """Load analyses from the JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    analyses = []
                    for entry in data.get("analyses", []):
                        # Handle backward compatibility with old field names
                        if "common_issues" in entry:
                            entry["issue_codes"] = entry.pop("common_issues")
                        if "useful_prompt_snippets" in entry:
                            entry["helpful_snippets"] = entry.pop("useful_prompt_snippets")
                        analyses.append(AnalysisEntry(**entry))
                    self._analyses = analyses
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # If file is corrupted, start fresh
                print(f"Warning: Could not load memory store: {e}. Starting fresh.")
                self._analyses = []
        else:
            self._analyses = []

    def save(self) -> None:
        """Save analyses to the JSON file."""
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "analyses": [entry.model_dump() for entry in self._analyses]
        }

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_analysis(
        self,
        agent_name: str,
        issue_codes: List[str],
        helpful_snippets: List[str],
        session_id: Optional[str] = None,
    ) -> None:
        """
        Add a new analysis entry to memory.

        Args:
            agent_name: Name of the agent being analyzed
            issue_codes: List of issue codes found
            helpful_snippets: List of short prompt fragments that worked well
            session_id: Optional session ID to group this analysis with others
        """
        entry = AnalysisEntry(
            agent_name=agent_name,
            issue_codes=issue_codes,
            helpful_snippets=helpful_snippets,
            session_id=session_id,
        )
        self._analyses.append(entry)
        
        # Generate a unique entry ID for vector store indexing
        entry_id = f"entry-{len(self._analyses) - 1}"
        
        # Add to vector store if available
        if self._vector_collection is not None:
            try:
                for idx, snippet in enumerate(helpful_snippets):
                    snippet_id = f"{entry_id}-{idx}"
                    self._vector_collection.add(
                        documents=[snippet],
                        ids=[snippet_id],
                        metadatas=[{
                            "issue_codes": ",".join(issue_codes),
                            "agent_name": agent_name,
                            "session_id": session_id or "",
                        }]
                    )
            except Exception as e:
                # If vector store addition fails, log but continue
                print(f"Warning: Could not add snippets to vector store: {e}. Continuing with JSON storage only.")
        
        self.save()

    def get_snippets_for_issues(self, issue_codes: List[str]) -> List[str]:
        """
        Retrieve prompt snippets from analyses that dealt with similar issues.

        Args:
            issue_codes: List of issue codes to match against

        Returns:
            List of useful prompt snippets from matching analyses
        """
        if not issue_codes:
            return []

        snippets: List[str] = []
        seen_snippets: set = set()

        # Find analyses that share at least one common issue
        for entry in self._analyses:
            # Check if there's any overlap in issues
            if set(entry.issue_codes) & set(issue_codes):
                for snippet in entry.helpful_snippets:
                    if snippet not in seen_snippets:
                        snippets.append(snippet)
                        seen_snippets.add(snippet)

        return snippets

    def get_snippets(self, limit: Optional[int] = None) -> List[str]:
        """
        Retrieve all prompt snippets from memory (for backward compatibility).

        Args:
            limit: Maximum number of snippets to return. If None, returns all.

        Returns:
            List of prompt snippets, most recent first.
        """
        snippets: List[str] = []
        seen_snippets: set = set()

        # Collect all snippets from all analyses, most recent first
        for entry in reversed(self._analyses):
            for snippet in entry.helpful_snippets:
                if snippet not in seen_snippets:
                    snippets.append(snippet)
                    seen_snippets.add(snippet)

        if limit is not None:
            return snippets[:limit]
        return snippets

    def clear(self) -> None:
        """Clear all stored analyses."""
        self._analyses = []
        self.save()

    def count(self) -> int:
        """Return the number of stored analyses."""
        return len(self._analyses)

    def __len__(self) -> int:
        """Return the number of memory entries currently stored."""
        return len(self._analyses)

    def debug_summary(self, max_entries: int = 10) -> List[Dict]:
        """
        Return a lightweight summary of up to `max_entries` memory records.

        Each summary includes:
          - agent_name
          - issue_codes
          - a shortened list of helpful_snippets (truncated to ~120 chars each)

        This is meant for debugging and notebook display only.

        Args:
            max_entries: Maximum number of entries to return. Defaults to 10.

        Returns:
            List of dictionaries with summary information, most recent first.
        """
        summaries = []
        
        # Get the most recent entries (reverse order, then take max_entries)
        recent_entries = list(reversed(self._analyses))[:max_entries]
        
        for entry in recent_entries:
            # Truncate snippets to ~120 characters
            truncated_snippets = []
            for snippet in entry.helpful_snippets:
                if len(snippet) > 120:
                    truncated_snippets.append(snippet[:120] + "...")
                else:
                    truncated_snippets.append(snippet)
            
            summaries.append({
                "agent_name": entry.agent_name,
                "issue_codes": entry.issue_codes,
                "helpful_snippets": truncated_snippets,
            })
        
        return summaries

    def get_entries_for_session(self, session_id: str) -> List[AnalysisEntry]:
        """
        Return all memory entries associated with a given session_id.

        Args:
            session_id: The session ID to filter by

        Returns:
            List of AnalysisEntry objects that match the session_id
        """
        return [e for e in self._analyses if e.session_id == session_id]

    def find_similar_snippets(self, query: str, n: int = 3) -> List[str]:
        """
        Optional semantic retrieval over helpful snippets using Chroma.

        Returns top-n snippet texts that are semantically similar to the query.

        Args:
            query: The search query text
            n: Number of similar snippets to return (default: 3)

        Returns:
            List of snippet texts, most similar first. Returns empty list if
            semantic memory is unavailable or ChromaDB is not installed.
        """
        if self._vector_collection is None:
            return []  # semantic memory unavailable
        
        try:
            results = self._vector_collection.query(
                query_texts=[query],
                n_results=n,
            )
            docs = results.get("documents", [[]])
            return docs[0] if docs else []
        except Exception as e:
            # If query fails, return empty list
            print(f"Warning: Could not query vector store: {e}")
            return []
