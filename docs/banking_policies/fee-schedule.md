# Rubies MFB — Fee Schedule

**Document ID:** RB-POL-FEE-001  
**Version:** 0.1  
**Status:Final
**Policy owner:** Product and Banking Operations  
**Applies to:** Synthetic Rubies MFB capstone environment only  
**Effective date:** 1 October 2026 (demo policy date; not a real bank policy)  
**Review trigger:** Any change to the demo product scope, fee rules, or applicable regulatory requirements

> **Important scope notice:** Rubies MFB is fictional. Every fee amount, threshold, exemption, and processing rule in this document is a synthetic value created for the capstone. Do not present these values as actual fees charged by any Nigerian bank or as a statement of current CBN requirements. If this demo policy conflicts with applicable law or a verified official requirement, the official requirement takes precedence and the policy must be reviewed.

## 1. Purpose

This schedule is the source of truth for fee-related answers in the Rubies MFB Customer Support Agent. The agent must retrieve the relevant rule and cite the applicable section when answering questions about transfer charges or supported service fees.

The schedule does not authorize the agent to initiate a transaction, debit an account, waive a fee, or change a customer record. Those actions require the applicable banking API controls and confirmation workflow.

## 2. General rules

1. Fees are denominated in Nigerian naira (₦).
2. A fee applies only when the service and transaction meet the conditions in this schedule.
3. The transaction amount is the amount requested by the customer before any fee is added.
4. Unless a rule below explicitly says otherwise, a fee is charged once per successfully completed transaction, not once per attempt.
5. A failed, rejected, or cancelled transaction does not attract a transfer fee under this synthetic policy.
6. If a transfer is confirmed as failed but the account was debited, the agent must not promise an immediate refund. It should retrieve the transaction status and follow the failed-transfer/reversal policy. Any fee reversal must be confirmed from the transaction record or an authorized operations outcome.
7. The agent must not infer a fee from a vague description, invent an exemption, or calculate a total debit without confirming whether the fee is charged separately or included.
8. If the retrieved policy is missing, outdated, or inconsistent with the transaction record, the agent must explain that it cannot confirm the amount and hand off when needed.

## 3. Outbound electronic transfer fees

These bands are synthetic demo rules for transfers initiated from a Rubies MFB account to another bank account in Nigeria.

| Requested transfer amount | Synthetic Rubies fee per successful transfer |
|---|---:|
| ₦0.01–₦5,000.00 | ₦10 |
| ₦5,000.01–₦50,000.00 | ₦25 |
| Above ₦50,000.00 | ₦50 |

### 3.1 Application

- The applicable band is selected using the requested transfer amount, excluding the fee.
- The fee is assessed once when the transfer is successfully completed.
- For a transfer of exactly ₦50,000.00, the fee is ₦25.
- For a transfer of ₦50,000.01 or more, the fee is ₦50.
- The schedule defines the fee, but does not by itself define whether the fee is debited as a separate ledger entry or included in the total debit. The agent must inspect the transaction record or the banking API response before stating the customer's total debit.
- This schedule applies only to supported outbound electronic transfers. It does not establish fees for cash withdrawals, deposits, international transfers, card transactions, USSD sessions, loan repayments, or other services.

### 3.2 Examples

| Customer's requested transfer | Synthetic fee if successful | What the agent may say |
|---|---:|---|
| ₦2,000 | ₦10 | “Under Rubies MFB's demo fee schedule, a successful ₦2,000 transfer has a ₦10 fee.” |
| ₦25,000 | ₦25 | “Under the demo schedule, a successful ₦25,000 transfer has a ₦25 fee.” |
| ₦50,000 | ₦25 | “₦50,000 falls in the up-to-₦50,000 band, so the demo fee is ₦25.” |
| ₦50,001 | ₦50 | “₦50,001 is above ₦50,000, so the demo fee is ₦50.” |
| ₦200,000 | ₦50 | “Under the demo schedule, a successful ₦200,000 transfer has a ₦50 fee.” |

These examples illustrate this synthetic policy only. They are not representations of actual market charges or regulatory limits.

## 4. Failed, reversed, and duplicate-debit cases

### 4.1 Failed or rejected transfer

- The transfer fee under this schedule is ₦0 if the transfer is confirmed as failed, rejected, or cancelled.
- If the account was debited despite a failed status, the agent must not state that the principal or fee has already been refunded unless the transaction record confirms it.
- The agent should retrieve the transaction status and use the approved failed-transfer/reversal policy for timelines and next steps.
- If the status is pending, unknown, or contradictory, the agent must not classify the transfer as failed or successful without further evidence.

### 4.2 Reversal after a completed transfer

- A completed transfer is not automatically fee-free merely because a later adjustment or reversal is reported.
- The agent must inspect the transaction and reversal records. It must not promise that the transfer fee will be returned unless the records or an authorized policy decision support that statement.
- This schedule does not define reversal service-level timelines. Those belong in the separate failed-transfer and reversal policy.

### 4.3 Duplicate debit

- A customer report of a duplicate debit is a dispute signal, not proof that two completed transfers occurred.
- The agent should retrieve the relevant transaction records and, with the customer's required confirmation, open a dispute through the authorized tool.
- Do not promise a refund amount or timeline without a confirmed transaction record and the applicable dispute/reversal policy.

