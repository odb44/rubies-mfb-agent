"""Single entry point for the Rubies MFB evaluation suites.

Default mode deliberately runs with no agent adapters and records BLOCKED cases.
It never fabricates agent observations or reports a pass without an adapter.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dataset_loader import load_evaluation_datasets
from evaluator_runner import CaseAdapter, DatasetInput, RunConfig, run_evaluation, sha256_file

SUITE_MAPPING = {
    "rag_questions": ("rag", "rag-policy-questions-v0.2.jsonl", "0.2"),
    "tool_scenarios": ("tool", "tool-scenarios-v0.1.jsonl", "0.1"),
    "safety_cases": ("safety", "safety-adversarial-cases-v0.1.jsonl", "0.1"),
}


def run_harness(
    *,
    repository_root: str | Path,
    report_path: str | Path,
    application_version: str = "not-connected",
    environment: str = "local",
    adapters: Mapping[str, CaseAdapter] | None = None,
    operator: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Load/validate all datasets and run evaluation.

    If adapters are omitted, all cases are marked BLOCKED. Supply adapters only
    after wiring them to the actual agent and trusted observation providers.
    """
    root = Path(repository_root).resolve()
    datasets_root = root / "evaluation" / "datasets"
    schemas_root = datasets_root / "schemas"
    loaded = load_evaluation_datasets(
        datasets_dir=datasets_root,
        schemas_dir=schemas_root,
    )

    dataset_inputs: list[DatasetInput] = []
    for loader_name, (suite_name, filename, version) in SUITE_MAPPING.items():
        loaded_dataset = loaded[loader_name]
        dataset_path = datasets_root / filename
        dataset_inputs.append(
            DatasetInput(
                suite=suite_name,
                path=str(dataset_path),
                version=version,
                records=loaded_dataset.records,
                sha256=sha256_file(dataset_path),
            )
        )

    report_schema_path = root / "evaluation" / "reports" / "report-schema.json"
    with report_schema_path.open("r", encoding="utf-8") as handle:
        report_schema = json.load(handle)

    config = RunConfig(
        environment=environment,
        application_version=application_version,
        operator=operator,
        notes=notes or (
            "No adapters configured: BLOCKED outcomes are expected. "
            "This run validates dataset loading and report orchestration only."
            if not adapters else notes
        ),
        report_schema_path=str(report_schema_path),
        minimum_cases_per_suite=1,
    )
    return run_evaluation(
        config=config,
        datasets=dataset_inputs,
        adapters=adapters or {},
        report_schema=report_schema,
        report_path=report_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing evaluation/datasets and evaluation/reports.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("evaluation/reports/latest-evaluation-report.json"),
        help="Output report path (relative paths are resolved from --root).",
    )
    parser.add_argument("--application-version", default="not-connected")
    parser.add_argument("--environment", default="local")
    parser.add_argument("--operator", default=None)
    parser.add_argument("--notes", default=None)
    args = parser.parse_args(argv)

    report_path = args.report if args.report.is_absolute() else args.root / args.report
    try:
        report = run_harness(
            repository_root=args.root,
            report_path=report_path,
            application_version=args.application_version,
            environment=args.environment,
            operator=args.operator,
            notes=args.notes,
        )
    except Exception as exc:
        print(
            f"Evaluation harness stopped safely: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print(json.dumps({
        "report_path": str(report_path.resolve()),
        "decision": report["decision"]["status"],
        "summary": report["summary"],
        "suites": [
            {
                "suite": suite["suite"],
                "defined": suite["defined"],
                "blocked": suite["blocked"],
                "needs_review": suite["needs_review"],
                "passed": suite["passed"],
                "failed": suite["failed"],
            }
            for suite in report["suites"]
        ],
    }, indent=2))
    return 0 if report["decision"]["status"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
