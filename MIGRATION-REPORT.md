# Direct Agent Tool Migration Report

Date: 2026-10-31

## Architecture changes

- Removed `apps/mcp_server/` and the retired MCP runtime backup.
- Agent tool execution now runs inside `apps/agent`.
- Added `clients/banking_api_client.py` for direct authenticated HTTP calls.
- Split registered tools into domain modules under `apps/agent/src/rubies_agent/tools/`.
- Added `services/banking_tool_executor.py` for request-scoped token propagation, approved-operation dispatch, error normalization, and observability.
- Added `orchestration/tool_policy.py` as the explicit registered-tool catalogue.
- Added `GET /api/auth/session` to the Banking API. The agent validates bearer tokens through this endpoint instead of importing Banking API authentication internals.
- Kept the Banking API authoritative for identity validation, ownership, authorization, confirmation state, persistence, and audit records.
- Normalized transaction and loan status responses to the same `success` / `data` envelope used by the agent tool executor.
- Updated the local launcher, environment example, workspace metadata, lockfile, architecture docs, and active tool contract.
- Retained ADR-006 as historical documentation and marked its MCP runtime decision as superseded by ADR-009.

## Validation performed

- Python syntax compilation passed for agent, Banking API, tests, and shared packages.
- `uv lock --check --offline` passed.
- 51 targeted tests passed across the direct Banking API client, client observability, loan-status client, and observability package tests.

## Validation limitation

The full agent and Banking API suites could not be executed in this environment because several project dependencies were unavailable locally (including Strands/AG-UI dependencies and `psycopg`). An offline workspace sync was also blocked by an uncached `torch` wheel required transitively by the knowledge-base package. The agent integration tests and the new Banking API session endpoint test therefore still need to be run in a fully provisioned project environment.

## Security and behavior notes

- No direct database access was added to the agent.
- The request-scoped bearer token is passed explicitly to each Banking API call; the HTTP client no longer stores a reusable token on the client instance.
- Sensitive actions still require the Banking API confirmation lifecycle.
- Loan eligibility fails closed while no authoritative eligibility endpoint exists.
- Human handoff is reported as queued only when the Banking API returns a case reference and status.
- `.env`, virtual environments, Python bytecode, and test caches are excluded from the delivered archive.
