# Evaluation Report Schema Validation v0.2

**Target repository path:** `evaluation/reports/report-schema.json`  
**Status:** Schema syntax valid; example validation results recorded.

## Results

- **JSON Schema validation:** PASS
- **Schema draft:** JSON Schema Draft 2020-12
- **Illustrative report instance(s):** [{"example": 1, "status": "PASS", "errors": []}]


## Interpretation

The machine-readable schema is syntactically valid. The illustrative report instance is checked separately; if it fails, that indicates a mismatch between the example and the current schema, not a failed agent evaluation.

JSON Schema does not enforce all cross-field invariants. The evaluator must additionally verify:
- Summary counts reconcile with case-level outcomes.
- Any critical failure blocks `ACCEPT`.
- `ACCEPT` requires complete required-suite coverage and all gates to pass.
- `NEEDS_REVIEW`, `BLOCKED`, and `NOT_RUN` do not count as passes.
- Dataset hashes and case counts match the inputs actually used.
- Reports and evidence contain no secrets or sensitive customer data.

No agent evaluation was run. These checks concern report-format validity only.
