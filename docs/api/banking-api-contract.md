# Banking API Contract

- **Status:** Accepted
- **Version:** 0.1
- **Purpose:** Define the internal API boundary used by the agent's approved tools to access banking capabilities.
- **Related artifacts:**
  - `docs/architecture/architecture-sketch.md`
  - `docs/flows/agent-execution-flow.mmd`
  - `docs/flows/confirmation-and-execution-flow.mmd`
  - `docs/adr/ADR-008-agent-execution-and-confirmation-lifecycle.md`
  - `docs/api/agent-interface.md`

## 1. Purpose and scope

The Banking API is the trusted application boundary for customer/account data and banking operations used by the Rubies MFB Customer Support Agent.

The agent must not access PostgreSQL directly. It requests banking capabilities through approved tools, and those tools call the Banking API. The Banking API validates the trusted request context, enforces customer ownership and permissions, performs domain validation, persists changes, and returns structured results.

This contract defines responsibilities and operation groups. It does not yet prescribe final endpoint paths, database tables, request/response JSON schemas, or implementation code; those details must be agreed before implementation.

## 2. Core rules

1. **Trusted identity:** Customer identity is derived from authenticated backend context. A customer ID supplied by the model is not authoritative.
2. **Customer isolation:** Every customer-scoped read or write is checked against the trusted customer identity and resource ownership.
3. **Backend authorization:** Permissions and required verification are enforced by backend code, not by prompts or model decisions.
4. **Confirmation before changes:** A state-changing action requiring customer confirmation cannot execute until a valid, unexpired, unused confirmation is verified.
5. **Durable confirmation state:** Pending actions and their lifecycle are stored durably in PostgreSQL, not only in conversation history.
6. **Safe retries:** Operations that may be retried use an idempotency mechanism where duplicate execution would be harmful.
7. **Unknown outcomes:** A timeout does not prove failure. The caller must check operation status or reconcile before retrying.
8. **Auditability:** Tool calls, authorization decisions, confirmation lifecycle events, and operation outcomes are auditable. Sensitive values are minimized or redacted.
9. **Data minimization:** Return only the fields needed for the customer request; do not expose another customer's data or unnecessary sensitive details.
10. **Synthetic environment:** Initial development and evaluation use synthetic customers and banking records only.

## 3. Responsibilities

### Banking API owns

- Customer-scoped account and transaction data access.
- Transaction-status lookup.
- Dispute creation and its required confirmation lifecycle.
- Card-blocking requests and their required confirmation lifecycle.
- Loan-status and loan-eligibility requests.
- Pending-action persistence and validation, where applicable to the operation.
- Domain validation, persistence, operation status, and audit events.
- Structured success, validation, authorization, not-found, conflict, and unknown-outcome results.

### Agent layer owns

- Understanding the customer's natural-language request.
- Selecting among registered, approved tools.
- Asking for missing information.
- Presenting action summaries and requesting confirmation.
- Explaining returned results without inventing facts.
- RAG retrieval and source citations for policy/product questions.
- Initiating human handoff when required.

The agent layer does not independently grant permissions, invent customer identity, or treat its own conversation history as the source of truth for banking state.

## 4. Operation groups

The following are logical operation groups, not yet final endpoint definitions.

| Operation group | Required behaviour | State-changing? |
|---|---|---:|
| Customer verification | Verify the customer using the approved verification flow and return a structured verification result. Do not return secrets or expose unnecessary identity data. | May update verification state |
| Balance lookup | Return the authenticated customer's permitted account balance(s) and currency/context required to interpret them. | No |
| Mini-statement | Return a bounded set of recent transactions belonging to the authenticated customer. | No |
| Transaction status | Look up a transaction using an allowed reference and verify that it belongs to the authenticated customer. | No |
| Open dispute | Validate dispute details, associate the dispute with the authenticated customer's eligible transaction/account, and create the dispute only after required confirmation. | Yes |
| Block card | Validate card ownership and current card state; block only after required confirmation and authorization. | Yes |
| Loan eligibility | Apply the approved eligibility logic and return the result plus permitted explanation fields. Eligibility is not a promise of loan approval. | No, unless a later approved workflow changes this |
| Loan status | Return only the authenticated customer's permitted loan status/details. | No |
| Human handoff | Create or route a support handoff and return a definitive handoff status/reference where available. | Creates support record |

A later tool/API contract must specify the exact input and output schema for each operation group.

## 5. Request context and customer identity

Every customer-scoped operation must receive trusted identity and authorization context from the authenticated application boundary.

