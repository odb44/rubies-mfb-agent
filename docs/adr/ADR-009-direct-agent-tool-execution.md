# ADR-009: Direct Agent Tool Execution

- **Status:** Accepted
- **Date:** 2026-10-31
- **Supersedes:** ADR-006 for the active runtime topology

## Context

The initial repository used a separate MCP server between the agent and Banking API. The capstone now uses direct tool execution inside the agent runtime to reduce service and deployment complexity. This does not make the agent authoritative for banking state or authorization.

## Decision

1. Agent tools execute within `apps/agent`.
2. The agent calls the Banking API over HTTP through `rubies_agent.clients.banking_api_client.BankingAPIClient`.
3. The agent never accesses banking tables or connects directly to the Banking API database.
4. The Banking API remains authoritative for bearer-token validation, customer identity, ownership, authorization, domain validation, confirmation state, persistence, and audit events.
5. The agent validates the current bearer token through the Banking API session endpoint before invoking the model. The same request-scoped token is forwarded to each banking tool call.
6. Sensitive operations continue to require backend-approved, action-bound confirmation and explicit customer consent.
7. Loan-model output remains a demonstration only and must not be represented as a lending decision.
8. Human handoff is reported as queued only after the Banking API returns a valid case reference and status.

## Consequences

- No separate MCP server process or direct project dependency is required for the active runtime. A transitive `mcp` package may remain in the lockfile if a third-party dependency such as Strands requires it.
- Direct client and tool tests replace MCP transport tests.
- Banking API authorization must remain independently enforced; agent-side checks are not a substitute.
- ADR-006 is retained as historical context but is superseded for the active runtime topology.
