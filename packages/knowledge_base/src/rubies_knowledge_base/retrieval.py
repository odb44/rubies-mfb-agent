"""Retrieve relevant banking policy passages using semantic and lexical search."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.35

_WORD_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class PolicyChunk:
    """A searchable passage from an approved banking policy document."""

    source: str
    title: str
    section: str
    content: str


def _project_root() -> Path:
    """Resolve the repository root from this package's source directory."""
    return Path(__file__).resolve().parents[4]


def _policy_directory(policy_dir: str | Path | None = None) -> Path:
    """Resolve the directory containing approved Markdown policy documents."""
    if policy_dir is not None:
        return Path(policy_dir).expanduser().resolve()

    configured_directory = os.getenv("RUBIES_POLICY_DIR")
    if configured_directory:
        return Path(configured_directory).expanduser().resolve()

    return _project_root() / "docs" / "banking_policies"


def _tokenize(text: str) -> set[str]:
    """Convert text into a set of lowercase alphanumeric tokens."""
    return {token.lower() for token in _WORD_PATTERN.findall(text)}


def _clean_markdown(text: str) -> str:
    """Remove common Markdown formatting while preserving readable content."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[#>*_~]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def _flush_policy_paragraphs(
    paragraphs: list[str],
    *,
    source: str,
    title: str,
    section: str,
    chunks: list[PolicyChunk],
) -> None:
    """Convert buffered paragraphs into a policy chunk."""
    if not paragraphs:
        return

    content = _clean_markdown("\n\n".join(paragraphs))
    paragraphs.clear()

    if not content:
        return

    chunks.append(
        PolicyChunk(
            source=source,
            title=title,
            section=section,
            content=content,
        )
    )


def _load_policy_chunks(
    policy_dir: str | Path | None = None,
) -> list[PolicyChunk]:
    """Load policy Markdown files and split them into heading-based passages."""
    directory = _policy_directory(policy_dir)

    if not directory.exists() or not directory.is_dir():
        return []

    chunks: list[PolicyChunk] = []

    for path in sorted(directory.glob("*.md")):
        try:
            markdown = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        current_title = path.stem.replace("-", " ").replace("_", " ").title()
        current_section = "General"
        paragraphs: list[str] = []

        for line in markdown.splitlines():
            heading_match = _HEADING_PATTERN.match(line.strip())

            if heading_match:
                _flush_policy_paragraphs(
                    paragraphs,
                    source=path.name,
                    title=current_title,
                    section=current_section,
                    chunks=chunks,
                )

                heading_level = len(heading_match.group(1))
                heading_text = _clean_markdown(heading_match.group(2))

                if heading_level == 1:
                    current_title = heading_text
                    current_section = "General"
                else:
                    current_section = heading_text

                continue

            if not line.strip():
                _flush_policy_paragraphs(
                    paragraphs,
                    source=path.name,
                    title=current_title,
                    section=current_section,
                    chunks=chunks,
                )
                continue

            paragraphs.append(line)

        _flush_policy_paragraphs(
            paragraphs,
            source=path.name,
            title=current_title,
            section=current_section,
            chunks=chunks,
        )

    return chunks


def _score_chunk(query: str, chunk: PolicyChunk) -> float:
    """Calculate a lexical relevance score between zero and one."""
    query_tokens = _tokenize(query)

    if not query_tokens:
        return 0.0

    title_tokens = _tokenize(chunk.title)
    section_tokens = _tokenize(chunk.section)
    content_tokens = _tokenize(chunk.content)

    title_score = len(query_tokens & title_tokens) / len(query_tokens)
    section_score = len(query_tokens & section_tokens) / len(query_tokens)
    content_score = len(query_tokens & content_tokens) / len(query_tokens)

    score = (
        0.25 * title_score
        + 0.25 * section_score
        + 0.50 * content_score
    )

    normalized_query = " ".join(query.lower().split())
    normalized_content = " ".join(chunk.content.lower().split())

    if len(normalized_query) >= 4 and normalized_query in normalized_content:
        score = min(1.0, score + 0.20)

    return round(score, 4)


def _format_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Format retrieval results consistently for downstream agent components."""
    if not results:
        return {
            "found": False,
            "results": [],
            "message": (
                "No sufficiently relevant approved banking policy was found. "
                "Do not invent a policy answer; ask for clarification or "
                "escalate when appropriate."
            ),
        }

    return {
        "found": True,
        "results": results,
        "message": (
            "Use the retrieved policy passages as grounding for the response. "
            "Identify the source filename and section where appropriate. "
            "Do not claim that a policy says more than the retrieved text supports."
        ),
    }


def search_policies(
    query: str,
    *,
    policy_dir: str | Path | None = None,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict[str, Any]:
    """Search approved banking policies semantically, with lexical fallback.

    Semantic search uses the persistent local vector index. If the index is
    unavailable or stale, lexical retrieval is used instead.

    Args:
        query: The customer's question or policy-related search query.
        policy_dir: Optional directory containing approved Markdown policies.
        top_k: Maximum number of passages to return.
        min_score: Minimum relevance score between zero and one.

    Returns:
        A dictionary containing the found flag, ranked results, and guidance.
    """
    if not isinstance(query, str) or not query.strip():
        return _format_results([])

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0.0 and 1.0.")

    if not _tokenize(query):
        return _format_results([])

    chunks = _load_policy_chunks(policy_dir)

    if not chunks:
        return _format_results([])

    # Import lazily to avoid a circular import:
    # vector_index imports PolicyChunk and helpers from this module.
    try:
        from rubies_knowledge_base.vector_index import search_policy_index

        semantic_results = search_policy_index(
            query,
            policy_dir=policy_dir,
            top_k=top_k,
            min_score=min_score,
        )
    except (ImportError, OSError, ValueError, RuntimeError):
        semantic_results = None

    # A None result means that the index is missing, stale, or unavailable.
    # An empty list means semantic search ran successfully but found no match.
    if semantic_results is not None:
        return _format_results(semantic_results)

    # Lexical fallback: keeps retrieval usable without a valid vector index.
    scored_results: list[dict[str, Any]] = []

    for chunk in chunks:
        score = _score_chunk(query, chunk)

        if score < min_score:
            continue

        scored_results.append(
            {
                "source": chunk.source,
                "title": chunk.title,
                "section": chunk.section,
                "excerpt": chunk.content[:700],
                "score": score,
            }
        )

    scored_results.sort(
        key=lambda result: (
            -result["score"],
            result["source"],
            result["section"],
        )
    )

    return _format_results(scored_results[:top_k])