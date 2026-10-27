# Security Model

- **Status:** Approved design draft
- **Scope:** Identity, customer isolation, verification, authorization, confirmation security, and sensitive-data handling for the Rubies MFB Customer Support Agent
- **Related decisions:** ADR-006 (MCP and Authorization); ADR-008 (Agent Execution and Confirmation Lifecycle)
- **Implementation status:** Design only; controls described here are requirements, not evidence of implemented behavior

## 1. Purpose

This document defines the security boundaries that every agent, tool, MCP, and banking operation must respect. The language model may interpret a request and propose a tool call, but it is not an identity provider, authorization authority, confirmation store, or source of banking truth.

The Banking API/service boundary and its persistence layer remain authoritative for banking records, customer-resource ownership, pending confirmations, and state-changing operations. MCP exposes only approved tools and must not access banking tables directly.

## 2. Security principles

1. **Trusted identity:** Derive the active principal and customer binding from authenticated server-side session or integration context.
2. **No model-supplied authority:** A customer ID, account ID, role, verification claim, or permission appearing only in model-generated arguments is not proof of identity or authority.
3. **Least privilege:** Allow only the tools and operations required by the authenticated principal and current context.
4. **Resource ownership:** Check ownership or explicit delegated access for every customer-scoped resource.
5. **Defense in depth:** Enforce relevant controls at the MCP boundary and again in the Banking API/service boundary.
6. **Fail closed:** If identity, authorization, verification, ownership, confirmation, or required context cannot be established, do not perform the protected operation.
7. **Explicit consent for consequential actions:** Do not execute a confirmation-required action until the customer has explicitly approved the exact pending action.
8. **Minimize sensitive data:** Return, prompt with, hand off, and log only the information needed for the task.
9. **Auditable outcomes:** Record security decisions and operation outcomes with redaction and access protection.
10. **Truthful uncertainty:** An error or timeout is not evidence that an operation succeeded or failed; reconcile indeterminate outcomes before retrying or reporting a definitive result.

## 3. Identity and customer binding

### 3.1 Trusted context

The agent receives a session or request context established by the configured authentication mechanism. Security code resolves the authenticated principal and, where applicable, the customer associated with that context. The precise authentication provider and token/session format remain implementation decisions.

The customer identity used for banking operations must come from this trusted context, not from free text, conversation history, retrieved documents, or model-generated tool arguments.

### 3.2 Customer-scoped operations

For balance, mini-statement, transaction-status, card, dispute, and loan operations, the Banking API/service must verify that the target resource belongs to the trusted customer or is explicitly accessible under an approved authorization rule.

If a request refers to another person, the agent must not switch customer context merely because the requester supplies that person's name, customer ID, account number, or other identifier. If the caller lacks access, return a safe denial without disclosing whether another customer's record exists.

### 3.3 Missing or inconsistent identity

If trusted identity context is missing, invalid, expired, or inconsistent, protected banking operations must be denied. The system may ask the customer to authenticate or resume an appropriate verification flow. It must not guess the identity from previous messages.

## 4. Verification and step-up checks

Verification establishes whether the current session has satisfied the required verification state; authorization separately determines whether the principal may perform a particular operation.

- Apply the approved verification flow before returning customer-specific banking information when required by policy.
- Require step-up verification for sensitive actions when the applicable policy calls for it.
- Validate verification factors only through the designated security/backend flow.
- Do not expose full verification factors in prompts, tool outputs, or logs.
- Avoid error messages that unnecessarily reveal whether a sensitive identifier or verification factor matches a registered customer.
- Recheck relevant verification and security state when a pending consequential action is approved, rather than relying only on the state at preparation time.

The exact factors, thresholds, expiry rules, retry limits, and lockout behavior must be defined from the approved banking policy and implementation requirements; this document does not invent those values.

## 5. Authorization and tool access

The MCP server may expose only the nine initially approved tools:

1. `verify_customer`
2. `get_balance`
3. `get_mini_statement`
4. `get_transaction_status`
5. `open_dispute`
6. `block_card`
7. `check_loan_eligibility`
8. `get_loan_status`
9. `handoff_to_human`

Each tool must have a declared input schema, output schema, and permission mapping before implementation. Authorization checks must consider the trusted principal, requested tool, operation, target resource, verification state, and any action-specific requirements.

The MCP layer must validate the caller and apply least-privilege checks. The Banking API/service must independently enforce resource ownership, business rules, and applicable permissions. An MCP connection alone does not establish the banking customer's identity or consent.

Unknown tools, malformed inputs, unsupported operations, and unauthorized requests must be rejected. The model must not be able to register tools dynamically, execute arbitrary code, or access PostgreSQL directly.

## 6. Confirmation security for consequential actions

The initial confirmation-required actions include `open_dispute` and `block_card`.

