"""Command-line utility for rebuilding the local banking policy index."""

from __future__ import annotations

import argparse
import sys

from rubies_knowledge_base.vector_index import build_policy_index


def main() -> int:
    """Build the semantic index and report the outcome."""
    parser = argparse.ArgumentParser(
        description="Rebuild the local semantic index for banking policies."
    )
    parser.add_argument(
        "--policy-dir",
        help="Optional directory containing approved Markdown policy files.",
    )
    parser.add_argument(
        "--index-dir",
        help="Optional destination directory for the vector index.",
    )

    args = parser.parse_args()

    try:
        result = build_policy_index(
            policy_dir=args.policy_dir,
            index_dir=args.index_dir,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Index rebuild failed: {exc}", file=sys.stderr)
        return 1

    print("Policy index rebuilt successfully.")
    print(f"Index directory: {result['index_directory']}")
    print(f"Chunks indexed: {result['chunks_indexed']}")
    print(f"Embedding dimensions: {result['embedding_dimensions']}")
    print(f"Embedding model: {result['embedding_model']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())