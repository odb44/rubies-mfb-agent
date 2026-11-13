"""Canonical hashing and normalization for confirmation-bound action payloads."""

import hashlib
import json
from typing import Any


def normalize_confirmation_payload(
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an action payload before it is created, approved, or consumed."""
    normalized_action = action.strip().upper()

    if normalized_action != "OPEN_DISPUTE":
        return payload

    allowed_fields = {
        "category",
        "description",
        "transaction_reference",
    }

    unexpected_fields = set(payload) - allowed_fields
    if unexpected_fields:
        raise ValueError("The dispute confirmation contains unsupported fields.")

    category = payload.get("category")
    description = payload.get("description")

    if not isinstance(category, str) or not category.strip():
        raise ValueError("A dispute category is required.")

    if not isinstance(description, str) or not description.strip():
        raise ValueError("A dispute description is required.")

    normalized_payload: dict[str, Any] = {
        "category": category.strip().upper(),
        "description": description.strip(),
    }

    transaction_reference = payload.get("transaction_reference")

    if transaction_reference is not None:
        if not isinstance(transaction_reference, str):
            raise ValueError("Transaction reference must be a string.")

        normalized_reference = transaction_reference.strip()

        if not normalized_reference:
            raise ValueError("Transaction reference must not be blank.")

        normalized_payload["transaction_reference"] = normalized_reference

    return normalized_payload


def hash_confirmation_payload(payload: dict[str, Any]) -> str:
    """Hash a payload using deterministic JSON serialization."""
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()