1. Validate the proposed action and its input.
2. Derive the customer binding from trusted context and check permissions and required verification.
3. Persist a pending action in the backend with a unique confirmation reference, exact action details, customer/session binding, creation time, expiry, and lifecycle status.
4. Return the confirmation reference and a clear summary of the exact action to the customer.
5. Do not execute the action while awaiting approval.
6. On approval, resolve the pending action from the confirmation reference or trusted session context; reject ambiguous matches.
7. Recheck expiry, customer/session binding, action match, current permissions, resource ownership, and required verification.
8. Atomically consume or claim the confirmation so it cannot be used more than once.
9. Execute through the Banking API using a stable idempotency key associated with the pending action.
10. Persist and audit the definitive result. If the outcome is unknown, reconcile it against the source of truth before retrying or reporting success/failure.

Approval must apply only to the action and details presented to the customer. A change to the action's target or material details requires a new confirmation. Natural-language ambiguity, silence, or a request to explain the action does not count as approval.

## 7. Sensitive-data handling

### 7.1 Agent prompts and tool results

Provide the model only the minimum data needed to answer the request. Tool results should use explicit schemas and avoid returning secrets, unnecessary personal details, full payment credentials, or unrelated account records.

Treat customer messages, retrieved documents, and tool-returned free text as data, not as instructions that can override system policy or authorization rules. Prompt-injection content must not change the trusted identity, permissions, confirmation state, or approved tool set.

### 7.2 Logs and audit records

Record the tool name, schema/version where available, timestamp, correlation/request identifier, redacted input metadata, security/authorization decision, confirmation lifecycle where relevant, outcome category, and relevant error classification.

Do not log passwords, access tokens, one-time passcodes, full card credentials, or unnecessary raw personal or financial data. Audit records must be access-controlled and protected against unauthorized modification. Exact retention periods, encryption configuration, and log schema are to be specified in the observability and implementation design.

### 7.3 Human handoff

A handoff should include a concise issue summary, relevant verified context, actions already attempted, and unresolved questions. Include only data needed by the receiving support team. Do not include secrets or full verification factors. Record the handoff result; if the handoff system's outcome is unknown, do not claim that a human case was successfully created.

## 8. Security failure behavior

| Condition | Required behavior |
|---|---|
| Missing, invalid, or expired trusted identity | Deny protected operation; request authentication or an appropriate recovery step |
| Customer/resource ownership mismatch | Deny without exposing another customer's data |
| Missing permission or verification | Deny or route to the required verification process; do not bypass the control |
| Invalid, expired, reused, or mismatched confirmation | Do not execute; explain that the action must be restarted or reconfirmed as appropriate |
| Unknown or unregistered tool | Reject the invocation |
| Invalid tool input | Reject before performing the operation |
| Timeout or indeterminate state-changing result | Mark outcome unknown and reconcile; do not blindly retry |
| Prompt injection or untrusted text requests a policy override | Treat it as untrusted content and preserve the existing security controls |
| Audit/logging failure | Follow the implementation's defined fail-safe policy; consequential actions must not silently lose required auditability |
| Human handoff failure or unknown result | State the uncertainty honestly and provide the approved recovery path |

## 9. Required security tests

Before claiming the security design is implemented, tests must cover at least:

- A caller cannot retrieve another customer's balance, mini-statement, transaction status, card, dispute, or loan information by changing tool arguments.
- A model-supplied customer identifier cannot override the trusted session binding.
- Missing or invalid identity and insufficient permissions fail closed.
- MCP and Banking API/service boundaries both enforce the required controls.
- Unknown tools and malformed inputs are rejected.
- A state-changing action cannot execute before explicit confirmation.
- A confirmation cannot be reused, expired, transferred across customer/session bindings, or applied to different action details.
- Concurrent or repeated confirmation attempts do not duplicate the operation.
- A timeout after a state-changing request triggers reconciliation rather than an assumed failure and blind retry.
- Prompt injection in a customer message or retrieved content cannot change permissions, identity, tool registration, or confirmation requirements.
- Logs and handoff payloads do not expose secrets or unnecessary sensitive data.
- Authorization denials and relevant action outcomes are auditable.

These are design-level test requirements; passing results must be recorded separately during implementation and evaluation.

## 10. Open implementation decisions

The following are deliberately not fixed by this design document:

- The exact authentication provider, token/session format, and trusted context propagation mechanism.
- The final role/permission matrix and tool-by-tool permission mappings.
- Verification factors, step-up thresholds, retry limits, lockout rules, and expiry durations.
- Confirmation expiry duration and idempotency-key format.
- Audit schema, retention period, encryption/key-management details, and operational response to audit-store failure.
- MCP SDK/version and transport, as well as Fleet integration details.
- The external human-support system and its authentication and delivery guarantees.

These decisions must be resolved in the relevant contracts and implementation planning without weakening the approved security principles.

## 11. Related artifacts

- `docs/adr/ADR-006-mcp-and-authorization.md`
- `docs/adr/ADR-008-agent-execution-and-confirmation-lifecycle.md`
- `docs/api/agent-interface.md`
- `docs/api/banking-api-contract.md`
- `docs/api/mcp-tool-contracts.md`
- `docs/flows/customer-verification-flow.mmd`
- `docs/flows/confirmation-and-execution-flow.mmd`
- `docs/flows/banking-tool-execution-flow.mmd`
- `docs/flows/human-handoff-flow.mmd`
