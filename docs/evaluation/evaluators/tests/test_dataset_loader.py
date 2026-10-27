"""Unit tests for evaluation/evaluators/dataset_loader.py."""
import json
import tempfile
import unittest
from pathlib import Path

from dataset_loader import (
    DatasetLoadError,
    load_evaluation_datasets,
    load_jsonl_dataset,
)


class DatasetLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.schema = self.root / "schema.json"
        self.schema.write_text(json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["id", "question"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "question": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        }), encoding="utf-8")
        self.data = self.root / "data.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def load(self, text, fail_on_invalid=True):
        self.data.write_text(text, encoding="utf-8")
        return load_jsonl_dataset(
            self.data, self.schema, dataset_type="test",
            fail_on_invalid=fail_on_invalid,
        )

    def test_loads_valid_rows_and_ignores_blank_lines(self):
        result = self.load('\n{"id":"A","question":"hello"}\n\n{"id":"B","question":"hi"}\n')
        self.assertEqual(result.count, 2)
        self.assertTrue(result.valid)

    def test_rejects_malformed_json(self):
        with self.assertRaises(DatasetLoadError) as caught:
            self.load('{"id":')
        self.assertEqual(caught.exception.issues[0].code, "INVALID_JSON")
        self.assertEqual(caught.exception.issues[0].line, 1)

    def test_rejects_non_object_row(self):
        with self.assertRaises(DatasetLoadError) as caught:
            self.load('["not", "an object"]')
        self.assertEqual(caught.exception.issues[0].code, "ROW_NOT_OBJECT")

    def test_rejects_schema_invalid_row(self):
        with self.assertRaises(DatasetLoadError) as caught:
            self.load('{"id":"A"}')
        self.assertEqual(caught.exception.issues[0].code, "SCHEMA_VALIDATION")

    def test_rejects_duplicate_ids(self):
        with self.assertRaises(DatasetLoadError) as caught:
            self.load('{"id":"A","question":"one"}\n{"id":"A","question":"two"}')
        self.assertEqual(caught.exception.issues[0].code, "DUPLICATE_ID")

    def test_non_strict_mode_reports_issues_without_hiding_them(self):
        result = self.load(
            '{"id":"A","question":"valid"}\n{"id":}\n',
            fail_on_invalid=False,
        )
        self.assertEqual(result.count, 1)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "INVALID_JSON")

    def test_missing_dataset_fails(self):
        with self.assertRaises(DatasetLoadError):
            load_jsonl_dataset(
                self.root / "missing.jsonl", self.schema,
                dataset_type="test",
            )

    def test_missing_schema_fails(self):
        with self.assertRaises(DatasetLoadError):
            load_jsonl_dataset(
                self.data, self.root / "missing-schema.json",
                dataset_type="test",
            )

    def test_invalid_schema_fails(self):
        self.schema.write_text('{"type": "not-a-real-json-schema-type"}', encoding="utf-8")
        self.data.write_text('{"id":"A","question":"hello"}', encoding="utf-8")
        with self.assertRaises(DatasetLoadError):
            load_jsonl_dataset(self.data, self.schema, dataset_type="test")

    def test_all_required_datasets_must_load(self):
        datasets = self.root / "datasets"
        schemas = self.root / "schemas"
        datasets.mkdir()
        schemas.mkdir()
        for name in ("rag-question.schema.json", "tool-scenario.schema.json", "safety-case.schema.json"):
            (schemas / name).write_text(self.schema.read_text(encoding="utf-8"), encoding="utf-8")
        (datasets / "rag-policy-questions-v0.2.jsonl").write_text(
            '{"id":"R1","question":"hello"}', encoding="utf-8"
        )
        (datasets / "tool-scenarios-v0.1.jsonl").write_text(
            '{"id":"T1","question":"hello"}', encoding="utf-8"
        )
        # Deliberately omit safety dataset: loading must fail closed.
        with self.assertRaises(DatasetLoadError):
            load_evaluation_datasets(datasets_dir=datasets, schemas_dir=schemas)


if __name__ == "__main__":
    unittest.main()
