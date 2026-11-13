# Rubies MFB — Disputes, Complaints, and Escalation Policy

**Document ID:** RB-POL-DCE-001  
**Version:** 0.1  
**Status:Final
**Policy owner:** Customer Experience and Banking Operations  
**Applies to:** Synthetic Rubies MFB capstone environment only  
**Effective date:** 1 October 2026 (demo policy date; not a real bank policy)  
**Review trigger:** Changes to dispute categories, complaint workflows, escalation ownership, or applicable verified requirements

> **Important scope notice:** Rubies MFB is fictional. Categories, internal targets, workflow rules, and example timelines in this document are synthetic capstone design choices. They are not actual service commitments or regulatory timelines for any Nigerian financial institution. Do not present them as CBN requirements. Verified applicable law or regulation takes precedence and requires review of this policy.

## 1. Purpose

This policy defines how the Rubies MFB Customer Support Agent identifies a complaint, prepares and opens a dispute, routes cases for human review, communicates status, and determines when a case may be closed.

It complements `transfer-failure-reversal-policy.md`: that document governs transfer-state and reversal handling; this document governs dispute intake, complaint ownership, escalation, customer updates, and closure. It does not authorize the agent to reverse transactions, approve refunds, waive fees, or make other banking-ledger changes.

## 2. Definitions

- **Question or service request:** A request for information or routine assistance that does not allege a service failure or request formal review.
- **Complaint:** An expression of dissatisfaction about a product, service, process, employee interaction, or unresolved issue.
- **Dispute:** A case requiring review of a specific transaction, debit, transfer, card event, or account-related record.
- **Case reference:** A unique identifier returned by the case/dispute system after successful creation.
- **Escalation:** Routing a case to an authorized human team or specialist because of risk, complexity, customer request, or inability to resolve safely.
- **Acknowledgement:** Confirmation that a complaint or dispute has been received. It is not a finding, refund approval, or resolution.
- **Resolution:** A recorded outcome supported by the authorized case system and any required operational evidence.

## 3. Case categories

Use the narrowest category supported by the customer's account and the available evidence. Do not infer wrongdoing or assign a final cause based only on the customer's description.

| Category | Typical trigger | Initial handling |
|---|---|---|
| `TRANSFER_FAILED_DEBITED` | Transfer appears unsuccessful but an account debit is present. | Follow transfer-status checks and dispute confirmation workflow. |
| `TRANSFER_DELAYED_OR_UNKNOWN` | Transfer remains pending or its outcome cannot be established. | Check status; do not call it failed or completed without evidence. Escalate if unresolved. |
| `DUPLICATE_DEBIT` | Customer reports multiple debits for one intended payment or transfer. | Compare authorized records and references; do not assume the report is proven. |
| `BENEFICIARY_NOT_CREDITED` | Transfer is recorded as completed but beneficiary reports non-receipt. | Record both the system status and customer's report; route for review. |
| `CARD_LOST_OR_STOLEN` | Customer says their card is missing or stolen. | Prioritize safe card-blocking workflow; explicit confirmation is required before blocking. Escalate suspected unauthorized activity. |
| `UNRECOGNIZED_TRANSACTION` | Customer does not recognize a transaction. | Treat as potentially sensitive; verify customer, avoid unsupported conclusions, and route to authorized review. |
| `FEE_OR_CHARGE_QUERY` | Customer questions a fee or charge. | Check the approved fee schedule and actual transaction record; open a dispute if the customer contests a posted charge. |
| `ACCOUNT_ACCESS_OR_KYC` | Customer reports an access restriction or questions a verification/tier requirement. | Check the applicable account-access policy; do not bypass restrictions. |
| `LOAN_QUERY_OR_COMPLAINT` | Customer questions loan eligibility, status, terms, or handling. | Use approved loan records/policy; escalate disputed or unsupported decisions. |
| `SERVICE_OR_STAFF_COMPLAINT` | Customer complains about service quality, process, or staff conduct. | Acknowledge neutrally and route to Customer Experience or the designated team. |
| `OTHER_OR_UNCLEAR` | The issue does not fit a supported category or facts are insufficient. | Ask a focused clarification if useful; otherwise hand off rather than inventing a category or cause. |

