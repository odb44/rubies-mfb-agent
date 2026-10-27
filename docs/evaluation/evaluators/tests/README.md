# Dataset loader artifact

## Files
- `dataset_loader.py`: fail-closed JSONL reader and JSON Schema validation.
- `test_dataset_loader.py`: standard-library `unittest` tests.
- `requirements.txt`: runtime dependency.

## Target repository paths
- `evaluation/evaluators/dataset_loader.py`
- `evaluation/evaluators/tests/test_dataset_loader.py`
- Add `jsonschema>=4.21,<5` to the project's dependency management (or install from this folder's requirements file during the prototype stage).

## Run tests
From this folder:
```bash
python -m pip install -r requirements.txt
python -m unittest -v test_dataset_loader.py
```

## Contract
- JSONL blank lines are ignored.
- Every non-blank line must parse as a JSON object and validate against its schema.
- Duplicate string `id` values are rejected.
- Strict mode is the default: any issue raises `DatasetLoadError`, so callers cannot accidentally run an evaluation on a partial dataset.
- Diagnostic mode (`fail_on_invalid=False`) returns valid rows plus explicit issues. Do not use this mode for release gates.
- This module loads and validates datasets only. It does not invoke an LLM, execute tools, score outputs, or write evaluation reports.
