# Rubies MFB — Transfer Failure and Reversal Policy

**Document ID:** RB-POL-TRF-001  
**Version:** 0.1  
**Status:Final
**Policy owner:** Banking Operations  
**Applies to:** Synthetic Rubies MFB capstone environment only  
**Effective date:** 1 October 2026 (demo policy date; not a real bank policy)  
**Review trigger:** Changes to transfer-status handling, reversal workflows, customer communication, or applicable verified requirements

> **Important scope notice:** Rubies MFB is fictional. Status definitions, response targets, escalation rules, and timelines in this document are synthetic demo rules. They are not representations of actual Nigerian bank or payment-network timelines and must not be presented as CBN requirements. A verified applicable legal or regulatory requirement takes precedence and requires this document to be reviewed.

## 1. Purpose

This policy defines how the Rubies MFB Customer Support Agent handles outbound transfer questions when a transaction is pending, failed, rejected, completed, reversed, or has an uncertain outcome. It supports consistent customer communication, safe tool use, dispute handling, and retrieval-augmented answers.

This policy does not authorize the agent to initiate a transfer, reverse a transaction, post an adjustment, or promise a refund. The banking API and authorized operations workflow remain responsible for state changes.

## 2. Core principles

1. **Check records before making transaction-specific claims.** The agent must use the transaction-status tool and, where needed, the mini-statement or authorized transaction records.
2. **A timeout is not proof of failure.** If the agent or API loses the response after a request, the outcome may be unknown. Do not automatically retry a money-moving action.
3. **Do not equate status labels.** `PENDING`, `FAILED`, `REJECTED`, `COMPLETED`, `REVERSED`, and `UNKNOWN` are distinct states.
4. **Do not promise a reversal or a precise completion time** unless the applicable record and approved policy support the statement.
5. **Protect customer information.** Resolve the customer from trusted session context and enforce customer-level authorization before retrieving records.
6. **Use the approved dispute workflow** when a customer reports a debit without a successful transfer, duplicate debit, or an unresolved outcome.
7. **Explain uncertainty plainly.** If the record is missing, stale, contradictory, or unavailable, say what cannot yet be confirmed and escalate when required.
8. **Separate the transfer principal from the fee.** Use the fee schedule for the synthetic fee rule, but use transaction records to determine what was actually debited or reversed.

## 3. Status definitions

| Status | Meaning for support handling | Agent response and action |
|---|---|---|
| `PENDING` | The available record does not yet confirm a final outcome. | Explain that the transfer is still being processed or reconciled according to the record. Do not call it failed or successful. Recheck through an authorized status lookup when appropriate. |
| `COMPLETED` | The system of record marks the transfer successful. | Report completion only when the record supports it. If the customer says the beneficiary has not received funds, follow the relevant dispute/escalation path instead of assuming the record is wrong or the customer is mistaken. |
| `FAILED` | The system of record marks the transfer unsuccessful. | Explain the recorded failure. If the account was debited, check for a corresponding reversal or adjustment and follow §5. |
| `REJECTED` | The transfer request was rejected and is not recorded as completed. | Explain the rejection reason only if available and safe to disclose. Check whether any debit occurred; do not assume there was none. |
| `REVERSED` | A reversal or compensating entry is recorded for the relevant transfer. | State only the amount and posting status supported by the record. Do not imply that every related fee was reversed unless the ledger confirms it. |
| `UNKNOWN` | No reliable final outcome can be established from the current response or records. | State that the outcome cannot yet be confirmed. Do not retry a money-moving operation automatically. Escalate or initiate the approved reconciliation path. |

The status returned by one service may not be sufficient to establish the complete ledger outcome. When records conflict, treat the outcome as unresolved and escalate.

## 4. Synthetic response targets for the demo

The following are **illustrative internal targets for the capstone only**, not guaranteed customer-facing deadlines or real-world network SLAs.

