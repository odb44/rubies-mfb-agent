# Evaluation Harness

**Status:** Orchestration implementation validated by unit tests. The harness loads and validates the evaluation datasets, executes configured adapters when available, and produces a schema-validated evaluation report. It does not yet connect to the live Rubies MFB agent.

## Repository locations

The evaluation assets are maintained under `docs/evaluation/`.

- Harness: `docs/evaluation/evaluators/evaluation_harness.py`
- Dataset loader: `docs/evaluation/evaluators/dataset_loader.py`
- Evaluation runner: `docs/evaluation/evaluators/evaluator_runner.py`
- RAG adapter: `docs/evaluation/evaluators/adapters/rag_adapter.py`
- Tool-scenario adapter: `docs/evaluation/evaluators/adapters/tool_scenario_adapter.py`
- Safety adapter: `docs/evaluation/evaluators/adapters/safety_adapter.py`
- Harness tests: `docs/evaluation/evaluators/tests/test_evaluation_harness.py`
- Evaluation test suite: `docs/evaluation/evaluators/tests/`
- Evaluation datasets: `docs/evaluation/datasets/`
- Dataset schemas: `docs/evaluation/datasets/schemas/`
- Report schema: `docs/evaluation/reports/report-schema.json`

## Run the evaluation harness

Run the following command from the repository root:

```powershell
uv run python docs/evaluation/evaluators/evaluation_harness.py --root .
```

The harness writes its default report to:

```text
docs/evaluation/reports/latest-evaluation-report.json
```

The report includes the evaluation decision, aggregate summary, and per-suite results.

## Run the unit tests

Run the complete evaluation test suite from the repository root:

```powershell
$env:PYTHONPATH = "$PWD\docs\evaluation\evaluators;$PWD\docs\evaluation\evaluators\adapters"

uv run python -m unittest discover -s docs/evaluation/evaluators/tests -v
```

The `PYTHONPATH` includes both the evaluator directory and the adapters directory so the existing test imports can resolve their modules.

**Current test status:** 37 tests pass.

## Current baseline result

When the harness runs without connected agent adapters, the expected result is:

| Measure | Expected result |
|---|---:|
| Defined cases | 37 |
| Executed cases | 0 |
| Passed cases | 0 |
| Failed cases | 0 |
| Blocked cases | 37 |
| Needs review | 0 |
| Decision | `INCOMPLETE` |

The three suites contain:

| Suite | Defined cases | Expected blocked cases |
|---|---:|---:|
| RAG | 20 | 20 |
| Tool scenarios | 10 | 10 |
| Safety | 7 | 7 |
| **Total** | **37** | **37** |

This baseline is intentional. It prevents the harness from inventing successful results when the agent has not been evaluated.

**Important:** Passing the harness unit tests validates the evaluation infrastructure, not the behaviour or safety of the live Rubies MFB agent. The baseline `INCOMPLETE` result must not be represented as an agent pass or failure.

## Before using this as a live-agent evaluation

1. Keep the validated JSONL datasets under `docs/evaluation/datasets/` and their three JSON Schemas under `docs/evaluation/datasets/schemas/`.
2. Keep the report JSON Schema at `docs/evaluation/reports/report-schema.json`.
3. Connect `make_rag_case_adapter`, `make_tool_scenario_adapter`, and `make_safety_case_adapter` to actual agent execution and trusted observation providers.
4. Pass the adapter mapping to `run_harness(adapters={...})` from an integration entry point.
5. Build observations from trusted execution evidence, not solely from model self-reports.
6. Review dataset lifecycle statuses and provisional policy/source dependencies before treating evaluation results as a release gate.
7. Run the evaluation against the connected agent and inspect the generated report before making claims about its quality, reliability, or safety.

## Dependency

The harness uses the existing `jsonschema` dependency through the project's `uv` and `pyproject.toml` setup. Do not add a separate requirements file for this artifact.