## 4. Intake and triage

For every complaint or potential dispute:

1. **Listen and acknowledge.** Use calm, neutral language. Do not blame the customer or another party.
2. **Classify provisionally.** Select a category based on the reported issue, not an assumed root cause.
3. **Verify access.** Apply `customer-verification-account-access-policy.md`. Resolve customer identity from trusted session context; never trust a model-supplied customer ID.
4. **Collect only necessary details.** Prefer transaction reference, approximate date/time, amount, channel, and a concise description. Do not ask for passwords, PINs, OTPs, or full card credentials.
5. **Retrieve available records.** Use authorized tools and distinguish customer statements from system-of-record facts.
6. **Determine the next action.** Give information, perform an allowed lookup, prepare a dispute, or hand off. Any record-changing action requires the applicable explicit confirmation.
7. **Explain the next step.** State what has been checked, what remains unknown, and what will happen next without inventing an SLA.
8. **Record the interaction.** Log required audit events and preserve the minimum useful case context.

If the customer is upset, asks for a human, or the situation cannot be handled safely, prioritize handoff over repeated questioning.

## 5. Opening a dispute

Opening a dispute creates a persistent record and is therefore a record-changing action. It requires explicit customer confirmation.

### 5.1 Prepare the dispute

The backend should validate the requested category and available evidence before a pending action is presented for approval. The agent should summarize, when available:

- The transaction reference or safely masked identifier.
- The amount and date/time.
- The recorded transaction status.
- The proposed dispute category.
- The customer's reported issue in neutral wording.
- A statement that a dispute record will be created for review.

Do not represent the customer's allegation as an established fact. For example, use “customer reports a possible duplicate debit,” not “bank duplicated the debit,” unless the records have confirmed it.

### 5.2 Confirmation and execution

1. Persist the proposed action as a pending confirmation bound to the verified customer/session and exact payload.
2. Return a confirmation identifier, expiry, and readable summary.
3. Wait for an explicit affirmative response to that exact action.
4. Validate that the confirmation is unexpired, single-use, belongs to the same verified customer/session, and has not been altered.
5. Consume the approval and execute the dispute creation through the authorized banking API.
6. Use idempotency or equivalent duplicate-prevention controls.
7. Return a case reference only when the system confirms successful creation.
8. If the result is uncertain after a timeout, reconcile using the request/idempotency reference before retrying. Do not create a second dispute blindly.
9. If the customer declines, the confirmation expires, or the payload changes, do not execute. Obtain fresh confirmation if the customer still wants to proceed.

The model may propose a category and draft a summary; it must not authorize the action or bypass backend controls.

## 6. Complaint acknowledgement and customer updates

After successful case creation, acknowledge receipt and provide the returned case reference. Make clear that acknowledgement is not the same as resolution.

The agent may communicate only information supported by the case system or approved policy:

- Case reference and recorded status.
- Issue category and a neutral summary of the reported concern.
- Whether the case is awaiting review, additional information, or a recorded decision.
- The next action that is actually assigned or authorized.
- Any deadline explicitly present in an approved policy or the case record.

Do not invent a case reference, claim a case was created before the API confirms it, guarantee a refund, or promise a resolution date not supported by the system.

If the case system has no customer-update field or approved notification mechanism, the agent must not imply that an update has been sent. It can state what the next step is and offer a human handoff.

## 7. Escalation routes

The following routes are logical ownership groups for the synthetic demo. They do not imply real departments or external regulatory reporting arrangements.

