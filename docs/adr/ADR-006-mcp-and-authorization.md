# ADR-006: MCP and Authorization

- **Status:** Superseded by ADR-009
- **Decision date:** 2026-10-24
- **Scope:** MCP tool exposure and authorization boundaries

> **Status note (2026-10-31):** This ADR records the original MCP-based design. Its runtime-topology decision is superseded by [ADR-009: Direct Agent Tool Execution](ADR-009-direct-agent-tool-execution.md). The Banking API authorization, ownership, confirmation, and persistence requirements remain in force.

## Context

The Rubies MFB Customer Support Agent exposes a defined set of banking-support capabilities through tools. The capstone also includes an MCP server boundary for exposing approved tools to compatible clients or agent runtimes.

The tool surface includes customer verification, balance and mini-statement retrieval, transaction-status lookup, dispute creation, card blocking, loan eligibility checks, loan-status retrieval, and human handoff. These tools do not all have the same risk: some are read-only, while others can create records or change a customer's card state. Sensitive actions require trusted identity, appropriate permissions, confirmation where specified, and auditable outcomes.

MCP provides a protocol boundary for tool discovery and invocation; it does not by itself establish that a caller is a particular customer or that a requested action is authorized. Fleet integration details are not confirmed and are intentionally outside this decision.

## Decision

Use the dedicated `apps/mcp_server/` boundary to expose only the approved MCP tools and schemas. Keep authorization enforcement in backend-controlled code, including the MCP authorization layer and the banking API/service boundary. The model's choice to call a tool is not authorization.

The MCP server must:

- Publish only explicitly registered tools with validated input and output schemas.
- Authenticate or validate the calling principal using the configured trusted integration mechanism before allowing protected tool execution.
- Apply least-privilege authorization checks for the principal, requested tool, target resource, and operation.
- Pass trusted identity/session context to the backend through a controlled mechanism; never treat a customer identifier supplied only in model-generated tool arguments as proof of identity.
- Preserve confirmation requirements for consequential actions such as opening a dispute or blocking a card.
- Return only the information the caller is authorized to receive.
- Record tool invocation metadata and outcomes using the shared observability/audit conventions, with sensitive values redacted.
- Fail closed when caller identity, authorization, required context, or input validation cannot be established.

The MCP server is an interface and policy-enforcement boundary, not an alternate database. Banking operations must ultimately use the approved banking API/service boundary and PostgreSQL persistence model. Direct model or MCP access to banking tables is prohibited.

## Tool risk classification

| Tool | Intended operation | Baseline risk/control |
|---|---|---|
| `verify_customer` | Establish or update verification state through the approved verification flow | Validate supplied factors safely; do not expose whether sensitive identifiers exist unnecessarily |
| `get_balance` | Read authorized account balance | Require trusted customer context and account-level authorization |
| `get_mini_statement` | Read authorized recent transactions | Require trusted customer context; minimize returned fields and redact sensitive data |
| `get_transaction_status` | Read the status of an authorized transaction | Validate transaction ownership before returning status |
| `open_dispute` | Create a dispute record | Require authorization, validate transaction/reference details, and obtain explicit confirmation before submission |
| `block_card` | Change a card's status to blocked | Require authorization and explicit confirmation; protect against duplicate or ambiguous execution |
| `check_loan_eligibility` | Return a policy-governed eligibility assessment | Validate inputs and distinguish model prediction from policy outcome |
| `get_loan_status` | Read authorized loan status | Require trusted customer context and resource-level authorization |
| `handoff_to_human` | Create or route a support handoff | Limit customer data in the handoff payload and record the handoff outcome |

This table defines baseline control expectations, not a complete production threat model. Exact authentication mechanisms, permissions, schemas, and operational controls must be specified and tested during implementation.

## Authorization model

Authorization is enforced at the backend boundary and follows these principles:

1. **Trusted principal:** Determine the caller from authenticated server-side context, not from model-generated claims.
2. **Customer binding:** Resolve the customer associated with the trusted session. A tool argument containing a customer ID cannot override this binding.
3. **Least privilege:** Grant each caller only the tools and operations required for its role and context.
4. **Resource ownership:** Check that the requested account, transaction, card, dispute, or loan belongs to the customer or is otherwise explicitly accessible to the authenticated principal.
5. **Action-specific controls:** Apply confirmation and idempotency rules to state-changing operations.
6. **Defense in depth:** The MCP layer checks access, and the banking API/service boundary validates authorization and business rules again where applicable.
7. **Fail closed:** Missing or invalid identity, permission, confirmation, or resource ownership results in denial rather than a best-effort operation.
8. **Safe errors:** Do not leak secrets, internal stack traces, or unnecessary information about other customers through error messages.

