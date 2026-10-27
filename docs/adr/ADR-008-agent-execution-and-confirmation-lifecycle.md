# ADR-008: Agent Execution and Confirmation Lifecycle

- **Status:** Accepted
- **Date:** 2026-10-24
- **Decision owners:** Project team
- **Related artifacts:** `docs/flows/agent-execution-flow.mmd`, `docs/flows/confirmation-and-execution-flow.mmd`, `docs/api/agent-interface.md`

## 1. Context

The Rubies MFB Customer Support Agent answers policy questions and supports account-specific requests while protecting customer data and preventing unauthorized or accidental state changes. The model may interpret requests and propose tool calls, but trusted backend components enforce identity, authorization, verification, and confirmation. The system also needs multi-turn conversations, human handoff, auditable tool calls, and safe handling of uncertain operation outcomes.

## 2. Decision drivers

- Enforce identity, ownership, authorization, and verification outside the model.
- Prevent state-changing operations before valid action-specific confirmation.
- Persist pending confirmations across restarts and prevent replay/mismatch.
- Avoid duplicate state changes on retries.
- Audit tool calls and lifecycle events while minimizing sensitive data in logs.
- Never claim success when an outcome is unknown.
- Keep initial tool execution synchronous.
- Separate conversation state from banking records and confirmation records.

## 3. Decisions

### 3.1 Trusted identity and session ownership
The Agent API requires an authenticated request and establishes trusted identity context. A `session_id` is an identifier, not authentication. Existing sessions are checked against the authenticated customer. Banking services derive customer identity from trusted backend context, not model-generated arguments or untrusted client-supplied IDs.

### 3.2 Separate persistence responsibilities
- **PostgreSQL** is the source of truth for banking records and stores durable pending-action/confirmation state and audit records.
- **Strands File Session Manager** stores conversational session state. Protect its files with filesystem access controls and appropriate retention.
- Conversation history is not authoritative for balances, transactions, authorization, or pending confirmations.

### 3.3 Action-specific confirmation
For a state-changing action, the backend validates the proposal and authorization, then persists a pending action bound to authenticated customer, session, and exact action details, with creation time, expiry, and status. It returns a human-readable summary and `confirmation_id`; the action does not execute yet. Confirmation must explicitly match the pending action. If a natural-language confirmation cannot be associated unambiguously with exactly one pending action, do not execute and ask for clarification. Declined actions are not executed.

### 3.4 Atomic consumption and idempotency
The backend atomically transitions a valid pending action to consumed/execution-in-progress before calling the Banking API. A stable idempotency key is associated with that pending action. Retries reuse the same key and must not create a second logical operation.

### 3.5 Unknown outcomes
A timeout or lost response does not prove failure. Check operation status or reconcile with the source of truth before responding. If unresolved, retain the explicit unknown state and hand off for human review. Never blindly repeat the operation.

### 3.6 Audit and privacy
Audit tool invocation, authorization decisions, confirmation request/decision, execution, retries/reconciliation, and handoff. Record tool name, action/correlation identifiers, outcome classification, and inputs/results necessary for investigation. Minimize or redact sensitive values; never log raw credentials or authentication secrets.

### 3.7 RAG and handoff
Knowledge-base answers cite source document and section. If evidence is insufficient or conflicting, abstain rather than guess and offer/initiate handoff according to policy. The designated backend component creates/routes the handoff.

### 3.8 Initial execution model
Tool calls are synchronous initially. Streaming, long-running asynchronous jobs, and event-driven execution are deferred.

## 4. Alternatives considered

- Model-enforced authorization — rejected; model output is not a security boundary.
- Execute before confirmation — rejected; permits unintended changes.
- Conversation history as the only pending-confirmation store — rejected; not an authoritative durable action record.
- Treat timeout as failure and retry blindly — rejected; first operation may have succeeded.
- Session ID as identity — rejected; identifiers do not authenticate callers.
- Unbounded natural-language confirmation when multiple actions are pending — rejected; ambiguous intent must not execute.
- Asynchronous tools from day one — deferred to keep the first version simpler.

## 5. Consequences

**Benefits:** model-independent authorization; durable, action-specific, expiring, single-use confirmation; clear recovery for retries/unknown outcomes; auditable operations with redaction; traceable RAG answers.

**Costs:** durable pending-action lifecycle; careful atomic/idempotency design; operation-status/reconciliation support; synchronous limits for long-running operations; access control and retention for session files/audit/logs.

## 6. Implementation implications

Provide authenticated request context and session ownership checks; durable pending-confirmation storage; `confirmation_id` correlation and ambiguity handling; backend authorization/verification; stable idempotency and safe retries; reconciliation for unknown outcomes; privacy-conscious audit events; protected Strands File Session Manager storage; RAG citations/abstention; tests for expired, mismatched, declined, concurrent and replayed confirmations, plus unknown outcomes.

Detailed database schemas, retention periods, and idempotency-key format belong in their respective contracts.

## 7. Acceptance criteria

Design approval is recorded in the status above. The following implementation tests are required before claiming that this lifecycle is implemented and verified: no execution before confirmation; no mismatched/replayed/expired execution; authorization independent of model output; retries do not duplicate operations; unknown outcomes are not reported as success or blindly retried; tool/action lifecycle events are auditable with sensitive data minimized; and RAG answers cite sources or abstain when evidence is insufficient.
