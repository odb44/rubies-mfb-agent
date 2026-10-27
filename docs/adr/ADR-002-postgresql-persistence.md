# ADR-002: PostgreSQL Persistence

- **Status:** Accepted
- **Decision date:** 2026-10-24
- **Scope:** Authoritative persistence for banking-domain records

## Context

The Rubies MFB Customer Support Agent needs durable records for customers, accounts, transactions, cards, disputes, loans, pending confirmations, and audit events. These records must remain consistent across conversations and must not depend on the language model's memory or the lifecycle of an agent session.

The approved architecture also uses other forms of storage for different purposes: Strands File Session Manager stores conversation/session state, a local vector index supports knowledge retrieval, and versioned local artifacts store loan-model versions. Those stores serve different purposes and must not become competing sources of truth for banking records.

## Decision

Use **PostgreSQL as the authoritative persistence layer for banking-domain data** and for other structured, transactional records assigned to the banking API, including pending-action confirmation state and audit history.

The banking API owns access to this persistence boundary. The agent, retrieval pipeline, loan model, and MCP interface must use approved application or service contracts rather than directly modifying banking tables.

The conceptual data model includes the following record groups:

- **Customer and identity references:** synthetic customer records and the identifiers needed to associate a trusted session with the correct customer.
- **Accounts:** account metadata and the relationships required to retrieve account information under authorization checks.
- **Transactions:** transaction references, amounts, timestamps, status, and other fields required to explain transaction outcomes and support disputes.
- **Cards:** card metadata and status, including whether a card is active or blocked. Sensitive card credentials must not be stored in logs or exposed to the model.
- **Disputes:** dispute records, lifecycle status, references to relevant transactions, and the history needed to track resolution.
- **Loans:** loan application/status records and the fields needed to return approved loan-status information. Model predictions are not authoritative loan decisions unless the defined business process explicitly makes them so.
- **Pending confirmations:** action type, customer/session binding, a summary of the proposed action, expiry, approval state, single-use consumption state, and relevant idempotency reference.
- **Audit events:** actor or trusted session reference, action/tool name, relevant input and result metadata, outcome, timestamp, and correlation identifier, with sensitive values redacted or excluded.

The exact physical schema, constraints, indexes, migrations, and retention periods will be specified during implementation and must preserve the ownership and safety rules in this ADR.

## Rationale

1. **Transactional consistency:** Banking operations require durable, consistent state and controlled updates.
2. **Clear source of truth:** A single authoritative database prevents conversation history, retrieval indexes, and model outputs from becoming alternate authorities for balances or transaction status.
3. **Referential integrity:** Relational constraints can help preserve relationships among customers, accounts, transactions, cards, disputes, loans, and confirmation records.
4. **Auditable workflows:** Pending actions and audit events can be persisted and queried independently of an agent conversation's in-memory state.
5. **Testability:** Synthetic fixtures and integration tests can verify persistence behavior and failure handling against a known database schema.

## Alternatives considered

### Treat conversation/session files as the banking record store

**Rejected.** Session files support conversational continuity, not transactional banking persistence. A conversation may expire, be unavailable, or contain stale or model-generated statements.

### Use the vector index as a source of truth

**Rejected.** The vector index is for retrieving relevant knowledge content. It is not suitable as the authoritative store for balances, transaction states, or confirmation consumption.

### Let each application write directly to shared banking tables

**Rejected.** Direct table access from multiple components would blur ownership and make it harder to enforce authorization, validation, and audit requirements consistently. The banking API is the defined application boundary for banking-domain operations.

## Consequences

### Positive

- Banking state remains durable and independent of agent-session lifecycle.
- The architecture has a clear authority for structured banking records.
- Confirmation and audit state can be checked even if a conversation is resumed or retried.
- Relational constraints and transactions can support safe updates.

### Trade-offs and constraints

- Database migrations and schema compatibility need explicit management.
- Database credentials and permissions must be scoped to the services that need them.
- Availability and recovery procedures must be defined for the PostgreSQL instance.
- The application must handle transaction failures, duplicate requests, and uncertain outcomes without inventing a success or failure result.

## Required integrity and safety rules

1. **Authorization before access:** Resolve the customer from trusted identity/session context and verify authorization before reading or changing customer-owned records.
2. **No model-supplied identity:** Do not accept a customer identifier supplied only by the model as proof of which customer's data to access.
3. **Confirmation state is durable:** Sensitive actions must use persisted, expiring, single-use confirmation records. A confirmation must be bound to the intended action and trusted customer/session context.
4. **Idempotent execution:** Where an operation may be retried, use an idempotency mechanism or equivalent duplicate protection. A timeout alone does not prove that the operation failed.
5. **Atomic state changes:** Keep related database changes in a transaction when they must succeed or fail together.
6. **Audit without leakage:** Record the required tool/action metadata and outcome, but do not log secrets, full authentication factors, or unnecessary sensitive customer data.
7. **No unsupported claims:** If persistence lookup fails or returns an indeterminate result, the agent must communicate uncertainty or hand off rather than fabricate a balance, status, or completed action.

## Relationship to other storage

| Store | Intended responsibility | Not authoritative for |
|---|---|---|
| PostgreSQL | Banking records, pending confirmations, structured audit history | Conversation continuity, semantic retrieval, model binaries |
| Strands File Session Manager | Conversation/session state | Balances, transaction status, action authorization, confirmation consumption |
| Local vector index | Searchable representation of approved knowledge documents | Live banking records or customer-specific transaction truth |
| Versioned model artifacts | Loan-model versions, manifests, and associated evaluation assets | Customer account state or final banking records |
| Evaluation files/reports | Test cases, scores, regression results | Production banking state |

## Intentionally deferred

This ADR does not define the final table-by-table schema, SQL migration scripts, database sizing, deployment topology, backup schedule, retention period, or production high-availability design. Those details will be established in the implementation and operational design without changing PostgreSQL's role as the authoritative banking persistence layer.

## Acceptance criteria

This decision is considered implemented when:

- Banking-domain records are persisted in PostgreSQL through the approved banking API boundary.
- Conversation files, vector indexes, and model artifacts are not treated as sources of truth for banking records.
- Pending confirmations survive conversation restarts and enforce expiry and single-use consumption.
- Sensitive reads and mutations are authorized using trusted identity context.
- Retry, timeout, audit, and data-redaction behavior are covered by tests.
- Schema changes are managed through versioned migrations.
