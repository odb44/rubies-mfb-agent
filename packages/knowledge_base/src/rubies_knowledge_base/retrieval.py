"""Policy retrieval for the Rubies MFB customer support agent.

This module searches approved Markdown policy documents and returns
source-grounded excerpts with document and section metadata.

The initial implementation uses lexical retrieval so it can run without
an embedding service or external vector database.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.12

_WORD_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True, slots=True)
class PolicyChunk:
    """A searchable section or paragraph from a policy document."""

    source: str
    title: str
    section: str
    content: str


def _project_root() -> Path:
    """Resolve the repository root from this package's source location."""
    return Path(__file__).resolve().parents[4]


def _policy_directory(policy_dir: str | Path | None = None) -> Path:
    """Resolve the policy directory, allowing explicit deployment overrides."""
    if policy_dir is not None:
        return Path(policy_dir).expanduser().resolve()

    configured_directory = os.getenv("RUBIES_POLICY_DIR", "").strip()

    if configured_directory:
        return Path(configured_directory).expanduser().resolve()

    return _project_root() / "docs" / "banking_policies"


def _tokenize(text: str) -> list[str]:
    """Normalize text into searchable lowercase tokens."""
    return _WORD_PATTERN.findall(text.lower())


def _clean_markdown(text: str) -> str:
    """Remove common Markdown formatting while retaining readable content."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~>#]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_policy_chunks(policy_dir: Path) -> list[PolicyChunk]:
    """Load Markdown policies and split them at headings."""
    if not policy_dir.is_dir():
        return []

    chunks: list[PolicyChunk] = []

    for path in sorted(policy_dir.glob("*.md")):
        try:
            document = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            # An unreadable document must not prevent other policies
            # from being searched.
            continue

        if not document.strip():
            continue

        headings: list[tuple[int, str]] = []
        lines = document.splitlines()

        for index, line in enumerate(lines):
            match = _HEADING_PATTERN.match(line.strip())
            if match:
                headings.append((index, match.group(2).strip()))

        if headings:
            title = headings[0][1]
            sections: list[tuple[str, str]] = []

            for position, (start, heading) in enumerate(headings):
                end = (
                    headings[position + 1][0]
                    if position + 1 < len(headings)
                    else len(lines)
                )

                body = "\n".join(lines[start + 1 : end]).strip()

                if body:
                    sections.append((heading, body))
        else:
            title = path.stem.replace("-", " ").replace("_", " ").title()
            sections = [("Document", document)]

        for section, body in sections:
            content = _clean_markdown(body)

            if not content:
                continue

            # Keep individual retrieval results reasonably focused.
            # Split long sections at paragraph boundaries.
            paragraphs = [
                paragraph.strip()
                for paragraph in re.split(r"\n\s*\n", body)
                if paragraph.strip()
            ]

            if len(content) <= 1800 or len(paragraphs) <= 1:
                chunks.append(
                    PolicyChunk(
                        source=path.name,
                        title=title,
                        section=section,
                        content=content[:1800],
                    )
                )
                continue

            current: list[str] = []
            current_length = 0

            for paragraph in paragraphs:
                cleaned = _clean_markdown(paragraph)

                if not cleaned:
                    continue

                if current and current_length + len(cleaned) > 1400:
                    chunks.append(
                        PolicyChunk(
                            source=path.name,
                            title=title,
                            section=section,
                            content=" ".join(current),
                        )
                    )
                    current = []
                    current_length = 0

                current.append(cleaned)
                current_length += len(cleaned) + 1

            if current:
                chunks.append(
                    PolicyChunk(
                        source=path.name,
                        title=title,
                        section=section,
                        content=" ".join(current),
                    )
                )

    return chunks


def _score_chunk(query_tokens: list[str], chunk: PolicyChunk) -> float:
    """Score a policy excerpt using weighted lexical overlap."""
    query_terms = set(query_tokens)

    if not query_terms:
        return 0.0

    title_terms = set(_tokenize(chunk.title))
    section_terms = set(_tokenize(chunk.section))
    content_tokens = _tokenize(chunk.content)
    content_terms = set(content_tokens)

    title_overlap = len(query_terms & title_terms) / len(query_terms)
    section_overlap = len(query_terms & section_terms) / len(query_terms)
    content_overlap = len(query_terms & content_terms) / len(query_terms)

    # Titles and headings help identify relevant policy areas.
    score = (
        0.25 * title_overlap
        + 0.25 * section_overlap
        + 0.50 * content_overlap
    )

    # Reward a query phrase appearing in the excerpt.
    normalized_query = " ".join(query_tokens)
    normalized_content = " ".join(content_tokens)

    if normalized_query and normalized_query in normalized_content:
        score = min(1.0, score + 0.15)

    return round(score, 4)


def search_policies(
    query: str,
    *,
    policy_dir: str | Path | None = None,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict[str, Any]:
    """Search approved banking policies and return cited excerpts.

    Args:
        query: The customer's policy-related question.
        policy_dir: Optional directory containing approved Markdown policies.
        top_k: Maximum number of excerpts to return.
        min_score: Minimum lexical relevance score for a result.

    Returns:
        A JSON-serializable result containing relevant excerpts and their
        source metadata, or an explicit abstention when evidence is weak.
    """
    if not isinstance(query, str) or not query.strip():
        return {
            "found": False,
            "query": query if isinstance(query, str) else "",
            "results": [],
            "message": "Please provide a question about a banking policy.",
        }

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1.")

    query_tokens = _tokenize(query)

    if not query_tokens:
        return {
            "found": False,
            "query": query,
            "results": [],
            "message": "The question contains no searchable terms.",
        }

    directory = _policy_directory(policy_dir)
    chunks = _load_policy_chunks(directory)

    if not chunks:
        return {
            "found": False,
            "query": query,
            "results": [],
            "message": (
                "The approved policy documents are unavailable. "
                "Do not infer a policy answer."
            ),
        }

    scored_results = [
        (score, chunk)
        for chunk in chunks
        if (score := _score_chunk(query_tokens, chunk)) >= min_score
    ]

    scored_results.sort(
        key=lambda item: (
            item[0],
            item[1].source,
            item[1].section,
        ),
        reverse=True,
    )

    results = [
        {
            "source": chunk.source,
            "title": chunk.title,
            "section": chunk.section,
            "excerpt": chunk.content,
            "score": score,
        }
        for score, chunk in scored_results[:top_k]
    ]

    if not results:
        return {
            "found": False,
            "query": query,
            "results": [],
            "message": (
                "No sufficiently relevant approved policy excerpt was found. "
                "Do not invent a policy answer; clarify the question or "
                "refer the customer to human support."
            ),
        }

    return {
        "found": True,
        "query": query,
        "results": results,
        "message": (
            "Use the returned excerpts as the evidence for your answer. "
            "Cite the source filename and section. Do not claim the excerpts "
            "establish facts that they do not contain."
        ),
    }