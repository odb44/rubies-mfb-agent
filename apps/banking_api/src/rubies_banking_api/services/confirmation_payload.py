"""Canonical hashing for confirmation-bound action payloads."""

import hashlib
import json
from typing import Any


def hash_confirmation_payload(payload: dict[str, Any]) -> str:
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
