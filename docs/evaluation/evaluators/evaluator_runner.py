"""Adapter-driven evaluation runner for Rubies MFB.

This module orchestrates case execution and report assembly. It does not
implement agent calls or infer scores: a suite adapter must execute a case and
return explicit assertions/evidence. No adapter means no execution.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

OUTCOMES = {"PASSED", "FAILED", "BLOCKED", "NEEDS_REVIEW", "NOT_RUN"}
SUITE_NAMES = {"rag", "tool", "safety"}
EVALUATOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class CaseExecution:
    """Adapter result for one case; assertion checks should be explicit."""

    outcome: str
    assertions: tuple[dict[str, Any], ...] = ()
    critical_failure: bool = False
    critical_failures: tuple[dict[str, Any], ...] = ()
    scores: Mapping[str, float] | None = None
    language: str | None = None
    expected_response_language: str | None = None
    language_match_pass: bool | None = None
    content_correctness_pass: bool | None = None
    citation_pass: bool | None = None
    safety_parity_pass: bool | None = None
    handoff_pass: bool | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()
    citations: tuple[str, ...] = ()
    block_reason: str | None = None
    reviewer_notes: str | None = None


CaseAdapter = Callable[[str, dict[str, Any]], CaseExecution]


@dataclass(frozen=True)
class DatasetInput:
    suite: str
    path: str
    version: str
    records: Sequence[dict[str, Any]]
    sha256: str | None = None


@dataclass(frozen=True)
class RunConfig:
    environment: str
    application_version: str
    model: str | None = None
    prompt_version: str | None = None
    tool_schema_version: str | None = None
    retrieval_index_version: str | None = None
    embedding_model_version: str | None = None
    source_manifest_version: str | None = None
    fixture_version: str | None = None
    git_commit: str | None = None
    build_id: str | None = None
    operator: str | None = None
    run_id: str = field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:12]}")
    notes: str | None = None
    minimum_cases_per_suite: int = 1
    report_schema_path: str | None = None


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _case_id(suite: str, case: Mapping[str, Any]) -> str:
    """Resolve a case identifier using the identifier fields for its suite."""
    keys = {
        "rag": ("case_id", "id"),
        "tool": ("scenario_id", "case_id", "id"),
        "safety": ("case_id", "id"),
    }[suite]

    for key in keys:
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            return value

    raise ValueError(
        f"{suite} case is missing a non-empty identifier "
        f"({', '.join(keys)})."
    )


def _dataset_report_entry(dataset: DatasetInput) -> dict[str, Any]:
    """Build dataset provenance metadata for the report."""
    path = Path(dataset.path)
    digest = dataset.sha256

    if digest is None:
        if not path.is_file():
            raise ValueError(
                "Dataset hash was not supplied and source file does not exist: "
                f"{dataset.path}"
            )
        digest = sha256_file(path)

    if len(digest) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in digest
    ):
        raise ValueError(f"Invalid SHA-256 for dataset {dataset.path}.")

    return {
        "suite": dataset.suite,
        "path": dataset.path,
        "version": dataset.version,
        "sha256": digest.lower(),
        "case_count": len(dataset.records),
    }


def _normalise_execution(
    case_id: str,
    execution: CaseExecution,
) -> dict[str, Any]:
    """Normalise adapter output and enforce critical-failure semantics."""
    if execution.outcome not in OUTCOMES:
        raise ValueError(
            f"{case_id}: unsupported outcome {execution.outcome!r}."
        )

    # A populated critical-failure list is itself evidence of a critical
    # failure, even when the adapter forgot to set critical_failure=True.
    has_critical_failure = bool(
        execution.critical_failure or execution.critical_failures
    )

    # A critical failure can never be represented as a passing or other
    # non-failing outcome.
    outcome = "FAILED" if has_critical_failure else execution.outcome

    critical_ids = []
    for index, failure in enumerate(execution.critical_failures, start=1):
        failure_id = str(
            failure.get("failure_id") or f"CF-{case_id}-{index}"
        )
        critical_ids.append(failure_id)

    result: dict[str, Any] = {
        "case_id": case_id,
        "outcome": outcome,
        "critical_failure": has_critical_failure,
        "assertions": list(execution.assertions),
        "scores": (
            dict(execution.scores)
            if execution.scores is not None
            else None
        ),
        "language": execution.language,
        "expected_response_language": execution.expected_response_language,
        "language_match_pass": execution.language_match_pass,
        "content_correctness_pass": execution.content_correctness_pass,
        "citation_pass": execution.citation_pass,
        "safety_parity_pass": execution.safety_parity_pass,
        "handoff_pass": execution.handoff_pass,
        "tool_calls": list(execution.tool_calls),
        "citations": list(execution.citations),
        "critical_failure_ids": critical_ids,
        "block_reason": execution.block_reason,
        "reviewer_notes": execution.reviewer_notes,
    }

    return result


def _make_failure(
    case_id: str,
    failure: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert adapter-supplied critical-failure evidence into report format."""
    return {
        "failure_id": str(failure.get("failure_id") or f"CF-{case_id}"),
        "case_id": case_id,
        "category": str(
            failure.get("category") or "unspecified_critical_failure"
        ),
        "severity": "CRITICAL",
        "evidence_ref": failure.get("evidence_ref"),
        "status": failure.get("status") or "OPEN",
        "owner": failure.get("owner"),
        "notes": failure.get("notes"),
    }


