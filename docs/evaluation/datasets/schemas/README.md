# Evaluation Dataset Schemas v0.1

**Status:** Final.

## Schema Files

- `rag-question.schema.json` — defines one RAG policy-question case per JSONL line.
- `tool-scenario.schema.json` — defines one banking tool scenario per JSONL line.
- `safety-case.schema.json` — defines one safety or adversarial case per JSONL line.

## Usage

Each JSONL line should validate against the schema corresponding to its evaluation suite.

Validation should:

1. Validate each JSONL record independently.
2. Report the line number and `case_id` for every validation failure.
3. Validate the dataset manifest's case count and SHA-256 hash separately.

## Compatibility and Validation

These are proposed schemas based on the documented v0.1/v0.2 datasets. They have not yet been verified against the actual JSONL files.

Field names and required fields may need adjustment to match the prepared datasets. Do not enforce these schemas in CI until compatibility validation has been completed and any mismatches reconciled.

The `$id` values currently use the reserved example domain `rubies-mfb.example`. Replace them with the project's chosen stable schema identifiers before publication.

These schemas validate individual JSON objects. They do not validate an entire JSONL file or its manifest.

Creating these schema files does not constitute execution of evaluation cases.
