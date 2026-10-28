"""Persistent local semantic index for approved banking policies."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from rubies_knowledge_base.retrieval import (
    PolicyChunk,
    _load_policy_chunks,
    _policy_directory,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_VERSION = 1


def _index_directory() -> Path:
    """Resolve the local vector index directory."""
    configured = os.getenv("VECTOR_INDEX_DIR", "").strip()

    if configured:
        return Path(configured).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[4]
    return project_root / ".local" / "vector_index"


def _source_fingerprint(policy_dir: Path) -> str:
    """Hash policy filenames and contents to detect policy changes."""
    digest = hashlib.sha256()

    for path in sorted(policy_dir.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())

    return digest.hexdigest()


@lru_cache(maxsize=1)
def _load_encoder() -> Any:
    """Load and cache the embedding model using configured Hugging Face credentials."""
    from sentence_transformers import SentenceTransformer

    hf_token = os.getenv("HF_TOKEN", "").strip() or None

    return SentenceTransformer(
        EMBEDDING_MODEL,
        token=hf_token,
    )


def build_policy_index(
    policy_dir: str | Path | None = None,
    index_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Embed approved policy chunks and persist vectors and metadata."""
    policies = _policy_directory(policy_dir)
    destination = (
        Path(index_dir).expanduser().resolve()
        if index_dir is not None
        else _index_directory()
    )

    chunks = _load_policy_chunks(policies)

    if not chunks:
        raise ValueError(f"No readable policy chunks found in {policies}")

    encoder = _load_encoder()

    texts = [
        f"Title: {chunk.title}\n"
        f"Section: {chunk.section}\n"
        f"Policy: {chunk.content}"
        for chunk in chunks
    ]

    embeddings = encoder.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
        raise ValueError("The embedding model returned an invalid vector matrix.")

    destination.mkdir(parents=True, exist_ok=True)

    metadata = {
        "index_version": INDEX_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "source_fingerprint": _source_fingerprint(policies),
        "chunks": [
            {
                "source": chunk.source,
                "title": chunk.title,
                "section": chunk.section,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    }

    # Write temporary files first, then replace the published files.
    temporary_vectors = destination / "vectors.tmp.npy"
    temporary_metadata = destination / "metadata.tmp.json"

    np.save(temporary_vectors, embeddings, allow_pickle=False)
    temporary_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temporary_vectors.replace(destination / "vectors.npy")
    temporary_metadata.replace(destination / "metadata.json")

    return {
        "index_directory": str(destination),
        "chunks_indexed": len(chunks),
        "embedding_dimensions": int(embeddings.shape[1]),
        "embedding_model": EMBEDDING_MODEL,
    }


def load_policy_index(
    policy_dir: str | Path | None = None,
    index_dir: str | Path | None = None,
) -> tuple[np.ndarray, list[PolicyChunk]] | None:
    """Load a valid index, returning None when it is absent or stale."""
    policies = _policy_directory(policy_dir)
    destination = (
        Path(index_dir).expanduser().resolve()
        if index_dir is not None
        else _index_directory()
    )

    vectors_path = destination / "vectors.npy"
    metadata_path = destination / "metadata.json"

    if not vectors_path.is_file() or not metadata_path.is_file():
        return None

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        if metadata.get("index_version") != INDEX_VERSION:
            return None

        if metadata.get("embedding_model") != EMBEDDING_MODEL:
            return None

        if metadata.get("source_fingerprint") != _source_fingerprint(policies):
            return None

        vectors = np.load(vectors_path, allow_pickle=False)

        chunks = [
            PolicyChunk(
                source=item["source"],
                title=item["title"],
                section=item["section"],
                content=item["content"],
            )
            for item in metadata["chunks"]
        ]

        if (
            vectors.ndim != 2
            or vectors.shape[0] != len(chunks)
            or not chunks
        ):
            return None

        return vectors.astype(np.float32, copy=False), chunks

    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def search_policy_index(
    query: str,
    *,
    policy_dir: str | Path | None = None,
    index_dir: str | Path | None = None,
    top_k: int = 4,
    min_score: float = 0.35,
) -> list[dict[str, Any]] | None:
    """Return semantic matches, or None when the index needs rebuilding."""
    loaded = load_policy_index(policy_dir, index_dir)

    if loaded is None:
        return None

    vectors, chunks = loaded
    encoder = _load_encoder()

    query_vector = encoder.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_vector = np.asarray(query_vector, dtype=np.float32)[0]

    if query_vector.shape[0] != vectors.shape[1]:
        return None

    scores = vectors @ query_vector
    ranked_indices = np.argsort(scores)[::-1]

    results = []

    for index in ranked_indices:
        score = float(scores[index])

        if score < min_score:
            continue

        chunk = chunks[int(index)]

        results.append(
            {
                "source": chunk.source,
                "title": chunk.title,
                "section": chunk.section,
                "excerpt": chunk.content,
                "score": round(score, 4),
            }
        )

        if len(results) >= top_k:
            break

    return results