def run_evaluation(
    *,
    config: RunConfig,
    datasets: Sequence[DatasetInput],
    adapters: Mapping[str, CaseAdapter],
    report_schema: Mapping[str, Any],
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute configured suites and return a report validated against schema.

    Each dataset suite must have an adapter. If no adapter exists, its cases
    are marked BLOCKED; this is deliberate and prevents fake pass results.
    Adapter exceptions block that case rather than aborting other cases.
    The overall decision is conservative: REJECT for critical/failed cases;
    otherwise INCOMPLETE if anything is blocked, under-covered, or needs review;
    ACCEPT only when every supplied case passes and minimum coverage is met.
    """
    if not config.environment.strip():
        raise ValueError("environment must be non-empty.")

    if not config.application_version.strip():
        raise ValueError("application_version must be non-empty.")

    if config.minimum_cases_per_suite < 1:
        raise ValueError("minimum_cases_per_suite must be at least 1.")

    Draft202012Validator.check_schema(report_schema)

    started = datetime.now(UTC)
    dataset_entries: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {
        name: [] for name in SUITE_NAMES
    }
    critical_failures: list[dict[str, Any]] = []
    blockers: list[str] = []

    for dataset in datasets:
        if dataset.suite not in SUITE_NAMES:
            raise ValueError(
                f"Unknown suite {dataset.suite!r}; "
                f"expected one of {sorted(SUITE_NAMES)}."
            )

        if any(
            entry["suite"] == dataset.suite
            for entry in dataset_entries
        ):
            raise ValueError(
                "Only one dataset per suite is supported in v0.1: "
                f"{dataset.suite}."
            )

        dataset_entries.append(_dataset_report_entry(dataset))
        adapter = adapters.get(dataset.suite)

        seen: set[str] = set()

        for case in dataset.records:
            case_id = _case_id(dataset.suite, case)

            if case_id in seen:
                raise ValueError(
                    f"Duplicate case identifier {case_id!r} "
                    f"in {dataset.suite} dataset."
                )

            seen.add(case_id)

            if adapter is None:
                execution = CaseExecution(
                    outcome="BLOCKED",
                    block_reason=(
                        "No execution adapter configured for suite "
                        f"{dataset.suite}."
                    ),
                )
            else:
                try:
                    execution = adapter(dataset.suite, dict(case))

                    if not isinstance(execution, CaseExecution):
                        raise TypeError(
                            "Adapter must return a CaseExecution instance."
                        )
                except Exception as exc:
                    # Keep diagnostic details out of the generated report.
                    execution = CaseExecution(
                        outcome="BLOCKED",
                        block_reason=(
                            f"Adapter error ({type(exc).__name__}); "
                            "details withheld from report."
                        ),
                        reviewer_notes=(
                            "Inspect secured evaluator logs for "
                            "diagnostic details."
                        ),
                    )

            outcome = _normalise_execution(case_id, execution)
            grouped[dataset.suite].append(outcome)

            if outcome["critical_failure"]:
                supplied = execution.critical_failures or (
                    {
                        "failure_id": f"CF-{case_id}",
                        "category": "critical_assertion_failure",
                        "evidence_ref": None,
                        "status": "OPEN",
                        "notes": (
                            "Adapter marked this case as a critical failure."
                        ),
                    },
                )

                critical_failures.extend(
                    _make_failure(case_id, item) for item in supplied
                )

            if outcome["outcome"] == "BLOCKED":
                blockers.append(
                    f"{dataset.suite}/{case_id}: "
                    f"{outcome['block_reason'] or 'blocked'}"
                )
            elif outcome["outcome"] == "NEEDS_REVIEW":
                blockers.append(
                    f"{dataset.suite}/{case_id}: needs review"
                )

    suite_results = []
    all_outcomes: list[str] = []

    for suite in ("rag", "tool", "safety"):
        cases = grouped[suite]

        counts = {
            outcome.lower(): sum(
                1 for case in cases if case["outcome"] == outcome
            )
            for outcome in (
                "PASSED",
                "FAILED",
                "BLOCKED",
                "NEEDS_REVIEW",
                "NOT_RUN",
            )
        }

        # Executed includes completed pass/fail and needs-review cases.
        executed = (
            counts["passed"]
            + counts["failed"]
            + counts["needs_review"]
        )
        defined = len(cases)

        if defined and defined < config.minimum_cases_per_suite:
            blockers.append(
                f"{suite}: only {defined} case(s); minimum is "
                f"{config.minimum_cases_per_suite}."
            )

        suite_results.append(
            {
                "suite": suite,
                "defined": defined,
                "executed": executed,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "blocked": counts["blocked"],
                "needs_review": counts["needs_review"],
                "not_run": counts["not_run"],
                "metrics": {
                    "pass_rate": (
                        counts["passed"] / executed if executed else None
                    ),
                    "coverage_rate": (
                        executed / defined if defined else 0.0
                    ),
                },
                "cases": cases,
            }
        )

        all_outcomes.extend(
            case["outcome"] for case in cases
        )

    finished = datetime.now(UTC)
    total = len(all_outcomes)

    summary = {
        "defined": total,
        "executed": sum(
            outcome in {"PASSED", "FAILED", "NEEDS_REVIEW"}
            for outcome in all_outcomes
        ),
        "passed": all_outcomes.count("PASSED"),
        "failed": all_outcomes.count("FAILED"),
        "blocked": all_outcomes.count("BLOCKED"),
        "needs_review": all_outcomes.count("NEEDS_REVIEW"),
        "not_run": all_outcomes.count("NOT_RUN"),
        "critical_failure_count": len(critical_failures),
    }

    # Any failed case or critical failure rejects. Otherwise incomplete
    # evidence or missing suite coverage prevents acceptance.
    missing_suites = SUITE_NAMES - {
        entry["suite"] for entry in dataset_entries
    }

    if critical_failures or summary["failed"] > 0:
        decision_status = "REJECT"
        rationale = [
            "At least one case failed or a critical failure was recorded."
        ]

        if blockers:
            rationale.append(
                "The run also has incomplete or review-required cases."
            )

    elif (
        missing_suites
        or blockers
        or summary["blocked"]
        or summary["needs_review"]
        or summary["not_run"]
    ):
        decision_status = "INCOMPLETE"
        rationale = [
            "Required suites or case outcomes remain incomplete."
        ]

        if missing_suites:
            rationale.append(
                "Missing suites: "
                + ", ".join(sorted(missing_suites))
                + "."
            )

        rationale.extend(blockers[:20])

    elif any(
        suite["defined"] < config.minimum_cases_per_suite
        for suite in suite_results
    ):
        decision_status = "INCOMPLETE"
        rationale = [
            "Every suite must contain at least "
            f"{config.minimum_cases_per_suite} case(s)."
        ]

    elif summary["passed"] == summary["defined"] and summary["defined"] > 0:
        decision_status = "ACCEPT"
        rationale = [
            "Every supplied case passed; all three suites met "
            "minimum case coverage."
        ]

    else:
        decision_status = "INCOMPLETE"
        rationale = [
            "No acceptance decision can be supported by the "
            "available case evidence."
        ]

    report = {
        "schema_version": "0.1",
        "run": {
            "run_id": config.run_id,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "operator": config.operator,
            "environment": config.environment,
            "evaluator_version": EVALUATOR_VERSION,
            "notes": config.notes,
        },
        "application": {
            "version": config.application_version,
            "git_commit": config.git_commit,
            "build_id": config.build_id,
        },
        "configuration": {
            "model": config.model,
            "prompt_version": config.prompt_version,
            "tool_schema_version": config.tool_schema_version,
            "retrieval_index_version": config.retrieval_index_version,
            "embedding_model_version": config.embedding_model_version,
            "source_manifest_version": config.source_manifest_version,
            "fixture_version": config.fixture_version,
            "configuration_notes": None,
        },
        "datasets": dataset_entries,
        "summary": summary,
        "suites": suite_results,
        "critical_failures": critical_failures,
        "decision": {
            "status": decision_status,
            "rationale": rationale,
            "approved_by": None,
        },
    }

    errors = sorted(
        Draft202012Validator(report_schema).iter_errors(report),
        key=lambda error: list(map(str, error.absolute_path)),
    )

    if errors:
        detail = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '$'}: "
            f"{error.message}"
            for error in errors[:10]
        )
        raise ValueError(
            f"Generated report failed schema validation: {detail}"
        )

    if report_path is not None:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)

    return report
