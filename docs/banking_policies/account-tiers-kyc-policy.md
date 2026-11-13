# Account Tiers and KYC Policy

- **Document ID:** RUBIES-POL-KYC-001
- **Status:Final
- **Owner:** Project owner / Banking policy owner (to be assigned)
- **Applies to:** Synthetic customer/account data, customer-support explanations, and account-tier-related business rules in the Rubies MFB capstone
- **Related documents:** `docs/banking_policies/customer-verification-account-access-policy.md`; `docs/security/security-model.md`; `docs/security/threat-model-security-controls.md`
- **Implementation status:** Design policy for a fictional bank; not a representation of Rubies MFB as a real institution or a certification of regulatory compliance

## 1. Purpose and boundaries

This policy defines how the capstone represents account tiers, customer due diligence (CDD), verification status, and restrictions associated with incomplete KYC.

Rubies MFB is fictional. Synthetic tier names and operational values may be used for demonstrations, but must not be presented as current CBN-mandated limits unless each value is verified against the applicable current instrument.

This document distinguishes:

1. **Regulatory requirements:** Requirements stated in applicable official CBN instruments.
2. **Rubies synthetic product rules:** Demonstration values created for this fictional bank.
3. **Implementation controls:** System behavior required to enforce the chosen policy.

The current CBN circular on Tier 1 wallets and accounts, dated 1 December 2023, states that new Tier 1 accounts and wallets must not be opened without BVN or NIN, requires electronic validation/revalidation, and describes restrictions for accounts without BVN or NIN. The CBN's public BVN page also summarizes the December 2023 requirements for Tier 1, Tier 2, and Tier 3 individual accounts and wallets. The exact limits and detailed requirements must be checked in the applicable official guidance before any compliance claim is made. citeturn0search23turn0search0

## 2. Core policy rules

1. No customer is assigned a higher KYC tier merely because the customer requests it.
2. KYC status must be represented explicitly in the synthetic customer record and must not be inferred by the language model.
3. A submitted identifier is not equivalent to successful verification. The onboarding/verification process must use the approved source and record the result.
4. For the fictional capstone, do not create a new Tier 1 account with neither BVN nor NIN.
5. A tier upgrade is completed only after the required evidence has been collected, validated, reviewed where required, and persisted by the backend.
6. If a required check fails, conflicts with another source, or is unavailable, do not mark the customer as verified or silently raise the tier.
7. Apply transaction, balance, and service restrictions from the configured policy record, not from model memory or hard-coded natural-language answers.
8. Do not use actual BVN/NIN values in synthetic datasets. Use clearly synthetic identifiers that cannot be mistaken for real validated identifiers.
9. The support agent may explain the recorded tier and required next steps, but it cannot itself approve a KYC upgrade unless a separately authorized backend workflow explicitly permits that operation.
10. Account-tier restrictions are separate from support-session verification. Passing support verification does not automatically change account KYC status.

## 3. Tier model for the capstone

The capstone should use an explicit, versioned configuration for tier definitions. Until the relevant current CBN guidance has been checked and approved for the intended account type, use the following **non-numeric design model**. Do not infer transaction or balance limits from eNaira wallet limits, older circulars, or unrelated product categories.

| Synthetic tier label | Intended demonstration profile | KYC state | Permitted system behavior |
|---|---|---|---|
| `TIER_1` | Entry-level individual account profile | Required Tier 1 identity requirements recorded and validated according to the policy version in force | Apply configured Tier 1 limits and restrictions; block onboarding if mandatory identity requirements are absent |
| `TIER_2` | Individual account with the next approved verification level | Required identity evidence and validation recorded according to the approved policy | Apply configured Tier 2 limits and allowed services |
| `TIER_3` | Individual account with the higher approved verification level | Required identity evidence, address/evidence checks, and any applicable review recorded according to the approved policy | Apply configured Tier 3 limits and allowed services |
| `RESTRICTED_PENDING_KYC` | Existing synthetic account with missing, invalid, conflicting, or overdue required identity information | KYC incomplete or requires remediation | Enforce the configured restriction; do not permit a tier upgrade or bypass |
| `KYC_REVIEW_REQUIRED` | Case needs authorized manual review | Automated checks insufficient or conflicting | Prevent the upgrade until the designated reviewer records a decision |

