# Rubies MFB Customer Support Agent

An AI Engineering capstone project for building a customer-support agent
for a fictional Nigerian microfinance bank.

## Project Goals

- Provide source-grounded answers to banking policy questions.
- Support controlled access to customer banking information.
- Require confirmation for sensitive actions.
- Escalate unresolved or sensitive requests to a human agent.
- Evaluate retrieval quality, tool execution, and safety using
  versioned evaluation datasets.

## Technology

- Python
- uv for dependency and environment management
- PostgreSQL for banking persistence
- FastAPI for the banking API
- A local vector index for initial knowledge retrieval

## Development

Install dependencies:

```powershell
uv sync

Run the evaluation tests:
```powershell
uv run pytest -v