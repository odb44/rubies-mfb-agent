#!/usr/bin/env python3
"""Safely bootstrap the Rubies MFB monorepo skeleton.

Run from the repository root:
    python scripts/bootstrap_rubies_project.py

Existing files are never overwritten. This script creates only missing paths.
It does not move documentation or evaluation assets and does not create uv.lock;
run `uv lock` after reviewing pyproject.toml.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()

DIRECTORIES = [
    "apps/agent/src/rubies_agent",
    "apps/agent/tests",
    "apps/banking_api/src/rubies_banking_api",
    "apps/banking_api/tests",
    "apps/loan_model/src/rubies_loan_model",
    "apps/loan_model/tests",
    "apps/mcp_server/src/rubies_mcp_server",
    "apps/mcp_server/tests",
    "packages/shared/src/rubies_shared",
    "packages/shared/tests",
    "packages/security/src/rubies_security",
    "packages/security/tests",
    "packages/knowledge_base/src/rubies_knowledge_base",
    "packages/knowledge_base/tests",
    "packages/observability/src/rubies_observability",
    "packages/observability/tests",
    "data/synthetic",
    "data/knowledge_base",
    "artifacts/models",
    "evaluation/datasets/rag_questions",
    "evaluation/datasets/tool_scenarios",
    "evaluation/datasets/safety_cases",
    "evaluation/datasets/schemas",
    "evaluation/evaluators/adapters",
    "evaluation/evaluators/tests",
    "evaluation/metrics",
    "evaluation/regression",
    "evaluation/reports",
    "tests/unit",
    "tests/integration",
    "tests/security",
    "scripts",
    "infra",
]

INIT_FILES = [
    "apps/agent/src/rubies_agent/__init__.py",
    "apps/banking_api/src/rubies_banking_api/__init__.py",
    "apps/loan_model/src/rubies_loan_model/__init__.py",
    "apps/mcp_server/src/rubies_mcp_server/__init__.py",
    "packages/shared/src/rubies_shared/__init__.py",
    "packages/security/src/rubies_security/__init__.py",
    "packages/knowledge_base/src/rubies_knowledge_base/__init__.py",
    "packages/observability/src/rubies_observability/__init__.py",
]

FILES = {
    ".gitignore": """# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Environments and secrets
.venv/
.env
.env.*
!.env.example

# Build outputs
build/
dist/
*.egg-info/

# Local runtime data; commit only reviewed synthetic fixtures
data/local/
artifacts/local/
logs/
*.log

# Editors and OS
.vscode/
.idea/
.DS_Store
Thumbs.db
""",
    ".env.example": """# Local development only. Never put real credentials in this file.
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://rubies:rubies@localhost:5432/rubies_mfb
SESSION_STORAGE_DIR=.local/sessions
VECTOR_INDEX_DIR=.local/vector_index
""",
    "pyproject.toml": """[project]
name = "rubies-mfb-agent"
version = "0.1.0"
description = "Rubies MFB Customer Support Agent capstone"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = [
  "pytest>=8.0,<9",
  "pytest-cov>=5.0,<7",
  "ruff>=0.6,<1",
  "mypy>=1.11,<2",
  "jsonschema>=4.21,<5",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests", "apps", "packages", "evaluation/evaluators/tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
check_untyped_defs = true
""",
}

def write_if_missing(relative: str, text: str) -> str:
    target = ROOT / relative
    if target.exists():
        return f"kept existing: {relative}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return f"created: {relative}"

def main() -> int:
    if not (ROOT / "docs").exists():
        print("ERROR: Run this script from the Rubies repository root (expected ./docs).", file=sys.stderr)
        return 2

    messages = []
    for directory in DIRECTORIES:
        path = ROOT / directory
        if path.exists():
            messages.append(f"kept existing directory: {directory}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            messages.append(f"created directory: {directory}")

    for relative in INIT_FILES:
        messages.append(write_if_missing(relative, '"""Rubies MFB project package."""\n'))

    for relative, text in FILES.items():
        messages.append(write_if_missing(relative, text))

    print("\n".join(messages))
    print("\nNext: review pyproject.toml, then run `uv lock` and `uv sync`.")
    print("No existing file was overwritten; documentation and locked evaluation data were not modified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