These labels are for the capstone's internal model. The precise mapping to regulatory account categories, required documents, limits, and restrictions is an explicit implementation dependency. Do not assume that these rows reproduce all CBN account categories or all institution-specific obligations.

## 4. KYC status fields

The synthetic customer/account model should separate **tier** from **verification status**. Recommended fields are:

| Field | Purpose |
|---|---|
| `accountTier` | Configured tier label, such as `TIER_1`, `TIER_2`, or `TIER_3` |
| `kycStatus` | Controlled state such as `NOT_STARTED`, `PENDING`, `VERIFIED`, `REJECTED`, `EXPIRED`, or `REVIEW_REQUIRED` |
| `identityType` | Synthetic indicator for the identity evidence type required by the approved policy; do not store actual BVN/NIN values in demonstration fixtures |
| `identityValidationStatus` | `NOT_CHECKED`, `PENDING`, `VALID`, `INVALID`, or `UNAVAILABLE` |
| `addressVerificationStatus` | `NOT_REQUIRED`, `PENDING`, `VERIFIED`, `FAILED`, or `REVIEW_REQUIRED`, where relevant |
| `policyVersion` | Version of the approved tier/KYC rules used for the decision |
| `lastReviewedAt` | Timestamp of the last completed verification or review |
| `restrictionCode` | Controlled reason for a restriction, avoiding unnecessary sensitive details |
| `reviewReference` | Synthetic reference to an authorized review record, where applicable |

These are proposed domain fields, not a claim that the existing repository already contains them. Final field names and persistence choices must be reconciled with the data architecture and banking API contract before implementation.

## 5. Tier assignment and upgrade workflow

1. Create or locate the customer record through the approved onboarding flow.
2. Determine the applicable account type and policy version.
3. Collect only the identity information required by that policy.
4. Validate identity evidence through the approved authoritative source or verification service.
5. Record the verification result, time, policy version, and necessary audit metadata.
6. If additional evidence or human review is required, keep the customer in the appropriate pending/review state.
7. Evaluate the tier-upgrade request against the policy configuration and required evidence.
8. Apply the new tier and its limits atomically only after all required checks pass.
9. Recalculate or apply the applicable restrictions from the versioned policy; do not leave old limits active accidentally.
10. Record the decision and its source evidence reference without logging raw identity secrets.
11. If any required service is unavailable or evidence conflicts, do not upgrade; retain a safe state and provide the approved recovery/handoff path.

The agent may collect the customer's intent and explain the workflow. The backend owns validation, authorization, persistence, and tier assignment.

## 6. Restrictions and enforcement

The Banking API/service must enforce the configured tier restrictions at the point of each relevant operation. A conversational explanation or UI warning is not enforcement.

At minimum, policy configuration should support:

- Maximum transaction value, where applicable.
- Cumulative transaction limits over the applicable period, where applicable.
- Maximum account/wallet balance, where applicable.
- Enabled/disabled product and channel capabilities.
- Restriction state and reason code.
- Effective date and policy version.
- Exception handling, if any, with explicit authorization and audit.

Do not fill these values with guessed numbers. Before implementation, record the current approved values for the precise account type and product in a controlled policy configuration, together with the official source, effective date, and reviewer.

If the account is restricted because a required identity check is missing or invalid, the system must enforce the restriction defined by the applicable current rule. Do not generalize a restriction from one instrument to every account type without confirming its scope.

## 7. Customer-facing explanations

When answering questions about account tiers or KYC:

- Use the customer's recorded tier and status from the backend when discussing their individual account.
- Use the currently approved knowledge-base policy source for general requirements.
- Explain the next required step without asking the customer to post a full BVN, NIN, password, PIN, or one-time passcode in the conversation.
- Distinguish an incomplete application from a rejected verification and from an account restriction.
- Do not promise an upgrade, removal of a restriction, or specific processing time unless supported by an approved source and the customer's current case status.
- If sources conflict or the system cannot retrieve the current policy, state that the information cannot be confirmed and hand off where appropriate.
- Do not present synthetic limits as actual CBN requirements.

## 8. Synthetic data requirements

Synthetic records should cover:

- A customer in each configured tier.
- A customer with KYC pending.
- A customer with failed or conflicting identity validation.
- A customer awaiting manual review.
- An existing account subject to a configured restriction.
- A customer whose upgrade succeeds only after required evidence is validated.

All identifiers must be clearly synthetic and must not be real BVN/NIN data. Synthetic account limits must be labeled as demo configuration unless reviewed against a current official instrument. Use deterministic fixture values so automated tests can reproduce the same tier and restriction outcomes.

## 9. Audit and version control

For tier assignment, upgrade, rejection, restriction, and review decisions, record:

- Synthetic customer/account reference.
- Previous and new tier/status, where applicable.
- Policy version.
- Decision category and timestamp.
- Authorized actor or service identity.
- Verification outcome reference, not raw identity secrets.
- Restriction applied or removed.
- Correlation identifier and outcome.

Access to audit records must be restricted. Any correction to a KYC status or tier must use an authorized backend operation and create an auditable state transition; direct database edits must not be the normal support workflow.

## 10. Required tests

Before claiming this policy is implemented, tests must demonstrate:

1. A new Tier 1 account cannot be created without the mandatory identity requirement configured for the applicable policy.
2. A supplied but unvalidated identifier does not satisfy the verification requirement.
3. A tier upgrade is denied when evidence is missing, invalid, conflicting, expired, or awaiting review.
4. Tier and KYC status are stored separately and can represent a restricted/pending state.
5. The Banking API enforces configured transaction, balance, and service restrictions; the agent cannot bypass them.
6. Policy-version changes apply predictably and do not accidentally preserve obsolete limits.
7. The agent does not reveal or request prohibited secrets in customer-facing explanations.
8. Synthetic datasets contain no real BVN/NIN values.
9. Customer-facing answers distinguish CBN-backed requirements from Rubies synthetic demo rules.
10. Audit records capture tier transitions without storing raw identity secrets.

## 11. Open decisions before implementation

The following must be resolved and recorded before using numeric limits or claiming compliance:

- The exact account/product category the synthetic tiers represent.
- The current applicable CBN circulars, guidance notes, and any subsequent amendments.
- Required identity fields and the exact BVN/NIN rules for the selected category.
- Current transaction, cumulative transaction, and balance limits.
- Required proof-of-address and additional evidence by tier.
- Restriction behavior for missing, invalid, or conflicting identity data.
- Verification provider/source, retry behavior, expiry, and manual-review workflow.
- Final domain field names and policy-configuration schema.
- Compliance/legal review owner and review date.

## 12. Official reference sources

1. **CBN — Circular on Tier 1 Wallets and Accounts, Guidance Note and Profiling of All Customer Accounts/Wallets (1 December 2023):** official PDF, including the scope of the requirements and restrictions for Tier 1 accounts/wallets. urlOfficial CBN Tier 1 accounts and wallets circularturn0search23
2. **CBN — BVN information and regulatory updates:** summarizes the December 2023 requirements for individual Tier 1, Tier 2, and Tier 3 accounts/wallets and related verification updates. urlCBN BVN pageturn0search0
3. **CBN — Reforms and Initiatives:** current regulatory update landing page; review for later amendments and security-related requirements before implementation. urlCBN Reforms and Initiativesturn0search1

Review these sources again before finalizing the numeric configuration. The policy is a capstone design artifact, not legal advice or a certification of regulatory compliance.