## 5. Exemptions, taxes, and waivers

- No general fee exemption, promotional waiver, staff waiver, or customer-tier discount is defined in this version.
- The agent must not invent or infer an exemption based on account tier, relationship, transaction purpose, or customer status.
- This document does not specify VAT, stamp duties, levies, or any other tax treatment. The agent must not add a tax amount to the synthetic fee unless a separately approved policy and transaction record explicitly support it.
- Only an authorized banking process may apply a waiver or adjustment. A conversational statement from a customer or an agent does not itself waive a fee.

## 6. Other services

No fee is established here for the following services:

- Inbound transfers
- Cash deposits or withdrawals
- Debit-card issuance, replacement, or maintenance
- ATM withdrawals or balance enquiries
- USSD access or session charges
- Bill payments and airtime/data purchases
- Loan application, disbursement, or repayment
- Account maintenance or statement requests
- International transfers or foreign-exchange services

If asked about one of these services, the agent must search the approved knowledge base for a separate, current policy. If none is available, it must say the fee cannot be confirmed from the available Rubies policy and offer a human handoff where appropriate. It must not treat “not listed” as “free.”

## 7. Customer-support response requirements

When answering a fee question, the agent must:

1. Identify the service and the relevant amount, where applicable.
2. Retrieve the current approved fee schedule rather than relying on model memory.
3. State that the amount comes from the **Rubies demo fee schedule** when there is a risk of confusion with real-world banking charges.
4. Explain the relevant band and fee in plain language.
5. Cite this document and the specific section or table used (for example, “RB-POL-FEE-001, §3”).
6. Distinguish the scheduled fee from the total debit if the transaction record does not establish how the fee is posted.
7. For a specific transaction, retrieve transaction status/records before asserting whether a fee was charged, reversed, or refunded.
8. Abstain and hand off if the retrieved source is absent, stale, conflicting, or insufficient to answer safely.

### 7.1 Example customer-facing answers

**Question:** “How much do you charge to transfer ₦60,000?”

**Approved answer:** “Under Rubies MFB's demo fee schedule, a successful ₦60,000 outbound transfer has a ₦50 fee. This is the capstone's synthetic fee, not a statement of fees charged by a real bank. (RB-POL-FEE-001, §3.)”

**Question:** “I sent ₦25,000 but it failed. Will you still charge me?”

**Approved answer:** “Under the Rubies demo policy, a transfer confirmed as failed does not attract a transfer fee. I’ll need to check the transaction status before confirming how your specific transfer was recorded. (RB-POL-FEE-001, §4.1.)”

**Question:** “I was debited twice. Is one fee coming back?”

**Approved answer:** “I’m sorry this happened. A duplicate debit needs to be checked against the transaction records. I can help open a dispute after confirming the details; I won’t promise a fee refund until the records and applicable policy confirm it. (RB-POL-FEE-001, §4.3.)”

## 8. Knowledge-base and versioning requirements

- The document must be stored as an approved source document before it is used for production-style RAG evaluation.
- Ingestion metadata should include document ID, title, version, effective date, status, policy owner, and source path.
- Chunks must retain the document ID and section heading so answers can cite the exact source section.
- Superseded versions must be marked inactive for current retrieval while remaining available for audit and regression testing.
- A change to a fee band, effective date, exemption, or failed-transfer treatment requires a version increment and regression tests for values below, at, and above each boundary.
- Retrieval must not combine fee rules from different versions into a single answer.

## 9. Acceptance tests

The policy and its RAG implementation should pass at least these tests:

| ID | Test | Expected result |
|---|---|---|
| FEE-01 | Ask the fee for a successful ₦2,000 outbound transfer | Returns ₦10 and cites §3 |
| FEE-02 | Ask the fee for a successful ₦25,000 outbound transfer | Returns ₦25 and cites §3 |
| FEE-03 | Ask the fee for exactly ₦50,000 | Returns ₦25 and cites §3.1 |
| FEE-04 | Ask the fee for ₦50,000.01 | Returns ₦50 and cites §3.1 |
| FEE-05 | Ask the fee for ₦200,000 | Returns ₦50 and identifies the values as synthetic demo fees |
| FEE-06 | Ask whether a confirmed failed transfer attracts a fee | Returns ₦0 under §4.1 |
| FEE-07 | Ask whether a specific customer's fee was refunded without transaction data | Does not guess; requests status lookup or hands off |
| FEE-08 | Ask for an unlisted card or ATM fee | Says this schedule does not define it; searches for a separate policy or hands off |
| FEE-09 | Ask whether VAT is included | Does not invent a tax treatment; cites §5 |
| FEE-10 | Ask for a real Nigerian bank's current transfer fee | Does not present Rubies synthetic values as real-world facts |
| FEE-11 | Retrieve conflicting versions | Uses only the approved active version or abstains if status cannot be resolved |
| FEE-12 | Ask for the total debit including fee | Does not infer fee-posting treatment without transaction/API evidence |

## 10. References and boundaries

This is a fictional product policy for a capstone simulator, not legal, tax, or regulatory advice. No claim is made here about the actual fee rules of Nigerian banks or the current requirements of the Central Bank of Nigeria. Any real-world regulatory review must be documented separately using current official sources before this schedule is adapted beyond the synthetic environment.

---

**End of document — RB-POL-FEE-001, version 0.1**
