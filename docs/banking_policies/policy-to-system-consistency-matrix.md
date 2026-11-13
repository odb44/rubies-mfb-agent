# Rubies MFB — Policy-to-System Consistency Matrix

**Artifact ID:** RB-DES-POL-CONS-001  
**Version:** 1.0  
**Status:** Reconciliation complete — design record  
**Scope:** Cross-check of the nine drafted banking-policy/knowledge documents against the agreed system invariants.  
**Purpose:** Record supported consistency findings and genuine implementation dependencies without rewriting approved architecture or changing the locked repository schema.

## 1. Executive result

The reviewed policy material is broadly consistent on the core safeguards: trusted customer context, backend authorization, explicit confirmation for sensitive state changes, authoritative transaction records, no invented fees or timelines, and human handoff when needed.

**No major cross-policy contradiction was identified in this review.** The matrix distinguishes consistent policy rules from unresolved implementation dependencies. This is a completed documentation reconciliation record, not evidence that code, data, or tests exist or have passed.

## 2. Cross-policy matrix

| ID | Topic / documents compared | Expected invariant | Finding | Classification | Recommended disposition |
|---|---|---|---|---|---|
| PCM-01 | Fee schedule ↔ transfer failure/reversal ↔ FAQ | Failed/rejected/cancelled transfers have no transfer fee under the synthetic schedule; account-specific status must be checked before stating what happened. | Consistent. The fee schedule explicitly directs debit-with-failed-status cases to the reversal policy; the FAQ avoids treating the customer's report alone as authoritative status. | Consistent | Keep the FAQ subordinate to the fee schedule and transaction record. |
| PCM-02 | Duplicate debit ↔ disputes ↔ confirmation lifecycle | A customer report is a signal, not proof; a dispute requires explicit confirmation; timeouts require reconciliation before retry. | Consistent in the reviewed material. | Consistent | Ensure the dispute flow persists the pending action and uses idempotency/reconciliation as specified in the existing flow design. |
| PCM-03 | Card policy ↔ fraud policy ↔ disputes/handoff | Lost/stolen or compromised card reports should receive safe guidance; blocking requires confirmation; success must not be claimed until backend confirmation; urgent uncertainty can be escalated. | Consistent. Card policy and fraud policy both prohibit unsupported claims and secrets in chat. | Consistent | Keep card blocking as a controlled state change; do not let urgent wording bypass verification, authorization, or confirmation. |
| PCM-04 | Customer verification ↔ KYC/account-tier policy ↔ verification flow | Support-session verification is distinct from regulatory KYC tier/status; the agent may explain recorded status but cannot silently upgrade it. | Consistent. The updated verification flow now explicitly states this separation. | Consistent | Retain the two explanatory notes in the updated `customer-verification-flow.mmd`. |
| PCM-05 | Loan policy ↔ customer verification ↔ FAQ | Eligibility assessment, existing application/loan status, credit decision, and disbursement are separate concepts. | Consistent. The loan policy assigns eligibility and status to different tools and forbids promises based only on eligibility. | Consistent | Preserve separate response wording and tool routing for eligibility versus recorded status. |
| PCM-06 | All policies ↔ trusted identity / authorization model | Customer-specific access must use trusted session context and backend ownership/permission checks; model-supplied customer identity is not authoritative. | Consistent in the reviewed policy excerpts. | Consistent | Enforce at the Banking API/service boundary; do not rely on prompt instructions alone. |
| PCM-07 | All policies ↔ confirmation policy | Dispute creation and card blocking require action-specific, persistent, expiring, single-use confirmation; confirmation does not replace verification or authorization. | Consistent in the reviewed excerpts. | Consistent | Use one backend-enforced confirmation lifecycle rather than separate weaker implementations per tool. |
| PCM-08 | Fee schedule ↔ card/USSD/app ↔ FAQ | Only documented fees may be stated; no card/ATM/USSD/app fees or USSD codes should be invented. | Consistent. The fee schedule limits itself to defined outbound transfer bands; the channel policy says unspecified charges and codes cannot be confirmed. | Consistent | Keep unknown service charges explicitly unknown until a separately approved source is added. |
| PCM-09 | Transfer policy ↔ fraud policy ↔ handoff policy | A timeout or conflicting evidence is an unknown outcome, not proof of success or failure; no guaranteed reversal or recovery timeline. | Consistent in the reviewed material. | Consistent | Reconcile authoritative records before safe retries; escalate unresolved or conflicting outcomes. |
| PCM-10 | KYC policy ↔ regulatory references | Synthetic tiers/limits must not be represented as verified regulatory limits; numeric compliance configuration requires current official-source review. | Consistent in the policy's stated boundaries. Regulatory verification remains an open dependency, not a demonstrated contradiction. | Open dependency | Before implementation or compliance claims, verify the applicable current CBN instruments and later amendments for the chosen account category. |
| PCM-11 | Loan policy ↔ product FAQ | Product amounts/terms are synthetic; interest, fees, repayment schedules, and disbursement timing are undefined unless another approved source exists. | Consistent in the reviewed excerpts. | Open dependency | Do not add repayment calculations or extra loan terms without a separately approved product-terms source. |
| PCM-12 | Customer verification ↔ operational handoff | Handoff must follow channel privacy rules, include minimum necessary information, and only be reported as successful when confirmed. | Consistent in the reviewed excerpts. Actual operational destination and failure behavior depend on configured implementation. | Open dependency | Define the human queue/channel, payload schema, acknowledgement, urgency handling, and failure fallback before implementation. |
| PCM-13 | Policy documents ↔ RAG citations/versioning | Policy answers should cite approved source sections; outdated/conflicting or insufficient evidence requires abstention or escalation. | Consistent as a design rule. Corpus manifests, version selection, and citation validation are not yet evidence of implementation. | Implementation dependency | Define active-version selection, document metadata, citation format, and stale/conflict handling in the knowledge-base design. |
| PCM-14 | Policy documents ↔ tool contracts | Policy statements that depend on actual account, transaction, card, dispute, or loan state require an authorized tool lookup. | Consistent in the reviewed excerpts. Exact response schemas and status enums still need to be finalized against the locked API/tool contracts. | Implementation dependency | Reconcile tool schemas and enum values before coding; do not infer a result from FAQ/policy text. |
| PCM-15 | Tool-call logging ↔ security/fraud/loan policies | Every tool call is logged with useful audit/correlation information while secrets and unnecessary personal data are redacted. | Consistent as a stated requirement. Exact common event schema and retention/access policy remain implementation details. | Implementation dependency | Define a shared audit event contract and redaction rules before implementing handlers. |

