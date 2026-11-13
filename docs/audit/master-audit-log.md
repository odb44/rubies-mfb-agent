# Rubies MFB Agent — Master Audit Log

**Purpose:** Single source of truth for audit findings, remediation, and verification.

## Working rules

1. Preserve existing architecture, evaluation, security, and observability documents.
2. Do not repeat an investigation unless new evidence requires it.
3. Every finding must have an ID, evidence, status, owner/action, and verification result.
4. Distinguish confirmed defects from suspected defects and unverified behaviour.
5. A fix is not complete until its relevant tests pass and the result is recorded.
6. Do not modify production code merely to make an audit finding disappear.
7. Do not claim live end-to-end verification based only on mocked tests.

## Status definitions

- **CONFIRMED:** Reproduced or directly established by evidence.
- **NEEDS REPRODUCTION:** Previously reported; current behaviour or cause has not been independently reproduced.
- **UNDER INVESTIGATION:** Investigation is active.
- **FIXED — VERIFY:** A change has been made but verification is incomplete.
- **VERIFIED:** The fix has passed the relevant tests and required checks.
- **BLOCKED:** Cannot proceed because a specific dependency or piece of evidence is missing.

## Verified test baseline

The following targeted banking API test suites passed together:

- `test_confirmations_api.py`
- `test_card_authentication.py`
- `test_card_integration.py`
- `test_dispute_api.py`
- `test_dispute_workflow.py`

**Recorded result: 28 passed in 1.60 seconds.**

This is a targeted test baseline, not evidence that the entire repository or live end-to-end application passes.

## Master findings register

| ID | Area | Finding | Evidence / limitation | Status | Next action |
|---|---|---|---|---|---|
| AUD-001 | Confirmations | Live approval request previously returned HTTP 409; exact cause remains unresolved. | API route and confirmation service have been inspected. Four confirmation API tests pass, but mocked tests do not establish the cause of the live response. | NEEDS REPRODUCTION | Trace the agent tool executor request, authentication headers, payload, and response handling; reproduce the request and capture the actual response detail. |
| AUD-002 | Banking API | Mini-statement retrieval previously returned HTTP 500. | Earlier live observation; precise failure cause is not established in the current evidence. | NEEDS REPRODUCTION | Reproduce once, capture the server traceback and request path, then identify the failing component. |
| AUD-003 | Banking API | Balance lookup returned HTTP 200, but complete agent-to-banking-tool behaviour was not demonstrated. | HTTP success alone does not establish correct tool execution or response interpretation. | NEEDS REPRODUCTION | Verify the complete request, tool result, and customer-facing response. |
| AUD-004 | MCP | MCP service startup and live tool invocation were not fully verified. | Earlier startup was blocked by missing `JWT_SECRET_KEY`, `JWT_ISSUER`, and `JWT_AUDIENCE`; the recorded port check found no listener on port 8002 at that time. Current state is unknown. | NEEDS REPRODUCTION | Check current configuration, startup, health/discovery, authentication, and one real tool invocation. |
| AUD-005 | Observability | Cross-service correlation and tool-call/result coverage have not been established end to end. | Existing observability architecture documentation is present, but documentation is not runtime proof. | NEEDS REPRODUCTION | Trace one request across frontend, agent, MCP, and banking API; record correlation IDs and corresponding events. |
| AUD-006 | Evaluation | The evaluation report previously contained 37 blocked cases. | Existing evaluation specifications, harness, and report files are present. Current report state and causes of blocked cases have not yet been reconciled here. | NEEDS REPRODUCTION | Inspect the existing report and classify blocked cases by root cause before changing the harness or rerunning evaluation. |
| AUD-007 | Frontend | Earlier manual checks raised concerns about raw tool output, confirmation interaction, retries, success messaging, and handoff claims. | These observations require targeted reproduction before each is treated as a confirmed defect. | NEEDS REPRODUCTION | Reproduce each behaviour and record the scenario, expected result, actual result, and evidence. |
| AUD-008 | Security | Cross-service authentication and customer/session isolation have not been proven end to end. | Earlier review identified gaps in live verification; this does not establish that every boundary is defective. | NEEDS REPRODUCTION | Test authorization propagation and customer/session isolation across service boundaries. |
| AUD-009 | Database / migrations | An empty migration revision was previously identified, and loan-related schema/data consistency needs verification. | Earlier migration review; current database state and migration history must be checked before any change. | NEEDS REPRODUCTION | Inspect migration history and affected schema/data constraints before proposing a migration. |
| AUD-010 | Tool contracts | Confirmation tools explicitly validate supported actions and the BLOCK_CARD card reference; other downstream payload contracts need verification. | Current agent-side confirmation tool implementation was inspected. A downstream validation gap has not been established. | UNDER INVESTIGATION | Trace the executor and banking API contract, then add tests only for demonstrated gaps. |

## Remediation log

| Date | Finding ID | Change | Tests / evidence | Outcome |
|---|---|---|---|---|
| 2026-10-31 | AUD-001 | Added confirmation API tests; no production implementation change recorded. | Four confirmation API tests passed; combined targeted banking API suite passed 28 tests. | Test coverage improved; original live HTTP 409 remains unresolved. |

## Next action

Start with AUD-001 because the confirmation approval failure is already a known unresolved issue. Trace the existing executor and reproduce the request before editing production code.

Update this register after every meaningful finding, fix, or verification. Do not duplicate findings in separate informal lists.
