# Rubies MFB Customer Support Agent

An AI engineering capstone project focused on building an AI-powered customer support agent for a fictional Nigerian microfinance bank.

## Project Goals

- Provide source-grounded answers to banking policy and procedure questions.
- Support secure access to authenticated customer banking information.
- Require backend-approved confirmation for sensitive banking actions.
- Escalate unresolved or sensitive customer requests to human support.
- Evaluate retrieval quality, tool execution, and safety using versioned evaluation datasets.

## Architecture

The project is a monorepo containing the Customer Support Agent API, Banking API, frontend, and shared packages.

The agent uses in-process tools to communicate with the Banking API over HTTP through:

`apps/agent/src/rubies_agent/clients/banking_api_client.py`

There is no separate MCP server in the active runtime.

The Banking API remains the authoritative security and data boundary. It is responsible for:

- Authentication and token validation.
- Customer ownership and authorization checks.
- Sensitive-action confirmations.
- Banking data persistence.
- Audit records.

## Technology Stack

- **Python 3.11+** — application development.
- **uv** — dependency and environment management.
- **FastAPI** — Agent API and Banking API.
- **PostgreSQL** — banking data persistence.
- **Strands Agents** — agent execution and orchestration.
- **Local vector index** — initial policy retrieval.
- **React / TypeScript** — frontend application.

## Local Development

### Prerequisites

- Python 3.11 or later.
- `uv`.
- PostgreSQL.
- Node.js and npm for frontend development.
- AWS credentials and an appropriately configured Amazon Bedrock model.

### Setup

1. Clone the repository.
2. Create a local `.env` file from `.env.example`.
3. Configure the required environment variables, including:
   - Database connection.
   - A strong local `JWT_SECRET_KEY`.
   - AWS region and credentials.
   - Bedrock model configuration.
   - Other application-specific settings.
4. Install the Python workspace dependencies:

   ```powershell
   uv sync
   ```

5. If running the frontend independently, install its dependencies from the `frontend/` directory.

### Start the Application

From the repository root:

```powershell
uv run python run_local.py
```

The local launcher starts the Banking API, Agent API, and frontend.

The launcher does not start a separate MCP process. The agent uses `BANKING_API_BASE_URL`, which defaults to `http://127.0.0.1:8000`, for session validation and banking tool calls.

**Security note:** Never commit `.env` files, AWS credentials, database passwords, JWT secrets, or other sensitive configuration.

## Tests

Run the available test suite from the repository root:

```powershell
uv run pytest -q
```

Test locations include:

- `apps/agent/tests/` — agent-specific tests.
- `apps/banking_api/tests/` — Banking API tests.
- Shared package and evaluation test directories.

## Architecture Decisions

Architecture decisions and supporting documentation are maintained in `docs/README.md`.

See ADR-009 for the current direct-agent-tool architecture and the associated security boundary decisions.


## Author
### Bamigbele Oluwaseun