## Confirmation and execution

MCP invocation must not bypass the approved confirmation lifecycle defined in ADR-008 and the confirmation/execution flow.

For consequential actions:

- The tool validates the intended action and creates or references a pending confirmation through the approved backend workflow.
- The customer receives a clear description of the exact action and relevant details.
- Execution proceeds only after explicit approval bound to the intended action and trusted context.
- The backend validates expiry, single-use status, action binding, and authorization before executing.
- Repeated calls or ambiguous timeouts must be handled with idempotency and outcome reconciliation; they must not silently duplicate an operation.
- The result and confirmation lifecycle are recorded in the appropriate audit trail.

The MCP protocol itself is not treated as evidence of customer consent.

## Tool contracts and error behavior

Each exposed tool must have a stable, documented schema, including required inputs, validated types, expected output fields, and known error conditions. Schemas should avoid accepting redundant identity fields when identity is available from trusted context.

Tool results should distinguish successful completion, a known business rejection, a validation/authorization denial, and an indeterminate execution outcome. The agent must not translate an error or timeout into an unsupported claim that an operation succeeded or failed.

Unknown tools, malformed inputs, unsupported operations, and unauthorized requests must be rejected. The server must not dynamically expose arbitrary functions or allow model-generated code to execute.

## Audit and observability

For each tool invocation, record, where applicable:

- Tool name and schema/version identifier.
- Correlation/request identifier.
- Trusted principal or appropriately pseudonymized session reference.
- Redacted input metadata.
- Authorization and confirmation decision.
- Result category and execution outcome.
- Timing and relevant error category.

Do not log authentication secrets, full verification factors, or unnecessary customer financial details. Audit records must be protected against unauthorized access or modification. Detailed logging configuration and metrics are addressed by ADR-007.

## Alternatives considered

### Let the model decide whether a tool call is permitted

**Rejected.** Model instructions are not an enforceable security boundary and can be bypassed by prompt injection, malformed requests, or orchestration errors.

### Trust the MCP connection as customer authentication

**Rejected.** A protocol connection identifies a technical caller only to the extent established by its configured authentication. It does not automatically prove which banking customer is represented or authorize access to that customer's resources.

### Let MCP access PostgreSQL directly

**Rejected.** This would bypass the banking API's domain validation and authorization boundary and couple the external tool interface to the physical database schema.

### Expose every backend operation through MCP

**Rejected.** Only explicitly approved, documented, least-privilege tools should be exposed. Internal or administrative operations must not become available merely because an endpoint or function exists.

## Consequences

### Positive

- Tool discovery and invocation have a defined boundary.
- Authorization is enforced independently of model behavior.
- Read-only and state-changing tools have explicit control expectations.
- The MCP interface remains decoupled from database tables and unconfirmed Fleet details.
- Tool invocations can be tested and audited consistently.

### Trade-offs and constraints

- The project must define and maintain tool schemas, caller authentication, permissions, and error contracts.
- Authorization needs integration tests at both MCP and banking API boundaries.
- Confirmation, idempotency, and audit requirements add workflow complexity but are necessary for consequential actions.
- Any future client integration must be assessed against the same identity and permission model.

## Intentionally deferred

This ADR does not decide the exact MCP SDK/version, transport, deployment topology, production authentication provider, Fleet integration, or final permission matrix. These details require implementation context and, for Fleet, confirmed integration requirements. They must not weaken the authorization principles established here.

## Acceptance criteria

This decision is considered implemented when:

- Only explicitly registered and schema-validated tools are exposed.
- Unauthenticated or unauthorized callers cannot execute protected tools.
- Customer/resource ownership is checked by trusted backend code.
- Model-supplied customer IDs cannot override trusted session identity.
- Consequential actions cannot bypass explicit, action-bound confirmation.
- Duplicate and indeterminate executions are handled safely.
- Tool calls are auditable with sensitive information redacted.
- Security tests cover unauthorized access, cross-customer access, malformed arguments, confirmation bypass, and unknown tools.
