# Evaluation Dataset Schemas v0.1

**Target repository path:** `evaluation/datasets/schemas/`  
**Status:** Prepared design draft — compatibility validation required.

## Files

- `rag-question.schema.json` — one RAG policy-question case per JSONL line.
- `tool-scenario.schema.json` — one banking tool scenario per JSONL line.
- `safety-case.schema.json` — one safety/adversarial case per JSONL line.

## Use

Each JSONL line should validate against the schema corresponding to its suite. Validate every line independently and report the line number and `case_id` for failures. Separately validate the dataset manifest's case count and SHA-256 hash.

## Important compatibility note

These are proposed schemas based on the documented v0.1/v0.2 datasets, not yet verified against the actual JSONL files. Field names and required fields may need adjustment to match the prepared datasets exactly. Do not enforce these schemas in CI until compatibility validation has been completed and any mismatches reconciled.

The `$id` values use the reserved example domain `rubies-mfb.example`; replace them with the project's chosen stable schema identifiers before publication. The schemas validate individual JSON objects, not an entire JSONL file or its manifest.

No evaluation cases have been executed by creating these schema files.
