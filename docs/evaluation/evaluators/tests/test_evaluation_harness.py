import json
import tempfile
import unittest
from pathlib import Path

from evaluation_harness import run_harness


class EvaluationHarnessTests(unittest.TestCase):
    def test_missing_adapters_block_all_cases_without_fake_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            datasets = root / "evaluation" / "datasets"
            schemas = datasets / "schemas"
            reports = root / "evaluation" / "reports"
            schemas.mkdir(parents=True)
            reports.mkdir(parents=True)

            # Resolve fixtures from the existing docs/evaluation layout.
            evaluation_docs = Path(__file__).resolve().parents[2]
            source_datasets = evaluation_docs / "datasets"
            source_schemas = source_datasets / "schemas"
            source_report_schema = (
                evaluation_docs / "reports" / "report-schema.json"
            )

            # Copy the locked evaluation datasets without modifying them.
            for filename in (
                "rag-policy-questions-v0.2.jsonl",
                "tool-scenarios-v0.1.jsonl",
                "safety-adversarial-cases-v0.1.jsonl",
            ):
                (datasets / filename).write_bytes(
                    (source_datasets / filename).read_bytes()
                )

            # Copy the dataset validation schemas.
            for filename in (
                "rag-question.schema.json",
                "tool-scenario.schema.json",
                "safety-case.schema.json",
            ):
                (schemas / filename).write_bytes(
                    (source_schemas / filename).read_bytes()
                )

            # The report schema belongs to docs/evaluation/reports/.
            (reports / "report-schema.json").write_bytes(
                source_report_schema.read_bytes()
            )

            report_path = reports / "run.json"
            report = run_harness(
                repository_root=root,
                report_path=report_path,
                application_version="not-connected",
            )

            self.assertEqual(report["decision"]["status"], "INCOMPLETE")
            self.assertEqual(report["summary"]["defined"], 37)
            self.assertEqual(report["summary"]["passed"], 0)
            self.assertEqual(report["summary"]["blocked"], 37)
            self.assertTrue(report_path.is_file())

            stored = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["decision"]["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()