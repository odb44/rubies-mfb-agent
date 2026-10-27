# Threat Model and Security Controls

- **Status:** Design draft
- **Scope:** Threats and controls for the Rubies MFB Customer Support Agent
- **Related design:** `docs/security/security-model.md`
- **Related decisions:** ADR-006 (MCP and Authorization); ADR-008 (Agent Execution and Confirmation Lifecycle)
- **Implementation status:** Requirements only; implementation and test results must be recorded separately

## 1. Purpose

This document identifies the principal security threats implied by the approved architecture and Security Model. It maps each threat to prevention and detection controls and to tests that should demonstrate the controls work.

The threat list is scoped to the initial capstone system and its nine approved tools. It is not a claim that every possible threat has been identified.

## 2. Assets to protect

| Asset | Security objective |
|---|---|
| Customer identity and session binding | Prevent impersonation and customer-context substitution |
| Customer, account, transaction, card, dispute, and loan records | Prevent unauthorized access, disclosure, or modification |
| Verification state and factors | Prevent bypass or disclosure of verification controls |
| Pending confirmations | Prevent forgery, replay, cross-session use, and action substitution |
| Banking API and MCP tool boundary | Prevent unauthorized or unregistered operations |
| Synthetic customer dataset and knowledge documents | Preserve integrity and prevent untrusted content from becoming executable authority |
| Audit events and tool-call logs | Preserve useful traceability without exposing secrets or unnecessary personal data |
| Loan-model artifacts and outputs | Prevent unauthorized artifact changes and unsupported claims about eligibility |
| Human handoff payloads and results | Prevent unnecessary disclosure and false claims of successful escalation |
| Configuration and secrets | Prevent unauthorized access to credentials and security-sensitive settings |

## 3. Trust boundaries

1. **Customer ↔ Agent API:** Incoming messages and user-provided identifiers are untrusted input.
2. **Agent orchestration ↔ tool router:** Model-proposed tool calls are requests, not authorization decisions.
3. **Agent/tool router ↔ MCP server:** Tool access must be authenticated and authorized according to the configured integration design.
4. **MCP server ↔ Banking API:** The Banking API/service must independently validate identity context, ownership, permissions, business rules, and action requirements.
5. **Banking API ↔ PostgreSQL:** Database access is restricted to trusted service code and approved migrations; the model and MCP tools do not access banking tables directly.
6. **Agent ↔ knowledge base/model artifacts:** Retrieved documents and model artifacts are data inputs and must be integrity-controlled; retrieved text cannot override system policy.
7. **Agent ↔ session and confirmation storage:** Session files and pending-action records require access controls and must not be treated as interchangeable stores.
8. **Agent ↔ human-support destination:** Handoff data must be minimized, and delivery outcomes must be represented honestly.

## 4. Threat register