## 3. Items deliberately not resolved by this matrix

The following are not contradictions to fix by guessing. They are decisions or evidence that must be supplied before implementation:

1. **Regulatory KYC configuration:** selected account category, applicable current CBN instruments, identity requirements, numeric limits, restriction behavior, and compliance reviewer.
2. **Human handoff operation:** actual queue/channel, service-level targets if any, priority mapping, acknowledgement semantics, and fallback when the handoff tool fails.
3. **Canonical API/tool schemas:** exact field names, enum values, error shapes, correlation/idempotency fields, and ownership checks.
4. **Common audit event:** mandatory fields, secret redaction, access control, retention, and correlation across agent, agent tools, Banking API, and model inference.
5. **Knowledge versioning:** active policy version, effective dates, source-section identifiers, superseded-document behavior, and citation validation.
6. **Loan product terms:** rates, fees, repayment schedules, and disbursement terms remain undefined unless a separately approved source is introduced.
7. **Synthetic fixture coverage:** ensure fixtures actually include the intended failed transfer, duplicate debit, card customer, and active-loan cases without using real customer identifiers or secrets.

## 4. Reconciliation outcome

- **Major contradictions found:** None established in this review.
- **Clarifications completed:** Support verification versus regulatory KYC status is now stated in the updated verification flow.
- **Open dependencies recorded:** Regulatory KYC configuration, handoff operations, canonical schemas, audit contract, knowledge versioning, loan terms, and fixture coverage.
- **Repository schema changes:** None.
- **Architecture decision changes:** None.
- **Implementation or test status claimed:** None.

## 5. Closure and follow-on work

This consistency-matrix artifact is complete for the current design stage. It records the cross-policy checks, the findings supported by the reviewed material, and the unresolved dependencies without changing the locked repository schema or approved architecture decisions.

The follow-on artifact, when work resumes, should be the **evaluation specification**: define the RAG question set, scripted tool scenarios, safety/attack cases, Nigerian Pidgin coverage, expected outcomes, scoring criteria, and pass/fail thresholds. It should reference these policy invariants so evaluation tests the agreed behavior rather than inventing new rules.

**Closure boundary:** “Reconciliation complete” means the documentation check is recorded. It does not mean the separately delivered files have been copied into the repository, implementation dependencies have been resolved, or implementation/tests are complete.
