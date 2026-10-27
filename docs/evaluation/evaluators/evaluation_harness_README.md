# Evaluation Harness

**Status:** orchestration implementation draft. It validates and loads the datasets and emits a schema-validated report. It does not connect to the live Rubies MFB agent.

## Repository destinations
- `evaluation_harness.py` → `evaluation/evaluators/evaluation_harness.py`
- `test_evaluation_harness.py` → `evaluation/evaluators/tests/test_evaluation_harness.py`

## Run from the repository root
```bash
uv run python evaluation/evaluators/evaluation_harness.py --root .
```

Default output:
`evaluation/reports/latest-evaluation-report.json`

Expected current result with no adapters: `INCOMPLETE`, with all 37 cases `BLOCKED`. This is intentional and confirms that no pass is invented when no agent is connected.

## Before using this as an agent evaluation
1. Place the validated JSONL datasets under `evaluation/datasets/` and their three JSON Schemas under `evaluation/datasets/schemas/`.
2. Place the report JSON Schema at `evaluation/reports/report-schema.json`.
3. Wire the `make_rag_case_adapter`, `make_tool_scenario_adapter`, and `make_safety_case_adapter` factories to real-agent execution and trusted observation providers.
4. Pass the adapter mapping to `run_harness(adapters={...})` from an integration entry point. Do not build observations from model self-reports.
5. Review dataset lifecycle statuses and provisional policy/source dependencies before treating any run as a release gate.

## Dependency
Uses the existing `jsonschema` dependency through the project's `uv`/`pyproject.toml` setup. Do not add a separate requirements file for this artifact.