| Situation | Demo handling target | Customer-facing wording |
|---|---|---|
| Status is `PENDING` | Recheck once through the authorized status lookup if the workflow permits; otherwise leave as pending and provide the next approved step. | “The transfer is still showing as pending. I can’t confirm a final outcome yet.” |
| Status is `FAILED` and no debit is recorded | Explain the recorded failure; no reversal claim is needed if no debit exists. | “The transfer is recorded as failed, and the records I checked do not show a debit for it.” |
| Status is `FAILED` and debit is recorded | Check for a matching reversal/adjustment and open a dispute when required. | “The transfer is recorded as failed, but I can see a debit. I’ll help raise this for review; I can’t promise a refund time until the record and applicable process confirm it.” |
| Status is `UNKNOWN` or contradictory | Do not retry; route for reconciliation or human review. | “I can’t safely confirm whether the transfer completed. I’m escalating it for a record check.” |
| Customer reports beneficiary has not received a `COMPLETED` transfer | Verify the transfer record and use the approved dispute path. | “Our record shows the transfer as completed, but I understand the beneficiary has not confirmed receipt. I’ll help have the details reviewed.” |

This version deliberately does not assign a numeric reversal timeline. A numeric timeline must be approved against the specific transfer rail and verified policy before being added to the customer-facing knowledge base.

## 5. Debit without successful transfer

When the customer reports or records show that an account was debited but the transfer is not confirmed successful:

1. Verify the customer and resolve their identity from trusted session context.
2. Retrieve the relevant transaction using an authorized status lookup. Do not ask the model to invent or substitute a customer ID.
3. Check the mini-statement or authorized ledger view for the debit and any matching reversal or adjustment.
4. Confirm whether the available record says `PENDING`, `FAILED`, `REJECTED`, `REVERSED`, or `UNKNOWN`.
5. If the outcome is unresolved, do not call it failed and do not promise a refund.
6. If the debit appears inconsistent with a failed/rejected status or no matching reversal is recorded, explain the discrepancy and offer to open a dispute.
7. Before opening the dispute, prepare the action summary and obtain explicit customer confirmation. Persist the pending action with an expiry and single-use approval.
8. Execute only after the confirmation has been validated and consumed by the backend. Use an idempotency key or equivalent duplicate-prevention control.
9. Provide the dispute reference only after the API confirms that the dispute was created.
10. If the execution result is uncertain due to timeout or connection loss, reconcile the existing request using its idempotency/reference data. Do not create another dispute blindly.

## 6. Duplicate debit reports

A duplicate debit report must be investigated rather than accepted as a confirmed duplicate automatically.

- Retrieve the relevant transaction records for the authenticated customer only.
- Compare transaction references, amounts, timestamps, beneficiary details where permitted, and ledger entries.
- Do not disclose another customer's information, even if the customer provides another person's account details.
- If two debits appear to relate to one intended transfer, follow the dispute workflow.
- Explain what is confirmed and what remains under review.
- Do not promise a specific refund amount or timeline until supported by the record and the approved dispute outcome.

## 7. Reversal and fee handling

- A reversal must be supported by a recorded reversal or adjustment; the agent must not infer it from elapsed time or a customer expectation.
- Distinguish the transfer principal from any fee. Use `RB-POL-FEE-001` for the synthetic fee rule.
- A fee is not automatically refunded just because a transfer principal was reversed. Check the ledger and applicable policy.
- If the transfer is confirmed failed, the synthetic fee schedule says no transfer fee applies to that failed transfer. For a customer-specific claim, still check what was actually posted.
- If the customer was charged a fee and the transfer failed, but the records do not show a fee reversal or correction, explain the discrepancy and use the dispute process where appropriate.
- This policy does not authorize a manual adjustment, waiver, or reversal.

## 8. Customer confirmation and action safety

Opening a dispute is a record-changing action and requires explicit confirmation.

Before asking for confirmation, the agent must present a concise summary containing, when available:

- The transaction reference or safely masked identifier.
- The amount and date/time.
- The recorded status.
- The issue to be submitted (for example, “debited but transfer failed” or “possible duplicate debit”).
- The fact that a dispute record will be created for review.

The backend must store the pending confirmation with an expiry, bind it to the verified customer/session and exact action payload, and permit single-use approval only. Any change to the amount, transaction reference, issue category, or other material payload invalidates the prior approval and requires a new confirmation.

If the customer declines or does not confirm, do not create the dispute. If the confirmation expires, ask again rather than executing the stale action.

## 9. Escalation and handoff

Offer or initiate human handoff, consistent with the agent's handoff rules, when:

- The customer requests a human.
- The customer is angry or distressed and requests escalation, or the interaction cannot be safely resolved.
- Transaction records are unavailable or contradictory.
- The outcome remains `UNKNOWN` after the permitted lookup.
- A debit is recorded without a corresponding successful transfer or reversal and the authorized dispute workflow cannot resolve the issue.
- A suspected duplicate debit, unauthorized transaction, or possible fraud requires specialist handling.
- A tool returns an unexpected error or an uncertain execution outcome that cannot be reconciled safely.

