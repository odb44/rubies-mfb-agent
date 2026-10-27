"""Fail-closed JSONL dataset loader for the Rubies MFB evaluator.

The loader validates each dataset row against its JSON Schema and returns
normalised records with stable source locations. It deliberately does not
execute scenarios or score model responses.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError


@dataclass(frozen=True)
class DatasetIssue:
    """A dataset validation problem with a file and line location."""

    path: str
    line: int
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class LoadedDataset:
    """Validated rows and non-fatal diagnostics for one dataset."""

    dataset_type: str
    path: str
    records: tuple[dict[str, Any], ...]
    issues: tuple[DatasetIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def count(self) -> int:
        return len(self.records)


class DatasetLoadError(ValueError):
    """Raised when a dataset cannot safely be loaded for evaluation."""

    def __init__(self, message: str, issues: Iterable[DatasetIssue] = ()) -> None:
        super().__init__(message)
        self.issues = tuple(issues)


SCHEMA_FILENAMES = {
    "rag_questions": "rag-question.schema.json",
    "tool_scenarios": "tool-scenario.schema.json",
    "safety_cases": "safety-case.schema.json",
}

DEFAULT_DATASET_FILENAMES = {
    "rag_questions": "rag-policy-questions-v0.2.jsonl",
    "tool_scenarios": "tool-scenarios-v0.1.jsonl",
    "safety_cases": "safety-adversarial-cases-v0.1.jsonl",
}


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise DatasetLoadError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetLoadError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def _validator_for(schema_path: Path) -> Draft202012Validator:
    schema = _read_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise DatasetLoadError(f"Invalid JSON Schema {schema_path}: {exc.message}") from exc
    return Draft202012Validator(schema)


def load_jsonl_dataset(
    dataset_path: str | Path,
    schema_path: str | Path,
    *,
    dataset_type: str,
    fail_on_invalid: bool = True,
) -> LoadedDataset:
    """Load JSONL, validate every row, and fail closed by default.

    Blank lines are ignored. Each non-blank line must contain one JSON object.
    Duplicate case IDs are rejected. If ``fail_on_invalid`` is false, valid
    rows are returned alongside issues; callers must not use partial results
    for a release gate.
    """
    data_path = Path(dataset_path)
    schema_file = Path(schema_path)
    validator = _validator_for(schema_file)
    records: list[dict[str, Any]] = []
    issues: list[DatasetIssue] = []
    seen_ids: dict[str, int] = {}

    try:
        handle = data_path.open("r", encoding="utf-8")
    except FileNotFoundError as exc:
        raise DatasetLoadError(f"Required dataset not found: {data_path}") from exc

    with handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                issues.append(DatasetIssue(
                    str(data_path), line_number, "INVALID_JSON",
                    f"Invalid JSON at column {exc.colno}: {exc.msg}",
                ))
                continue

            if not isinstance(item, dict):
                issues.append(DatasetIssue(
                    str(data_path), line_number, "ROW_NOT_OBJECT",
                    "Each JSONL record must be a JSON object.",
                ))
                continue

            errors = sorted(
                validator.iter_errors(item),
                key=lambda error: (list(map(str, error.absolute_path)), error.message),
            )
            if errors:
                for error in errors:
                    location = ".".join(str(part) for part in error.absolute_path) or "$"
                    issues.append(DatasetIssue(
                        str(data_path), line_number, "SCHEMA_VALIDATION",
                        f"{location}: {error.message}",
                    ))
                continue

            case_id = item.get("id")
            if isinstance(case_id, str):
                if case_id in seen_ids:
                    issues.append(DatasetIssue(
                        str(data_path), line_number, "DUPLICATE_ID",
                        f"Duplicate id {case_id!r}; first seen on line {seen_ids[case_id]}.",
                    ))
                    continue
                seen_ids[case_id] = line_number

            # Return a detached JSON-compatible object; callers can safely mutate it.
            records.append(json.loads(json.dumps(item, ensure_ascii=False)))

    result = LoadedDataset(
        dataset_type=dataset_type,
        path=str(data_path),
        records=tuple(records),
        issues=tuple(issues),
    )
    if issues and fail_on_invalid:
        summary = f"{data_path} contains {len(issues)} validation issue(s); refusing partial dataset."
        raise DatasetLoadError(summary, issues)
    return result


def load_evaluation_datasets(
    *,
    datasets_dir: str | Path,
    schemas_dir: str | Path,
) -> dict[str, LoadedDataset]:
    """Load all three required datasets; return only if all validate cleanly."""
    root = Path(datasets_dir)
    schema_root = Path(schemas_dir)
    loaded: dict[str, LoadedDataset] = {}
    failures: list[DatasetIssue] = []

    for dataset_type, filename in DEFAULT_DATASET_FILENAMES.items():
        schema_path = schema_root / SCHEMA_FILENAMES[dataset_type]
        dataset_path = root / filename
        try:
            loaded[dataset_type] = load_jsonl_dataset(
                dataset_path,
                schema_path,
                dataset_type=dataset_type,
                fail_on_invalid=True,
            )
        except DatasetLoadError as exc:
            failures.extend(exc.issues)
            if not exc.issues:
                failures.append(DatasetIssue(
                    str(dataset_path), 0, "LOAD_FAILURE", str(exc)
                ))

    if failures:
        details = "; ".join(
            f"{issue.path}:{issue.line} [{issue.code}] {issue.message}"
            for issue in failures[:10]
        )
        remainder = len(failures) - min(len(failures), 10)
        suffix = f"; and {remainder} more" if remainder else ""
        raise DatasetLoadError(
            f"Evaluation dataset loading failed with {len(failures)} issue(s): {details}{suffix}",
            failures,
        )

    return loaded
