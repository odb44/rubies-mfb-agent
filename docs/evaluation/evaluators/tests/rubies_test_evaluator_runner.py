"""Unit tests for evaluator_runner.py."""

import json
import tempfile
import unittest
from pathlib import Path

from evaluator_runner import (
    CaseExecution,
    DatasetInput,
    RunConfig,
    run_evaluation,
)

_HERE = Path(__file__).resolve().parent
_SCHEMA_CANDIDATES = [
    _HERE / "report-schema.json",
    _HERE / "reports" / "report-schema.json",
    _HERE.parent / "reports" / "report-schema.json",
    _HERE.parent.parent / "reports" / "report-schema.json",
    Path("/mnt/data/report-schema.json"),
]
SCHEMA_PATH = next(
    (candidate for candidate in _SCHEMA_CANDIDATES if candidate.is_file()),
    _SCHEMA_CANDIDATES[0],
)


def simple_schema():
    """Load the report schema used by the evaluator-runner tests."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def passing_adapter(suite, case):
    """Return deterministic passing evidence."""
    return CaseExecution(
        outcome="PASSED",
        assertions=(
            {
                "assertion_id": "A-1",
                "passed": True,
                "notes": "deterministic assertion",
            },
        ),
    )


class EvaluatorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dataset_file = self.root / "cases.jsonl"
        self.dataset_file.write_text(
            '{"case_id":"CASE-1"}\n',
            encoding="utf-8",
        )

        self.datasets = [
            DatasetInput(
                "rag",
                str(self.dataset_file),
                "0.2",
                [{"case_id": "RAG-1"}],
            ),
            DatasetInput(
                "tool",
                str(self.dataset_file),
                "0.1",
                [{"scenario_id": "TOOL-1"}],
            ),
            DatasetInput(
                "safety",
                str(self.dataset_file),
                "0.1",
                [{"case_id": "SAFE-1"}],
            ),
        ]

        self.config = RunConfig(
            environment="test",
            application_version="test-build",
            run_id="test-run",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_it(self, adapters):
        return run_evaluation(
            config=self.config,
            datasets=self.datasets,
            adapters=adapters,
            report_schema=simple_schema(),
        )

    def test_all_passing_cases_can_accept(self):
        report = self.run_it(
            {
                "rag": passing_adapter,
                "tool": passing_adapter,
                "safety": passing_adapter,
            }
        )

        self.assertEqual(report["decision"]["status"], "ACCEPT")
        self.assertEqual(report["summary"]["passed"], 3)

    def test_missing_adapter_blocks_and_is_incomplete(self):
        report = self.run_it(
            {
                "rag": passing_adapter,
                "tool": passing_adapter,
            }
        )

        self.assertEqual(report["decision"]["status"], "INCOMPLETE")
        self.assertEqual(report["summary"]["blocked"], 1)

    def test_critical_failure_forces_failed_outcome_and_reject(self):
        def critical(suite, case):
            return CaseExecution(
                outcome="PASSED",
                critical_failure=True,
                critical_failures=(
                    {
                        "failure_id": "CF-1",
                        "category": "unauthorized_access",
                    },
                ),
            )

        report = self.run_it(
            {
                "rag": critical,
                "tool": passing_adapter,
                "safety": passing_adapter,
            }
        )

        self.assertEqual(report["decision"]["status"], "REJECT")
        self.assertEqual(
            report["suites"][0]["cases"][0]["outcome"],
            "FAILED",
        )
        self.assertTrue(report["suites"][0]["cases"][0]["critical_failure"])
        self.assertEqual(report["summary"]["critical_failure_count"], 1)

    def test_critical_failure_list_forces_failed_outcome(self):
        """Critical-failure evidence must count even if its flag is false."""

        def critical_list_only(suite, case):
            return CaseExecution(
                outcome="PASSED",
                critical_failure=False,
                critical_failures=(
                    {
                        "failure_id": "CF-LIST-1",
                        "category": "unauthorized_access",
                    },
                ),
            )

        report = self.run_it(
            {
                "rag": critical_list_only,
                "tool": passing_adapter,
                "safety": passing_adapter,
            }
        )

        rag_case = report["suites"][0]["cases"][0]

        self.assertEqual(rag_case["outcome"], "FAILED")
        self.assertTrue(rag_case["critical_failure"])
        self.assertEqual(
            rag_case["critical_failure_ids"],
            ["CF-LIST-1"],
        )
        self.assertEqual(report["decision"]["status"], "REJECT")
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["summary"]["critical_failure_count"], 1)

    def test_adapter_exception_blocks_case(self):
        def broken(suite, case):
            raise RuntimeError("private diagnostic")

        report = self.run_it(
            {
                "rag": broken,
                "tool": passing_adapter,
                "safety": passing_adapter,
            }
        )

        rag_case = report["suites"][0]["cases"][0]

        self.assertEqual(rag_case["outcome"], "BLOCKED")
        self.assertNotIn("private diagnostic", json.dumps(report))

    def test_duplicate_case_ids_rejected(self):
        duplicate = [
            DatasetInput(
                "rag",
                str(self.dataset_file),
                "0.2",
                [
                    {"case_id": "SAME"},
                    {"case_id": "SAME"},
                ],
            ),
        ]

        with self.assertRaises(ValueError):
            run_evaluation(
                config=self.config,
                datasets=duplicate,
                adapters={"rag": passing_adapter},
                report_schema=simple_schema(),
            )

    def test_report_written_atomically(self):
        path = self.root / "reports" / "report.json"

        report = run_evaluation(
            config=self.config,
            datasets=self.datasets,
            adapters={
                "rag": passing_adapter,
                "tool": passing_adapter,
                "safety": passing_adapter,
            },
            report_schema=simple_schema(),
            report_path=path,
        )

        self.assertTrue(path.is_file())

        saved_report = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved_report["run"]["run_id"], "test-run")
        self.assertFalse(path.with_suffix(".json.tmp").exists())
        self.assertEqual(report["decision"]["status"], "ACCEPT")

    def test_unknown_suite_rejected(self):
        with self.assertRaises(ValueError):
            run_evaluation(
                config=self.config,
                datasets=[
                    DatasetInput(
                        "unknown",
                        str(self.dataset_file),
                        "1",
                        [{"case_id": "x"}],
                    )
                ],
                adapters={},
                report_schema=simple_schema(),
            )


if __name__ == "__main__":
    unittest.main()
