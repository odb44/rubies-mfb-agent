# Direct Agent Tool Contracts

- **Status:** Accepted
- **Version:** 0.1
- **Purpose:** Define the contract and security boundary for exposing approved Rubies MFB agent capabilities through the agent runtime.
- **Repository path:** `docs/api/agent-tool-contracts.md`
- **Related artifacts:**
  - `docs/api/agent-interface.md`
  - `docs/api/banking-api-contract.md`
  - `docs/flows/agent-execution-flow.mmd`
  - `docs/flows/confirmation-and-execution-flow.mmd`
  - `docs/adr/ADR-009-direct-agent-tool-execution.md`
  - `docs/adr/ADR-008-agent-execution-and-confirmation-lifecycle.md`

## 1. Purpose and scope

The agent runtime exposes a controlled set of capabilities to the agent through direct agent tool execution. It is an adapter and authorization boundary, not a replacement for the Banking API or the agent's own orchestration.

The agent runtime must expose only explicitly registered tools. Each tool has a stable name, a validated input schema, a defined output shape, and a clear permission requirement. Tool descriptions help the model select capabilities; descriptions and model behaviour do not enforce security.

This document defines the initial tool catalogue and behavioural contract. Exact JSON Schema definitions, HTTP client configuration, and implementation details should be finalized when implementing the agent runtime, without changing the locked repository layout.

## 2. Architectural boundary

The expected call path is:

1. The agent selects a registered tool and submits arguments.
2. The agent runtime validates the tool name and argument schema.
3. The authenticated agent API establishes the trusted caller/customer context from the authenticated host/backend context; it does not trust a model-supplied customer identifier.
4. The agent applies narrow input validation and operation allowlists and any required verification checks.
5. The tool adapter calls the Banking API using trusted context.
6. The Banking API independently enforces resource ownership, domain rules, authorization, confirmation lifecycle, and persistence.
7. The agent runtime returns a structured result to the agent and records the tool invocation outcome.

The agent runtime must not connect directly to PostgreSQL for banking reads or writes. It must not bypass Banking API checks. Tool permissions are enforced in backend-controlled code, not by prompt instructions.

## 3. Tool catalogue

The active tool catalogue contains customer-facing tools plus supporting confirmation tools:

| Tool name | Purpose | Access class | Confirmation requirement |
|---|---|---|---|
| `verify_customer` | Run the approved customer verification flow and return a structured verification result. | Verification | Depends on the verification step; never return secrets |
| `get_customer_accounts` | List active accounts belonging to the authenticated customer. | Read | No state-changing confirmation |
| `get_balance` | Retrieve permitted balance information for the authenticated customer. | Read | No state-changing confirmation |
| `get_mini_statement` | Retrieve a bounded list of recent transactions for the authenticated customer. | Read | No state-changing confirmation |
| `get_transaction_status` | Check the status of a transaction after validating customer ownership. | Read | No state-changing confirmation |
| `open_dispute` | Create a dispute associated with an eligible customer-owned transaction or account. | State-changing | Required before creation |
| `block_card` | Block a customer-owned card after checking current state and permissions. | State-changing | Required before blocking |
| `check_loan_eligibility` | Return an eligibility assessment and permitted explanation. | Read / assessment | No loan approval or disbursement is implied |
| `get_loan_status` | Retrieve permitted status information for the authenticated customer's loan. | Read | No state-changing confirmation |
| `handoff_to_human` | Create or route a support handoff and return its confirmed status/reference. | Support workflow | Must not claim success unless confirmed by the Banking API |
| `create_confirmation` | Create a pending, action-bound confirmation for a supported sensitive action. | Supporting / internal | Creates a pending confirmation; does not authorize execution |
| `approve_confirmation` | Submit explicit customer approval for a pending action-bound confirmation. | Supporting / internal | Must match the exact action and payload; backend validates approval |

Confirmation tools support the customer-facing action workflow and should not be presented as standalone customer services. A future addition, removal, or rename requires an explicit contract change.

## 4. Common input rules

1. Inputs must conform to each tool's declared schema; reject unknown or malformed arguments.
2. Do not accept a model-supplied `customer_id` as proof of identity or permission.
3. Use trusted backend context to determine the customer scope.
4. Resource identifiers supplied as arguments are lookup references only; verify ownership before returning data or changing state.
5. Apply reasonable bounds to lists, pagination, date ranges, and free-text lengths when those fields are introduced in detailed schemas.
6. Do not request or accept passwords, one-time passcodes, full card credentials, or other authentication secrets as ordinary tool arguments unless a separately approved secure verification design explicitly requires a safe handling mechanism.
7. Do not treat natural-language claims such as “I am verified” or “the customer confirmed” as proof of verification or confirmation.
8. Do not silently coerce invalid values into valid-looking values.

The exact fields for each tool are not locked by this draft and must be specified in the detailed tool schemas.

## 5. Common output rules

Each tool returns a structured result that distinguishes a successful business result from an error or uncertain outcome. The agent must not infer success from an empty response, a timeout, or an unstructured string.

At minimum, results should communicate:
- whether the tool call succeeded at the protocol/application level;
- a stable outcome classification;
- the business data needed for the customer-facing response, limited to the minimum necessary;
- a correlation or operation reference where appropriate;
- whether the outcome is definitive or remains unknown.

Exact envelope and per-tool payload schemas remain to be defined. Internal stack traces, credentials, and unnecessary personal or financial data must never be returned to the model.

