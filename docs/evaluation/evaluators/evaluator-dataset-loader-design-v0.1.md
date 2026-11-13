# Evaluator Dataset Loader and Validation Layer — Design v0.1

**Artifact ID:** RB-EVAL-IMPL-001  
**Target repository path:** `evaluation/evaluators/dataset_loader.py`  
**Companion schemas:** `evaluation/datasets/schemas/`  
**Status:Final
**Scope:** Load and structurally validate the three prepared JSONL evaluation datasets before any agent test execution.

---

## 1. Purpose

The loader is the evaluator's first implementation component. It must read the selected JSONL dataset, parse each non-empty line as one JSON object, validate each record against its suite-specific JSON Schema, and return a typed collection of cases plus validation diagnostics.

**Fail closed:** if the dataset cannot be parsed or any record fails schema validation, the loader must not return a valid dataset for execution. It may return diagnostics, but the caller must not start agent evaluation with invalid input.

This component validates dataset structure only. It does not decide whether policy content is correct, whether a case is approved, or whether the agent passes the case.

## 2. Inputs

The loader receives:
- A configured dataset path.
- A suite identifier: `rag`, `tool_scenario`, or `safety`.
- The matching schema path, resolved from trusted evaluator configuration.
- Optional manifest metadata: dataset version, expected case count, and expected SHA-256.

Do not accept arbitrary schema paths from a dataset record. Suite-to-schema mapping must be defined by evaluator configuration.

### Suite-to-schema mapping

| Suite | Dataset | Schema |
|---|---|---|
| `rag` | `evaluation/datasets/rag_questions/` | `evaluation/datasets/schemas/rag-question.schema.json` |
| `tool_scenario` | `evaluation/datasets/tool_scenarios/` | `evaluation/datasets/schemas/tool-scenario.schema.json` |
| `safety` | `evaluation/datasets/safety_cases/` | `evaluation/datasets/schemas/safety-case.schema.json` |

Actual dataset filenames are configuration values; do not hard-code versioned filenames into loader logic.

## 3. Output contract

On success, return a `DatasetLoadResult` containing:
- `suite`
- `dataset_path` (repository-relative path where possible)
- `dataset_version` (from manifest/config, not guessed from content)
- `sha256` of the exact bytes read
- `case_count`
- `cases` in source-file order, each retaining its original JSON object
- `validation_status = "PASS"`

On failure, return or raise a structured validation failure containing:
- Dataset path and suite.
- Failure category: `FILE_NOT_FOUND`, `INVALID_UTF8`, `INVALID_JSON`, `SCHEMA_INVALID`, `DUPLICATE_CASE_ID`, `EMPTY_DATASET`, `CASE_COUNT_MISMATCH`, `HASH_MISMATCH`, or `INVALID_SCHEMA`.
- Line number when applicable.
- Case ID when it can be read safely.
- JSON Pointer/path to the invalid field when available.
- Human-readable diagnostic message.

Do not include secrets or full customer payloads in error messages. These are synthetic evaluation cases, but the error handling should still be safe by default.

## 4. Processing sequence

1. Validate the suite identifier against the supported suite set.
2. Resolve the dataset and schema paths from trusted configuration.
3. Read the dataset as bytes and calculate SHA-256 over those exact bytes.
4. If the manifest supplies an expected hash, compare it before parsing; mismatch means failure.
5. Decode as UTF-8 strictly; invalid encoding means failure.
6. Parse each non-empty line independently as JSON. Preserve original line numbers.
7. Require each parsed line to be a JSON object.
8. Validate the schema itself once per run (or use a safe cache keyed by schema path and file hash).
9. Validate each record against the selected Draft 2020-12 schema.
10. Check unique case IDs within the dataset. Identify the configured ID field for each suite; do not infer it from arbitrary nested values.
11. If a manifest case count is supplied, compare it to the number of parsed records.
12. Reject an empty dataset unless the caller explicitly enables an empty-dataset mode for a documented administrative use case. Evaluation runs should not enable that mode.
13. Return cases only if all checks pass.

The loader must not silently skip malformed lines. Blank lines may be ignored, but should be counted in diagnostics if the project chooses to enforce a no-blank-lines rule.

## 5. Failure behaviour