| Route | Examples | Required handling |
|---|---|---|
| `PAYMENTS_OPERATIONS` | Failed transfer with debit, pending/unknown outcome, beneficiary non-receipt, possible duplicate debit. | Include transaction reference, amount, timestamp, recorded status, checks performed, and unresolved discrepancy. |
| `CARD_SUPPORT` | Lost/stolen card, card access issue, card transaction concern. | If a card is lost or stolen, offer the authorized card-blocking action promptly; blocking still requires explicit confirmation. Route suspected unauthorized use for specialist review. |
| `FRAUD_AND_SECURITY` | Unrecognized transaction, suspected account compromise, social engineering, suspicious access. | Avoid exposing detection logic or another person's data. Follow approved containment and human-review procedures; do not investigate beyond authorized tools. |
| `CUSTOMER_EXPERIENCE` | Service dissatisfaction, staff conduct complaint, repeated unresolved support issue. | Record the customer's concern neutrally and route for review. Do not argue or promise a specific outcome. |
| `ACCOUNT_SERVICES` | KYC/tier restriction, account access, profile discrepancy. | Follow the account-access policy; do not bypass a restriction or change records without authorization and confirmation. |
| `LENDING_OPERATIONS` | Loan status discrepancy, loan servicing complaint, contested eligibility result. | Provide only supported loan status/model explanation and route disputed decisions or missing evidence. |
| `GENERAL_HUMAN_SUPPORT` | Unclear issue, unavailable tool, conflicting records, customer-requested human. | Supply a concise summary and preserve unresolved questions. |

If a routing destination is not configured or handoff creation fails, the agent must say that it could not complete the handoff, log the failure, and provide the approved next step. It must not pretend a human has been notified.

## 8. Priority and urgent handling

Use the following synthetic triage levels. These are internal routing priorities, not response-time promises.

- **P1 — Potential active security risk:** suspected account compromise, unauthorized transaction, lost/stolen card with risk of use, or a similarly urgent security concern. Prioritize the approved containment workflow and specialist handoff.
- **P2 — Financial discrepancy:** failed transfer with debit, duplicate debit, unrecognized transaction, or beneficiary non-receipt. Perform authorized lookups and route to the relevant operations team.
- **P3 — Service complaint or unresolved routine issue:** service dissatisfaction, repeated friction, or an issue needing human judgment without a clear immediate security risk.
- **P4 — Information request:** ordinary question that can be answered from approved policy without creating a case.

Priority must reflect available facts and the approved triage rules. The agent must not downgrade a suspected security issue merely because a customer cannot provide every requested detail. Where the facts are ambiguous, preserve uncertainty and route for review.

## 9. Case status and closure

Use case status values returned by the case system. If the synthetic implementation uses different labels, map them explicitly and document the mapping; do not fabricate a status.

Suggested conceptual states:

- `OPEN` — case created and awaiting review.
- `IN_REVIEW` — an authorized team is reviewing the case.
- `AWAITING_CUSTOMER` — an authorized reviewer needs further information from the customer.
- `RESOLVED` — an authorized outcome is recorded.
- `CLOSED` — closure has been recorded according to the approved workflow.

The agent must not mark a case resolved or closed merely because it has answered a question, opened a dispute, or handed off the conversation. Only an authorized workflow or case-system response may establish resolution/closure.

When the customer asks for an update, retrieve the current case status if the tool supports it. If no status lookup is available, say the agent cannot currently verify the case's latest status and offer a human handoff.

## 10. Handoff summary and data minimization

A handoff summary should include only information necessary for the receiving team:

- Verified customer/session reference, not credentials.
- Case reference if one exists.
- Relevant transaction reference, masked where appropriate.
- Amount and date/time, if relevant.
- Recorded status and source of that status.
- Customer's stated concern, neutrally summarized.
- Checks and tool calls already completed.
- Confirmation state and dispute-creation result.
- Unresolved question, risk signal, and requested next step.

Never include passwords, PINs, OTPs, bearer tokens, full card numbers, or unrelated sensitive details. Redact secrets from logs and summaries.