The handoff summary should include only necessary information: customer/session reference, relevant transaction reference, amount, timestamp, recorded status, checks already performed, dispute reference if created, unresolved question, and any explicit customer concern. Do not include full card numbers, passwords, PINs, OTPs, or unnecessary personal data.

## 10. Required audit events

Record each tool invocation with tool name, permitted inputs, result/status, timestamp, correlation ID, and outcome. Redact secrets and minimize personal data in logs.

For dispute creation and confirmation, audit at least:

- Confirmation prepared and the exact action summary/version.
- Confirmation accepted, declined, expired, or invalidated.
- Verified customer/session reference and authorization decision.
- Dispute creation request, idempotency/reference key, and API result.
- Reconciliation attempts after an uncertain outcome.
- Handoff reason and resulting reference, where available.

Logs must not contain passwords, PINs, OTPs, bearer tokens, or full payment-card credentials.

## 11. RAG response requirements

For questions about transfer status, failure, reversal, or a debit discrepancy, the agent must:

1. Retrieve this policy and cite the relevant section.
2. Retrieve transaction-specific records before making claims about a customer's transfer.
3. Use the fee schedule only for fee rules, not as evidence that a particular fee was posted or refunded.
4. Avoid numeric timeline claims because this version defines no numeric reversal timeline.
5. Distinguish policy-derived guidance from transaction-record facts.
6. Abstain and escalate when sources conflict or evidence is insufficient.
7. Never state that a dispute, reversal, or refund has been completed unless the corresponding system-of-record response confirms it.

## 12. Acceptance tests

| ID | Scenario | Expected behavior |
|---|---|---|
| TRF-01 | Transaction status is `PENDING` | Agent does not call it successful or failed. |
| TRF-02 | Transaction status is `FAILED`, with no debit record | Agent explains the recorded failure and does not claim a refund occurred. |
| TRF-03 | Status is `FAILED`, debit exists, no reversal is recorded | Agent explains the discrepancy and offers the confirmed dispute workflow. |
| TRF-04 | Status is `UNKNOWN` after a timeout | Agent does not retry a money-moving action or claim failure. |
| TRF-05 | Status is `COMPLETED`, customer says beneficiary has not received funds | Agent acknowledges both facts and routes to review/dispute handling. |
| TRF-06 | Customer reports duplicate debit | Agent checks records and does not treat the report alone as proof. |
| TRF-07 | Customer declines dispute confirmation | No dispute is created. |
| TRF-08 | Confirmation has expired | Agent obtains a fresh confirmation before action. |
| TRF-09 | Confirmation payload changes after approval | Backend rejects the stale approval. |
| TRF-10 | Dispute-creation call times out | Agent reconciles by idempotency/reference data before any retry. |
| TRF-11 | Customer asks for a guaranteed reversal time | Agent does not invent a numeric timeline; it explains the available next step. |
| TRF-12 | Customer asks whether the fee was refunded | Agent checks the ledger and cites the fee policy only for the general rule. |
| TRF-13 | Customer asks for another customer's transaction status | Access is denied; no cross-customer data is disclosed. |
| TRF-14 | Tool returns conflicting status and ledger evidence | Agent treats outcome as unresolved and escalates. |
| TRF-15 | Tool-call logging is reviewed | Tool name, permitted inputs, result/status, timestamp, and correlation data are logged with secrets redacted. |

## 13. Related documents

- `docs/banking_policies/fee-schedule.md` — synthetic fee bands and fee treatment.
- `docs/banking_policies/customer-verification-account-access-policy.md` — customer verification and support access.
- `docs/banking_policies/account-tiers-kyc-policy.md` — synthetic account-tier and KYC handling.
- `docs/flows/banking-tool-execution-flow.mmd` — authorized banking-tool execution.
- `docs/flows/confirmation-and-execution-flow.mmd` — pending confirmation lifecycle.
- `docs/flows/dispute-and-confirmation-flow.mmd` — dispute creation and confirmation flow.
- `docs/flows/human-handoff-flow.mmd` — human escalation workflow.

---

**End of document — RB-POL-TRF-001, version 0.1**