| ID | Threat / abuse case | Potential impact | Required controls | Verification tests |
|---|---|---|---|---|
| TM-01 | Cross-customer access: caller supplies another customer's ID or resource reference | Disclosure of another customer's financial or personal data | Derive customer binding from trusted context; enforce resource ownership in Banking API; return safe denial | Attempt balance, statement, transaction, card, dispute, and loan lookups against a second synthetic customer; assert no data is returned |
| TM-02 | Model-generated arguments attempt to override trusted identity | Agent acts under an attacker-selected customer context | Never treat model-supplied identity fields as authoritative; validate or reject unexpected identity fields at tool boundary | Inject a different customer ID into proposed tool arguments; assert trusted session binding wins or call is rejected |
| TM-03 | Prompt injection in customer messages or retrieved documents | Policy bypass, unauthorized tool use, data leakage | Treat user/retrieved text as untrusted data; keep authorization in backend; use explicit tool schemas and allowlist | Include instructions to ignore policy or reveal another customer's data in user text and indexed documents; assert denial and no unauthorized tool call |
| TM-04 | Unregistered or malformed tool invocation | Unauthorized behavior, validation bypass, service instability | Allowlist the nine tools; validate strict input schemas; reject unknown operations before execution | Invoke unknown tool names, missing fields, invalid types, oversized values, and unexpected identity/permission fields |
| TM-05 | MCP boundary bypass or direct database access | Circumvention of service rules and audit controls | MCP exposes registered tools only; no direct database access; Banking API re-enforces ownership and business rules | Verify MCP tool implementations call approved service/API paths; test direct requests without valid authorization and attempt forbidden DB access in integration setup |
| TM-06 | Confirmation forgery or reference guessing | Unauthorized state change | Generate unguessable references; bind pending action to trusted customer/session and exact action details; validate on approval | Submit nonexistent, altered, and another customer's confirmation references; assert no operation occurs |
| TM-07 | Confirmation replay or concurrent duplicate approval | Duplicate dispute/card operation or repeated side effect | Expiry, atomic single-use consumption, stable idempotency key, persisted lifecycle state | Reuse a consumed confirmation and send concurrent approval requests; assert at most one logical operation |
| TM-08 | Action substitution after approval request | Customer approves one action but a different action executes | Store canonical action details server-side; compare approved action with pending record; material changes require new confirmation | Alter target or material fields after preparation; assert the original confirmation cannot authorize the changed action |
| TM-09 | Stale verification or permission state | Sensitive action executes after security state has changed | Recheck current verification, permissions, ownership, and expiry when resolving confirmation | Revoke permission or expire verification between preparation and approval; assert execution is denied |
| TM-10 | Timeout or lost response after a state-changing request | Duplicate execution or false success/failure report | Persist operation reference; use idempotency; represent unknown outcome; reconcile with source of truth before retry | Simulate timeout after request acceptance; assert reconciliation occurs and no blind duplicate request is sent |
| TM-11 | Sensitive values appear in logs, prompts, or tool outputs | Credential compromise or unnecessary exposure of personal/financial data | Minimize fields; redact secrets; restrict log access; use typed tool outputs | Seed synthetic requests with marker secrets and assert they do not appear in logs, prompts, or handoff payloads where prohibited |
| TM-12 | Session-file or pending-confirmation storage is accessed or altered outside authorized service paths | Session compromise, forged state, or disclosure | Restrict filesystem/database access; separate session state from banking source of truth; validate confirmation records server-side | Attempt access under an unauthorized OS/service identity; alter or remove pending-action records and assert safe rejection/reconciliation |
| TM-13 | False or failed human handoff is reported as successful | Customer believes a complaint is being handled when it is not | Record handoff result; distinguish confirmed receipt from failed/unknown delivery; provide recovery path | Simulate rejection, timeout, and unknown result from handoff destination; assert response does not claim successful escalation without evidence |
| TM-14 | Untrusted or corrupted knowledge document changes policy behavior | Incorrect advice or prompt injection through retrieval | Version and validate documents; retain source metadata; cite supporting sections; retrieved content cannot grant permissions or override policy | Index a document containing malicious instructions or conflicting unsupported claims; assert it is treated as content and citations reflect retrieved sources |
| TM-15 | Unauthorized modification or rollback of loan-model artifacts | Incorrect or manipulated eligibility outputs | Version artifacts; restrict write access; record manifest/version; validate model identity at load time | Attempt to load an unapproved or manifest-mismatched artifact; assert rejection or controlled fallback |
| TM-16 | Audit event is missing, altered, or overexposes data | Inability to investigate actions or privacy leakage | Structured audit events, access control, redaction, and defined behavior when audit persistence fails | Simulate audit-store failure and unauthorized reads; assert configured fail-safe behavior and no secret leakage |
| TM-17 | Denial response reveals whether another customer's record exists | Customer enumeration or information leakage | Use safe, non-revealing denial responses for unauthorized cross-customer requests | Compare responses for nonexistent and unauthorized resource references; assert no sensitive existence details are disclosed |
| TM-18 | Repeated invalid verification or abusive requests | Account enumeration, service abuse, or resource exhaustion | Define rate limits, retry ceilings, monitoring, and safe lockout/recovery policy in implementation | Run controlled repeated-failure tests; assert configured limits and logging are applied without revealing verification details |

