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
from evaluator_runner import (
    CaseAdapter,
    DatasetInput,
    RunConfig,
    run_evaluation,
    sha256_file,
)


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
    """Load datasets, execute configured adapters, and validate the report.

    Dataset files and schemas are read from docs/evaluation/datasets.

    If adapters are omitted, every defined case is marked BLOCKED.
    Adapters must be connected to the actual agent and trusted observation
    providers before the results can be treated as agent evaluation results.
    """
    root = Path(repository_root).resolve()

    evaluation_root = root / "docs" / "evaluation"
    datasets_root = evaluation_root / "datasets"
    schemas_root = datasets_root / "schemas"
    reports_root = evaluation_root / "reports"

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

    report_schema_path = reports_root / "report-schema.json"

    with report_schema_path.open("r", encoding="utf-8") as handle:
        report_schema = json.load(handle)

    effective_notes = notes

    if effective_notes is None and not adapters:
        effective_notes = (
            "No adapters configured: BLOCKED outcomes are expected. "
            "This run validates dataset loading and report orchestration only. "
            "The live Rubies MFB agent has not been evaluated."
        )

    config = RunConfig(
        environment=environment,
        application_version=application_version,
        operator=operator,
        notes=effective_notes,
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
    """Run evaluation from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing docs/evaluation/datasets and reports.",
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "docs/evaluation/reports/latest-evaluation-report.json"
        ),
        help=(
            "Output report path. Relative paths are resolved from "
            "--root."
        ),
    )

    parser.add_argument(
        "--application-version",
        default="not-connected",
    )

    parser.add_argument(
        "--environment",
        default="local",
    )

    parser.add_argument(
        "--operator",
        default=None,
    )

    parser.add_argument(
        "--notes",
        default=None,
    )

    args = parser.parse_args(argv)

    root = args.root.resolve()

    report_path = (
        args.report
        if args.report.is_absolute()
        else root / args.report
    )

    try:
        report = run_harness(
            repository_root=root,
            report_path=report_path,
            application_version=args.application_version,
            environment=args.environment,
            operator=args.operator,
            notes=args.notes,
        )

    except Exception as exc:
        print(
            "Evaluation harness stopped safely: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    summary = report["summary"]

    print(
        json.dumps(
            {
                "report_path": str(report_path.resolve()),
                "decision": report["decision"]["status"],
                "summary": summary,
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
            },
            indent=2,
        )
    )

    return (
        0
        if report["decision"]["status"] == "ACCEPT"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())