- The caller must not be able to choose another customer by passing a different customer ID in tool arguments.
- If an operation requires a customer identifier internally, the backend derives or validates it against the trusted identity context.
- A transaction reference, card identifier, account identifier, loan identifier, or dispute identifier must be checked for ownership before data is returned or modified.
- Missing, invalid, or insufficient verification must result in a structured rejection or a request for the required verification step.
- Session IDs and confirmation IDs are correlation identifiers; neither is proof of identity.

The exact authentication mechanism and context propagation format are intentionally deferred to the security contract.

## 6. Confirmation boundary for state-changing operations

For a state-changing operation requiring confirmation:

1. The agent tool submits a proposed action to the trusted backend.
2. The backend validates the request and current authorization.
3. The backend persists a pending action bound to the trusted customer, session, and exact action details, with creation time, expiry, and lifecycle status.
4. The API returns a confirmation reference and a customer-readable summary.
5. No state change occurs while the action is merely pending.
6. On confirmation, the backend checks the reference, ownership, expiry, single-use state, action match, and current authorization again.
7. The backend atomically consumes the confirmation before execution and applies idempotency protection.
8. The result and lifecycle events are persisted and audited.

An ambiguous, expired, declined, mismatched, or previously consumed confirmation must not execute the action.

## 7. Result and error semantics

The Banking API returns structured results rather than relying on free-form text for control flow. Exact schemas are to be defined in the operation-specific contracts.

The implementation must distinguish at least these outcome classes:

- **Success:** The operation completed and its result is known.
- **Validation failure:** Required data is missing or invalid.
- **Unauthenticated / unauthorized:** The request lacks required trusted identity, permission, ownership, or verification.
- **Not found or not accessible:** The requested resource cannot be returned to this caller. Responses must not disclose another customer's resource existence.
- **Conflict:** The requested action is incompatible with the current resource state, such as an already-blocked card or a non-pending confirmation.
- **Definitive failure:** The operation failed and the failure is known.
- **Unknown outcome:** The system cannot yet establish whether the operation completed. The caller must not report success or blindly retry; status lookup/reconciliation is required.

The agent should receive enough structured information to respond safely, but not internal stack traces, secrets, or unnecessary protected data.

## 8. Audit requirements

For each tool/API interaction, record, as applicable:

- tool and operation name;
- action, request, and correlation identifiers;
- trusted actor/customer reference using the project's approved logging-safe representation;
- authorization and verification decision;
- confirmation lifecycle event;
- redacted/minimized input summary;
- result classification and operation reference;
- retry/reconciliation activity;
- timestamp and relevant service outcome.

Do not log passwords, tokens, secrets, full payment credentials, or unnecessary raw personal/financial data. The detailed audit schema and retention period remain open decisions for the observability/security artifacts.

## 9. Initial operational assumptions

- Initial tool execution is synchronous.
- PostgreSQL is the source of truth for banking records and durable pending-action state.
- The local vector index is used for knowledge-base retrieval; it is not the source of banking truth.
- The loan model returns an eligibility assessment and permitted explanation; the Banking API remains responsible for validating the request context and returning the result.
- Human handoff must be confirmed by the handoff component before the agent tells the customer it has been completed.
- The initial implementation uses synthetic data only.

## 10. Explicitly out of scope for this draft

This draft does not decide:

- final endpoint paths, HTTP methods, or versioning strategy;
- exact request/response JSON schemas for each operation;
- authentication token format or identity propagation mechanism;
- final database schema and migration details;
- confirmation expiry duration and idempotency-key format;
- precise error-code catalogue;
- audit retention period and redaction rules beyond the principles above;
- external integrations or production banking connectivity.

These decisions should be made in the corresponding detailed contracts, without changing the locked repository structure.

## 11. Review checklist

- [ ] The Banking API is the only application boundary for agent access to banking data and operations.
- [ ] Customer identity is derived from trusted backend context.
- [ ] Ownership and authorization are enforced for every customer-scoped resource.
- [ ] State-changing actions cannot execute before valid confirmation where required.
- [ ] Pending confirmations are durable, action-bound, expiring, and single-use.
- [ ] Retries and unknown outcomes are handled safely.
- [ ] Tool/API interactions are auditable without unnecessary sensitive-data exposure.
- [ ] Operation results are structured and distinguish definitive from unknown outcomes.
- [ ] Initial development and evaluation use synthetic data only.
- [ ] The scope boundaries and deferred decisions are accepted before detailed endpoint design.