## 5. Risk treatment priorities

Prioritize controls by the consequences of failure:

- **Priority 0 — Prevent unauthorized banking access or action:** TM-01, TM-02, TM-06, TM-07, TM-08, TM-09, and TM-10.
- **Priority 1 — Prevent boundary and instruction bypass:** TM-03, TM-04, TM-05, and TM-14.
- **Priority 1 — Protect sensitive information and auditability:** TM-11, TM-12, and TM-16.
- **Priority 2 — Ensure reliable support and model artifact integrity:** TM-13 and TM-15.
- **Priority 2 — Limit enumeration and repeated abuse:** TM-17 and TM-18.

These are design-priority groupings, not measured risk scores. A formal likelihood/impact rating should be added after the deployment and threat assumptions are agreed.

## 6. Security control ownership

| Control area | Primary enforcement point | Supporting enforcement / evidence |
|---|---|---|
| Trusted identity and session binding | Agent API/security layer | Banking API validates trusted context |
| Resource ownership and banking permissions | Banking API/service layer | MCP authorization and security audit |
| Tool allowlist and input schema | Tool registry/router and MCP server | Contract tests |
| Verification and step-up requirements | Security/backend services | Confirmation resolution rechecks current state |
| Confirmation lifecycle and idempotency | Banking backend confirmation/execution services | Persistent records, audit events, concurrency tests |
| Sensitive-data minimization | Tool response schemas, response builder, logging/handoff adapters | Redaction tests and access controls |
| Knowledge document integrity and citations | Knowledge ingestion/retrieval pipeline | Version manifests and RAG evaluation |
| Loan-model artifact integrity | Model loader/inference service | Version manifests and evaluation records |
| Handoff outcome accuracy | Handoff integration/service | Receipt/error state and integration tests |
| Auditability | Banking/API and tool execution layers | Protected audit store and observability tests |

## 7. Minimum acceptance criteria

The security design should not be considered implemented until tests demonstrate that:

1. No tested path can use model-supplied identity to access a different customer's records.
2. Every customer-scoped banking operation enforces resource ownership and authorization server-side.
3. The MCP boundary exposes only registered tools and cannot access banking tables directly.
4. Confirmation-required actions cannot execute before approval and cannot be replayed or altered after approval.
5. Indeterminate state-changing outcomes are reconciled without blind retries or unsupported claims.
6. Prompt injection cannot grant permissions, change customer binding, or bypass confirmation.
7. Sensitive secrets are absent from prohibited logging, prompting, and handoff paths.
8. Handoff and audit failures are represented according to explicit, tested policies.
9. Security tests run against synthetic fixtures and record reproducible results.

## 8. Open decisions and assumptions

This threat model identifies controls but does not decide the following:

- Authentication mechanism and trusted context propagation.
- Final tool-by-tool role/permission matrix.
- Verification factors, retry limits, lockout rules, and rate-limit values.
- Confirmation expiry and idempotency-key implementation.
- Filesystem and database deployment identities, encryption, secret management, and backup protections.
- Audit retention and the exact fail-safe behavior if audit persistence fails.
- Human-support destination and its delivery guarantees.
- Deployment-specific likelihood/impact scoring.

Resolve these in the relevant API/security/observability documents. Do not weaken the mandatory controls merely because an implementation detail remains open.

## 9. Related artifacts

- `docs/security/security-model.md`
- `docs/adr/ADR-006-mcp-and-authorization.md`
- `docs/adr/ADR-008-agent-execution-and-confirmation-lifecycle.md`
- `docs/api/agent-interface.md`
- `docs/api/banking-api-contract.md`
- `docs/api/mcp-tool-contracts.md`
- `docs/flows/customer-verification-flow.mmd`
- `docs/flows/confirmation-and-execution-flow.mmd`
- `docs/flows/banking-tool-execution-flow.mmd`
- `docs/flows/human-handoff-flow.mmd`
