# Rubies MFB Customer Support Agent — Documentation Index

**Documentation status:** The architecture and design decisions listed here are the approved project baseline. Implementation and test status are reported separately.

## Architecture

- [Architecture sketch](architecture/architecture-sketch.md) — end-to-end logical view and request paths.
- [Component architecture](architecture/component-architecture.md) — component responsibilities and interfaces.
- [Deployment architecture](architecture/deployment-architecture.md) — intended runtime boundaries and communication paths; physical hosting choices remain as documented.
- [Data architecture](architecture/data-architecture.md) — data ownership, persistence, and lifecycle boundaries.

### Architecture diagrams

- [System context](architecture/diagrams/system-context.mmd)
- [Component diagram](architecture/diagrams/component-diagram.mmd)
- [Deployment diagram](architecture/diagrams/deployment-diagram.mmd)
- [Data-flow diagram](architecture/diagrams/data-flow-diagram.mmd)

## Architecture Decision Records (ADRs)

- [ADR-001 — Monorepo and service boundaries](adr/ADR-001-monorepo-and-service-boundaries.md)
- [ADR-002 — PostgreSQL persistence](adr/ADR-002-postgresql-persistence.md)
- [ADR-003 — Local vector index](adr/ADR-003-local-vector-index.md)
- [ADR-004 — Local model artifacts](adr/ADR-004-local-model-artifacts.md)
- [ADR-006 — Historical MCP authorization decision (superseded)](adr/ADR-006-mcp-and-authorization.md)
- [ADR-007 — Observability and evaluation](adr/ADR-007-observability-and-evaluation.md)
- [ADR-008 — Agent execution and confirmation lifecycle](adr/ADR-008-agent-execution-and-confirmation-lifecycle.md)
- [ADR-009 — Direct agent tool execution](adr/ADR-009-direct-agent-tool-execution.md)

**ADR-005 — Fleet adapter** is intentionally deferred until Fleet integration requirements are confirmed. Its absence is deliberate, not an overlooked accepted decision.

## Agent and Banking API contracts

- [Agent interface](api/agent-interface.md)
- [Banking API contract](api/banking-api-contract.md)
- [Agent tool contracts](api/agent-tool-contracts.md)

## Operational and user flows

- [Agent execution](flows/agent-execution-flow.mmd)
- [Conversation](flows/conversation-flow.mmd)
- [Customer verification](flows/customer-verification-flow.mmd)
- [Banking tool execution](flows/banking-tool-execution-flow.mmd)
- [Confirmation and execution](flows/confirmation-and-execution-flow.mmd)
- [Dispute and confirmation](flows/dispute-and-confirmation-flow.mmd)
- [RAG retrieval](flows/rag-retrieval-flow.mmd)
- [Human handoff](flows/human-handoff-flow.mmd)

## Design guardrails

- PostgreSQL is authoritative for banking records, pending confirmations, and audit records.
- Strands File Session Manager stores conversation/session state only; it is not authentication or the source of truth for banking records or approval state.
- The model proposes actions; trusted backend components enforce identity, permissions, verification, confirmation, and execution.
- State-changing actions require a persisted, action-specific, expiring, single-use confirmation before execution.
- Unknown execution outcomes are reconciled; they are not blindly retried or reported as success.
- Policy answers require source-backed citations; insufficient or conflicting evidence requires abstention or clarification.
- Every tool call is logged with tool name, redacted inputs, result/status, and correlation context.

This index describes the approved design artifacts. It is not a statement that the application has been implemented, deployed, or passed its tests.