## 11. Audit and accountability

Log each tool invocation with tool name, permitted inputs, result/status, timestamp, correlation ID, and outcome. Apply data minimization and secret redaction.

For case workflows, also record:

- Provisional category and any category changes.
- Confirmation created, accepted, declined, expired, or invalidated.
- Authorization decision and verified customer/session reference.
- Case-creation request and idempotency/reference key.
- API result and returned case reference.
- Handoff attempt, destination, result, and failure reason if any.
- Status lookup and source of any customer update.
- Closure or resolution result as returned by the authorized system.

Access to case records and audit events must be restricted to authorized roles and tested for cross-customer isolation.

## 12. RAG response requirements

When answering complaint or dispute questions, the agent must:

1. Retrieve the applicable policy and cite the exact section.
2. Retrieve case or transaction records before stating case-specific status or outcome.
3. Distinguish the customer's report from verified record facts.
4. Never invent a case reference, assigned team, notification, resolution, refund, or deadline.
5. Require explicit confirmation before creating a dispute or performing any other record-changing action.
6. Use handoff when requested or when evidence, tools, or policy are insufficient.
7. Avoid exposing internal security details or another customer's data.
8. Abstain from claims that depend on a policy or system capability that is not available.

## 13. Acceptance tests

| ID | Scenario | Expected behavior |
|---|---|---|
| DCE-01 | Customer reports a debit after a failed transfer | Agent checks transaction records and follows the transfer/dispute workflow. |
| DCE-02 | Customer reports a duplicate debit without a reference | Agent asks only for necessary clarifying details or uses authorized records; does not assume the claim is proven. |
| DCE-03 | Customer asks to open a dispute | Agent presents the exact proposed action and waits for explicit confirmation. |
| DCE-04 | Customer declines the pending dispute | No dispute is created. |
| DCE-05 | Confirmation is expired or belongs to another session | Backend rejects execution. |
| DCE-06 | Dispute creation times out | Agent reconciles by request/idempotency reference before retrying. |
| DCE-07 | Case API confirms creation | Agent returns the actual case reference and acknowledges receipt. |
| DCE-08 | Case API fails | Agent does not claim a case was created and explains the failure/next step. |
| DCE-09 | Customer asks for a resolution date but none is recorded in policy or case | Agent does not invent a deadline. |
| DCE-10 | Customer requests a human | Agent initiates the configured handoff and reports success only if confirmed. |
| DCE-11 | Handoff tool fails | Agent logs the failure and does not claim a human was notified. |
| DCE-12 | Customer reports suspected unauthorized card use | Agent prioritizes the approved security/card workflow and specialist review. |
| DCE-13 | Customer asks for another person's case status | Access is denied and no other-customer information is disclosed. |
| DCE-14 | Case is `OPEN` | Agent does not describe it as resolved. |
| DCE-15 | Customer complains angrily | Agent remains calm, acknowledges the concern, and offers/initiates handoff when appropriate. |
| DCE-16 | RAG retrieves an outdated or conflicting policy | Agent uses the approved active version or abstains and escalates. |

## 14. Related documents

- `docs/banking_policies/customer-verification-account-access-policy.md` — identity and access rules.
- `docs/banking_policies/account-tiers-kyc-policy.md` — synthetic tiers and KYC restrictions.
- `docs/banking_policies/fee-schedule.md` — synthetic fee rules.
- `docs/banking_policies/transfer-failure-reversal-policy.md` — transfer status, failure, and reversal handling.
- `docs/flows/confirmation-and-execution-flow.mmd` — confirmation lifecycle.
- `docs/flows/dispute-and-confirmation-flow.mmd` — dispute creation workflow.
- `docs/flows/human-handoff-flow.mmd` — human handoff.
- `docs/api/banking-api-contract.md` — banking API boundary and contract.

---

**End of document — RB-POL-DCE-001, version 0.1**