## 6. Permissions and enforcement

The agent runtime maintains a bounded set of registered tools and validates tool inputs. The Banking API remains authoritative for authorization and ownership checks.

- Read tools require authenticated customer context and ownership checks.
- `verify_customer` follows the approved verification workflow and reports only the resulting verification state and next safe step.
- `open_dispute` and `block_card` require the confirmation lifecycle defined in the Banking API Contract and confirmation flow.
- `check_loan_eligibility` may return an assessment but cannot approve, originate, or disburse a loan unless a separately reviewed capability is added.
- `handoff_to_human` must create or route a real handoff through its designated component; the agent cannot fabricate a handoff reference.
- Unknown tool names and tools not enabled for the current caller must be rejected.

The Banking API performs its own authorization and ownership checks even if the agent runtime has already checked permissions. This defence-in-depth requirement prevents an agent-layer mistake from becoming unauthorized banking access.

## 7. Confirmation-sensitive tools

### 7.1 `open_dispute`

Before creating a dispute, the system must:
1. validate the request fields and the referenced resource;
2. verify the resource belongs to the authenticated customer and is eligible for dispute;
3. prepare a human-readable summary of the dispute being opened;
4. persist a pending action and return its confirmation reference;
5. execute creation only after valid confirmation;
6. return a dispute reference only after the Banking API confirms creation.

A pending confirmation must not itself create a dispute.

### 7.2 `block_card`

Before blocking a card, the system must:
1. validate the card reference and verify ownership;
2. check the card's current state and whether the requested action is permitted;
3. present a human-readable summary identifying the intended card safely, without exposing full card credentials;
4. persist a pending action and return its confirmation reference;
5. execute blocking only after valid confirmation;
6. report the resulting state only after the Banking API confirms it.

If the card is already blocked, the tool must return a truthful current-state result rather than pretending a new block occurred.

### 7.3 Confirmation enforcement

Confirmation state is durable and authoritative in the backend. The agent runtime and model must not independently mark an action confirmed. The backend checks the pending action's customer/session binding, exact action details, expiry, single-use state, and current authorization before execution.

A declined, ambiguous, expired, mismatched, or consumed confirmation must not execute the action. If an execution outcome is unknown, the caller must reconcile rather than blindly retry.

## 8. Failure and retry behaviour

Tool failures must be represented using stable classifications, not just natural-language messages. The initial classification set is:

- `INVALID_ARGUMENTS`
- `AUTHENTICATION_REQUIRED`
- `PERMISSION_DENIED`
- `RESOURCE_NOT_AVAILABLE`
- `VERIFICATION_REQUIRED`
- `CONFIRMATION_REQUIRED`
- `CONFIRMATION_INVALID`
- `CONFLICT`
- `DEPENDENCY_UNAVAILABLE`
- `OUTCOME_UNKNOWN`
- `INTERNAL_ERROR`

These are proposed classifications; the final error catalogue should be aligned with the Banking API contract before implementation.

Retry rules:
- Invalid arguments, permission denials, and invalid confirmations are not automatically retried.
- Dependency failures may be retried only where safe and according to the operation's idempotency semantics.
- `OUTCOME_UNKNOWN` must trigger status lookup or reconciliation before any repeat of a state-changing action.
- The model must not be given raw stack traces or internal secrets.
- A failure must not be rewritten as a successful result in the customer-facing answer.

## 9. Tool-call audit

For each invocation, record the tool name, timestamp, correlation identifier, outcome classification, and minimized/redacted input and result details. For sensitive or state-changing tools, also record the relevant authorization, verification, confirmation, and operation lifecycle events.

Logs must not include passwords, tokens, one-time passcodes, full card credentials, or unnecessary raw personal/financial data. Audit retention, exact schema, and monitoring requirements are defined in the observability and security artifacts.

## 10. Tool descriptions and model behaviour

Tool descriptions should state:
- what the tool does;
- when it should be used;
- required arguments and constraints;
- whether it reads data, proposes a state change, or performs a support workflow;
- any prerequisite such as verification or confirmation;
- important limitations, such as eligibility not being loan approval.

Descriptions improve tool selection but are not an authorization mechanism. The server must reject unauthorized calls even if the model selects the tool incorrectly or supplies malicious arguments.

## 11. Explicitly out of scope

The following items are not defined by this contract:
- final JSON Schema for every tool;
- agent HTTP client and runtime configuration;
- exact authentication-context propagation;
- exact Banking API endpoint paths;
- final error payload envelope;
- confirmation expiry duration or idempotency-key format;
- detailed loan-model feature explanations;
- external human-support system integration.

These remain open for their designated contracts and implementation planning.

## 12. Review checklist

- [ ] Exactly the approved core and supporting tools are registered; additions and removals require an explicit contract change.
- [ ] Every tool has a declared input schema, output schema, and permission mapping before implementation.
- [ ] Customer identity is sourced from trusted backend context.
- [ ] Resource ownership is checked for every customer-scoped operation.
- [ ] The agent runtime does not access banking tables directly or bypass the Banking API.
- [ ] The Banking API independently enforces authorization and domain rules.
- [ ] State-changing actions use durable, action-specific confirmation.
- [ ] Unknown outcomes are reconciled before retries.
- [ ] Tool-call audit records are useful without exposing unnecessary sensitive data.
- [ ] Tool errors are structured and safe for the agent to interpret.