| Failure | Required behaviour |
|---|---|
| Dataset or schema file missing | Stop loading that dataset; report `FILE_NOT_FOUND`. |
| Invalid UTF-8 or malformed JSON | Stop loading; report line/byte context without exposing unnecessary payload. |
| Schema is invalid | Stop; report `INVALID_SCHEMA`. Do not execute cases. |
| Record fails schema | Collect record-level diagnostics, then fail the dataset as a whole. |
| Duplicate case ID | Fail the dataset; identify duplicate ID and line numbers. |
| Hash or case-count mismatch | Fail the dataset; do not silently refresh manifest metadata. |
| Empty dataset | Fail for normal evaluation runs. |
| Unsupported suite | Fail before opening files. |

Collecting multiple schema errors from a file is useful, but do not return a partially valid case list as executable input.

## 6. Security and reliability requirements

- Dataset and schema paths must be constrained to the configured repository workspace; reject path traversal and unexpected external paths unless a controlled test explicitly allows them.
- Use only trusted schema files from the repository configuration.
- Do not execute code or expressions found in dataset content.
- Treat test-case text as untrusted input. It may intentionally contain prompt injection or adversarial instructions.
- Never pass dataset instructions to the host process or evaluator as executable commands.
- Avoid logging full user messages by default; log case ID, line number, and redacted diagnostic.
- Hash the exact bytes that were validated so report metadata identifies the input precisely.
- Keep input files immutable during a run, or read bytes once and parse/validate those same bytes to avoid a time-of-check/time-of-use mismatch.
- Do not mutate the source dataset during loading.

## 7. Error model

Use a dedicated exception or result type rather than string matching. Suggested Python types:

- `DatasetLoadError`
- `DatasetFileError`
- `DatasetParseError`
- `DatasetSchemaError`
- `DatasetIntegrityError`

Every error should carry machine-readable fields: `code`, `suite`, `dataset_path`, optional `line_number`, optional `case_id`, optional `json_path`, and a safe `message`.

If the project prefers result objects over exceptions, the contract may instead return `ok: false` and a list of diagnostics. Choose one style consistently before implementation; do not mix both styles unpredictably.

## 8. Minimum unit tests

1. Valid RAG JSONL returns all cases in original order.
2. Valid tool-scenario JSONL returns all cases in original order.
3. Valid safety JSONL returns all cases in original order.
4. Malformed JSON reports the correct line.
5. Invalid UTF-8 fails closed.
6. A non-object JSON value fails.
7. A schema-invalid case prevents execution-ready output.
8. A duplicate case ID fails.
9. A missing dataset fails.
10. A missing or invalid schema fails.
11. Hash mismatch fails.
12. Case-count mismatch fails.
13. Empty dataset fails.
14. Unsupported suite fails.
15. Path traversal outside the configured workspace is rejected.
16. A prompt-injection string is preserved as test data and never executed by the loader.
17. Reported hash matches the exact bytes parsed.
18. A malformed record is never silently skipped.

## 9. Dependencies and implementation choices

Proposed library: `jsonschema` using Draft 2020-12 validation. Add it as an explicit project dependency and pin it according to the project's dependency policy.

Potential helper functions:
- `load_dataset_bytes(path)`
- `validate_schema(schema_path)`
- `parse_jsonl(raw_bytes)`
- `validate_records(records, schema)`
- `validate_unique_ids(records, suite)`
- `validate_manifest(metadata, count, sha256)`

These are suggestions, not required public APIs. Keep the external interface small and testable.

## 10. Acceptance criteria for this component

The loader is ready when:
- All 37 prepared cases load against the current schemas.
- Invalid input fails closed with useful diagnostics.
- Duplicate IDs, hash mismatch, count mismatch, and invalid schema are covered by tests.
- The exact validated dataset hashes and case counts can be passed to report generation.
- Unit tests pass.
- No agent test execution is triggered by the loader itself.

## 11. Current status and next action

This document is a design specification, not the implementation of `dataset_loader.py`. The dataset and schema artifacts are standalone and still need to be placed in the repository.

Next action: implement `evaluation/evaluators/dataset_loader.py` and its unit tests, then run the loader against the three prepared datasets. Record structural validation separately from agent evaluation results.
