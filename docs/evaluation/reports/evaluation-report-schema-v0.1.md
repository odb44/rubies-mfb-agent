# Rubies MFB Evaluation Report Schema

**Artifact ID:** RB-DES-EVAL-SCHEMA-001  
**Version:** 0.1  
**Status:** Prepared design draft — review required  
**Target location:** `evaluation/reports/report-schema.json`  
**Purpose:** Define the machine-readable structure for one evaluation run and its per-case evidence.  
**Boundary:** This is a schema draft only. It does not implement the evaluator, execute tests, or provide baseline results.

## Design principles

- Preserve per-suite and per-case outcomes; never rely on one blended score.
- Critical failures override numeric scores.
- Distinguish prepared-case status from execution outcome.
- Record blockers and manual adjudication explicitly.
- Record Pidgin language matching and safety parity independently.
- Store references to sanitized evidence rather than embedding sensitive payloads.
- Version the schema and datasets so results can be reproduced.

## Proposed JSON Schema

Save the following JSON as `evaluation/reports/report-schema.json` when the schema is approved.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rubies-mfb.invalid/schemas/evaluation-report-v0.1.json",
  "title": "Rubies MFB Agent Evaluation Report",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "run",
    "application",
    "configuration",
    "datasets",
    "summary",
    "suites",
    "critical_failures",
    "decision"
  ],
  "properties": {
    "schema_version": {
      "const": "0.1"
    },
    "run": {
      "type": "object",
      "additionalProperties": false,
      "required": ["run_id", "started_at", "environment", "evaluator_version"],
      "properties": {
        "run_id": {"type": "string", "minLength": 1},
        "started_at": {"type": "string", "format": "date-time"},
        "finished_at": {"type": ["string", "null"], "format": "date-time"},
        "operator": {"type": ["string", "null"]},
        "environment": {"type": "string", "minLength": 1},
        "evaluator_version": {"type": "string", "minLength": 1},
        "notes": {"type": ["string", "null"]}
      }
    },
    "application": {
      "type": "object",
      "additionalProperties": false,
      "required": ["version"],
      "properties": {
        "version": {"type": "string", "minLength": 1},
        "git_commit": {"type": ["string", "null"]},
        "build_id": {"type": ["string", "null"]}
      }
    },
    "configuration": {
      "type": "object",
      "additionalProperties": false,
      "required": ["model", "prompt_version", "tool_schema_version", "retrieval_index_version"],
      "properties": {
        "model": {"type": ["string", "null"]},
        "prompt_version": {"type": ["string", "null"]},
        "tool_schema_version": {"type": ["string", "null"]},
        "retrieval_index_version": {"type": ["string", "null"]},
        "embedding_model_version": {"type": ["string", "null"]},
        "source_manifest_version": {"type": ["string", "null"]},
        "fixture_version": {"type": ["string", "null"]},
        "configuration_notes": {"type": ["string", "null"]}
      }
    },
    "datasets": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["suite", "path", "version", "sha256", "case_count"],
        "properties": {
          "suite": {"enum": ["rag", "tool", "safety"]},
          "path": {"type": "string", "minLength": 1},
          "version": {"type": "string", "minLength": 1},
          "sha256": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"},
          "case_count": {"type": "integer", "minimum": 0}
        }
      }
    },
    "summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["defined", "executed", "passed", "failed", "blocked", "needs_review", "not_run"],
      "properties": {
        "defined": {"type": "integer", "minimum": 0},
        "executed": {"type": "integer", "minimum": 0},
        "passed": {"type": "integer", "minimum": 0},
        "failed": {"type": "integer", "minimum": 0},
        "blocked": {"type": "integer", "minimum": 0},
        "needs_review": {"type": "integer", "minimum": 0},
        "not_run": {"type": "integer", "minimum": 0},
        "critical_failure_count": {"type": "integer", "minimum": 0}
      }
    },
    "suites": {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/$defs/suiteResult"}
    },
    "critical_failures": {
      "type": "array",
      "items": {"$ref": "#/$defs/criticalFailure"}
    },
    "thresholds": {
      "type": "array",
      "items": {"$ref": "#/$defs/thresholdResult"}
    },
    "regression": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "required": ["compared_run_id", "new_failures", "resolved_failures", "notes"],
      "properties": {
        "compared_run_id": {"type": ["string", "null"]},
        "new_failures": {"type": "array", "items": {"type": "string"}},
        "resolved_failures": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": ["string", "null"]}
      }
    },
    "decision": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "rationale"],
      "properties": {
        "status": {"enum": ["ACCEPT", "REJECT", "INCOMPLETE"]},
        "rationale": {"type": "array", "items": {"type": "string"}},
        "approved_by": {"type": ["string", "null"]}
      }
    }
  },
  "$defs": {
    "caseOutcome": {
      "type": "object",
      "additionalProperties": false,
      "required": ["case_id", "outcome", "critical_failure", "assertions"],
      "properties": {
        "case_id": {"type": "string", "minLength": 1},
        "outcome": {"enum": ["PASSED", "FAILED", "BLOCKED", "NEEDS_REVIEW", "NOT_RUN"]},
        "critical_failure": {"type": "boolean"},
        "scores": {
          "type": ["object", "null"],
          "additionalProperties": {"type": "number", "minimum": 0},
          "description": "Suite-specific numeric scores; for RAG, dimensions use a 0–2 scale."
        },
        "assertions": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["assertion_id", "passed"],
            "properties": {
              "assertion_id": {"type": "string"},
              "passed": {"type": "boolean"},
              "expected": {},
              "actual": {},
              "evidence_ref": {"type": ["string", "null"]},
              "notes": {"type": ["string", "null"]}
            }
          }
        },
        "language": {"type": ["string", "null"]},
        "expected_response_language": {"type": ["string", "null"]},
        "language_match_pass": {"type": ["boolean", "null"]},
        "content_correctness_pass": {"type": ["boolean", "null"]},
        "citation_pass": {"type": ["boolean", "null"]},
        "safety_parity_pass": {"type": ["boolean", "null"]},
        "handoff_pass": {"type": ["boolean", "null"]},
        "tool_calls": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["tool_name", "outcome"],
            "properties": {
              "tool_name": {"type": "string"},
              "outcome": {"type": "string"},
              "sanitized_input_ref": {"type": ["string", "null"]},
              "sanitized_output_ref": {"type": ["string", "null"]},
              "correlation_id": {"type": ["string", "null"]}
            }
          }
        },
        "citations": {"type": "array", "items": {"type": "string"}},
        "critical_failure_ids": {"type": "array", "items": {"type": "string"}},
        "block_reason": {"type": ["string", "null"]},
        "reviewer_notes": {"type": ["string", "null"]}
      }
    },
    "suiteResult": {
      "type": "object",
      "additionalProperties": false,
      "required": ["suite", "defined", "executed", "passed", "failed", "blocked", "needs_review", "not_run", "cases"],
      "properties": {
        "suite": {"enum": ["rag", "tool", "safety"]},
        "defined": {"type": "integer", "minimum": 0},
        "executed": {"type": "integer", "minimum": 0},
        "passed": {"type": "integer", "minimum": 0},
        "failed": {"type": "integer", "minimum": 0},
        "blocked": {"type": "integer", "minimum": 0},
        "needs_review": {"type": "integer", "minimum": 0},
        "not_run": {"type": "integer", "minimum": 0},
        "metrics": {"type": "object", "additionalProperties": {"type": ["number", "string", "boolean", "null"]}},
        "cases": {"type": "array", "items": {"$ref": "#/$defs/caseOutcome"}}
      }
    },
    "criticalFailure": {
      "type": "object",
      "additionalProperties": false,
      "required": ["failure_id", "case_id", "category", "severity", "evidence_ref", "status"],
      "properties": {
        "failure_id": {"type": "string"},
        "case_id": {"type": "string"},
        "category": {"type": "string"},
        "severity": {"enum": ["CRITICAL"]},
        "evidence_ref": {"type": ["string", "null"]},
        "status": {"enum": ["OPEN", "REMEDIATED", "ACCEPTED_RISK"]},
        "owner": {"type": ["string", "null"]},
        "notes": {"type": ["string", "null"]}
      }
    },
    "thresholdResult": {
      "type": "object",
      "additionalProperties": false,
      "required": ["metric", "target", "actual", "denominator", "passed", "notes"],
      "properties": {
        "metric": {"type": "string"},
        "target": {"type": ["number", "string"]},
        "actual": {"type": ["number", "string", "null"]},
        "denominator": {"type": ["integer", "null"], "minimum": 0},
        "passed": {"type": ["boolean", "null"]},
        "notes": {"type": ["string", "null"]}
      }
    }
  }
}
```

## Example report instance

This is a structural example only. It is not a real evaluation run and contains no measured performance results.

```json
{
  "schema_version": "0.1",
  "run": {
    "run_id": "EXAMPLE-NOT-A-REAL-RUN",
    "started_at": "2026-10-25T10:00:00Z",
    "finished_at": null,
    "operator": "example",
    "environment": "example-only",
    "evaluator_version": "not-implemented",
    "notes": "Illustrative structure; do not treat as evaluation evidence."
  },
  "application": {
    "version": "not-implemented",
    "git_commit": null,
    "build_id": null
  },
  "configuration": {
    "model": null,
    "prompt_version": null,
    "tool_schema_version": null,
    "retrieval_index_version": null,
    "embedding_model_version": null,
    "source_manifest_version": null,
    "fixture_version": null,
    "configuration_notes": "No evaluation executed."
  },
  "datasets": [],
  "summary": {
    "defined": 0,
    "executed": 0,
    "passed": 0,
    "failed": 0,
    "blocked": 0,
    "needs_review": 0,
    "not_run": 0,
    "critical_failure_count": 0
  },
  "suites": [],
  "critical_failures": [],
  "thresholds": [],
  "regression": null,
  "decision": {
    "status": "INCOMPLETE",
    "rationale": ["Illustrative example only; no tests have been executed."],
    "approved_by": null
  }
}
```

## Validation rules beyond JSON Schema

The schema validates shape, not all logical invariants. The evaluator should additionally enforce:

1. `defined = passed + failed + blocked + needs_review + not_run`; `executed = passed + failed + needs_review` unless the team explicitly adopts another definition. Document and keep the chosen definition consistent.
2. Suite and overall counts equal the totals of their case outcomes.
3. `critical_failure_count` equals the number of critical failure records; any critical failure forces `decision.status = REJECT` unless the run is `INCOMPLETE` due to unrelated missing coverage—in that case, report `INCOMPLETE` and still flag the critical failure prominently. Recommended acceptance remains blocked either way.
4. Any case with `critical_failure = true` must have outcome `FAILED`.
5. A `PASSED` RAG case must satisfy required citations, abstention, handoff, and language-match gates where applicable.
6. A `PASSED` tool case must satisfy every mandatory assertion.
7. Missing required execution evidence cannot be counted as a pass.
8. Dataset hash and case count must match the exact files used in the run.
9. No raw credentials, OTPs, PINs, passwords, CVVs, or unnecessary customer-sensitive data in evidence references or report payloads.
10. Threshold metrics must include their denominator; an undefined denominator produces `null` actual/pass state, not a pass.

## Review points

- Confirm whether this schema is sufficient for the initial evaluation harness.
- Confirm the count definitions in the validation rules, especially how `executed` treats `NEEDS_REVIEW`.
- Confirm the policy for a run with both a critical failure and incomplete suite coverage.
- Confirm whether `ACCEPTED_RISK` is permitted for critical failures; default recommendation is that it must never allow an acceptance decision.
- Keep model-specific predictive metrics in the separate loan-model evaluation report rather than conflating them with agent behavior.
