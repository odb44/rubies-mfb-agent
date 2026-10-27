# Rubies MFB — Loan Products and Eligibility Policy

**Document ID:** RB-POL-LOAN-001  
**Version:** 0.1  
**Status:** Design draft  
**Policy owner:** Lending Operations and Product  
**Applies to:** Synthetic Rubies MFB capstone environment only  
**Effective date:** 1 October 2026 (demo policy date; not a real bank policy)  
**Review trigger:** Changes to the synthetic loan products, eligibility rules, model version, or applicable verified requirements

> **Important scope notice:** Rubies MFB is fictional. Loan products, thresholds, terms, decision rules, and examples in this document are synthetic capstone design choices. They are not offers from a real financial institution, a statement of Nigerian lending regulation, or a guarantee of credit approval. Applicable verified legal and regulatory requirements take precedence and must be reviewed separately.

## 1. Purpose

This policy defines the synthetic loan products supported by the Rubies MFB Customer Support Agent, the distinction between an eligibility check and a loan decision, the information the agent may retrieve, and how model outputs should be explained.

The agent's `check_loan_eligibility` tool provides an eligibility assessment under the approved demo rules. It does not approve, disburse, or promise a loan. The `get_loan_status` tool retrieves the recorded status of an existing loan application or loan account. Only an authorized lending workflow may make and record an actual lending decision.

## 2. Synthetic loan products

The capstone supports two illustrative products. The amounts and terms below are invented for testing and must not be presented as actual market offers.

| Product code | Product name | Synthetic purpose | Illustrative principal range | Illustrative term |
|---|---|---|---:|---|
| `SALARY_ADVANCE` | Salary Advance | Short-term liquidity for an eligible salaried customer. | ₦20,000–₦200,000 | 1–3 months |
| `MICRO_BUSINESS` | Micro Business Loan | Small working-capital support for an eligible micro-business customer. | ₦50,000–₦500,000 | 3–6 months |

These ranges are demo product definitions only. This version does not define interest rates, APR, processing fees, late charges, collateral requirements, repayment schedules, or disbursement timelines. The agent must not invent those details. If a customer asks about them, it must retrieve a separate approved product terms document or hand off.

## 3. Eligibility check versus loan approval

These are separate concepts:

- **Eligibility assessment:** A preliminary result based on the available synthetic customer data and the versioned demo rules/model.
- **Application status:** The status recorded for a particular application in the loan system.
- **Credit decision:** A decision made through the authorized lending workflow, potentially including additional checks not represented by the eligibility model.
- **Disbursement status:** Evidence that funds were or were not disbursed, as recorded by the system of record.

A customer who passes the eligibility check is not guaranteed approval. A customer who does not pass the check must not be told that they are permanently ineligible for every Rubies product. The agent must state the result and scope precisely.

## 4. Minimum inputs and data provenance

The eligibility tool may use only the approved input schema and data the caller is authorized to access. The initial synthetic design may include:

- Product code requested.
- Customer identity/reference from trusted session context.
- Account/customer status required by the approved eligibility rules.
- Employment or business profile fields, where relevant to the product.
- Synthetic income or cash-flow features, if present in the approved data contract.
- Existing loan exposure or repayment-status features, if explicitly defined in the model schema.
- Model/ruleset version and assessment timestamp.

This document does not establish a complete feature schema or numerical cutoffs for every input. Those must be defined in the loan-model specification and the versioned feature contract before implementation. Do not infer missing values, silently substitute defaults, or ask the customer to disclose credentials or unnecessary sensitive information.

Every feature used in a decision explanation must have a documented source and a defined treatment for missing, stale, invalid, or contradictory data.

## 5. Synthetic eligibility workflow

1. Resolve the customer from trusted session context and apply the required access controls.
2. Validate that the requested product code is supported.
3. Retrieve the authorized customer/application data required by the approved feature contract.
4. Check for missing, stale, invalid, or contradictory inputs. If required data is unavailable, return `INSUFFICIENT_DATA` or the equivalent defined result rather than inventing values.
5. Run the approved versioned rules/model through the loan-model inference interface.
6. Return a structured assessment containing the product code, result, assessment timestamp, model/ruleset version, and permitted explanation fields.
7. Store or audit the assessment according to the approved data-retention and audit design.
8. Explain that the result is preliminary and does not constitute approval.
9. If the result is uncertain, unsupported, or outside the model's validated scope, abstain from a definitive eligibility claim and hand off to the authorized lending team.

The model must not initiate a loan, change an application status, create a disbursement, or alter a customer record. Those actions remain outside the model's authority.

## 6. Result categories

Use only categories defined in the implemented, versioned loan-model contract. The following are proposed conceptual categories for the demo; they must be mapped explicitly to the actual API schema before implementation.

| Proposed result | Meaning | Customer-support handling |
|---|---|---|
| `ELIGIBLE_FOR_REVIEW` | Available inputs meet the demo's preliminary eligibility criteria. | Explain that the customer may proceed to the next authorized application/review step; do not promise approval. |
| `NOT_ELIGIBLE_UNDER_CURRENT_RULES` | Available inputs do not meet one or more demo criteria. | Explain only the permitted, supported factors. Do not imply permanent exclusion or expose internal security controls. |
| `INSUFFICIENT_DATA` | Required inputs are missing, stale, invalid, or contradictory. | State that the assessment cannot be completed from current data; request only necessary corrections through an approved workflow or hand off. |
| `OUT_OF_SCOPE` | The product or case is not supported by the current model/ruleset. | Do not extrapolate a result. Explain the limitation and hand off if appropriate. |
| `ASSESSMENT_ERROR` | The assessment could not be completed due to a service or inference error. | Do not guess a result; report the limitation and use the approved retry/handoff behavior. |

These names are proposals, not a claim that the API already implements them. Final enum values must match the shared schema and model interface exactly.

## 7. Explanation requirements

When explaining an eligibility result, the agent must:

1. Retrieve the actual result from `check_loan_eligibility`; do not estimate it from a chat description.
2. Identify the product assessed and the timestamp/version when available.
3. Say clearly that the result is preliminary and is not loan approval.
4. Explain only factors returned by the approved explanation interface and permitted by policy.
5. Distinguish data facts from model inferences. For example, “the recorded income field was missing” is different from “the model predicts low repayment capacity.”
6. Avoid unsupported causal explanations, invented thresholds, or claims of certainty.
7. If the result cannot be explained reliably, state that limitation and hand off.
8. Never reveal internal fraud signals, secrets, or another customer's data.

For a `NOT_ELIGIBLE_UNDER_CURRENT_RULES` result, the agent must not manufacture a reason if the model provides no permitted reason. It should explain that the current assessment did not meet the demo criteria and offer the authorized next step.

## 8. Fairness, privacy, and responsible use

- Use synthetic data for capstone training, testing, and demonstration.
- Do not use real customer records or sensitive personal data in model training unless a separate lawful, approved process explicitly permits it.
- Do not infer protected or sensitive attributes from names, location, language, or other proxies.
- Document the purpose, provenance, transformation, and limitations of every model feature.
- Evaluate model performance across relevant synthetic segments and report limitations; synthetic evaluation does not establish real-world fairness or creditworthiness.
- Restrict access to eligibility inputs, outputs, explanations, and model artifacts.
- Log model version, feature-schema version, timestamp, result, and relevant non-sensitive explanation metadata for reproducibility.
- Do not expose raw feature vectors or internal model diagnostics to customers.
- Provide a human-review route for disputed, unsupported, or insufficient-data results.
- Do not state that a model output is an adverse credit decision unless the authorized lending workflow has recorded such a decision.

## 9. Existing loan status

For questions about an existing application or loan, use `get_loan_status` and the authorized loan record. Do not use an eligibility assessment as a substitute for application status.

The agent may report only fields supported by the API, such as a recorded application/loan status or an approved next step. This document does not define the final loan-status enum. The API contract must specify it.

If the status tool returns no record, an error, or a conflicting result, the agent must say it cannot confirm the status and offer handoff where appropriate. It must not infer that an application was rejected, approved, paid out, or cancelled from the absence of a record.

## 10. Fees, rates, repayment, and disbursement

This policy does not establish:

- Interest rates, APR, or profit rates.
- Processing or administration fees.
- Late-payment penalties.
- Collateral, guarantor, or documentation requirements.
- Repayment dates, instalment amounts, or collection methods.
- Loan approval or disbursement timelines.
- Early repayment, restructuring, or settlement terms.

If asked, the agent must retrieve an approved, current product terms source. If no source exists, it must state that the terms cannot be confirmed and offer a human handoff. It must not calculate a repayment amount from an invented rate or promise funds by a particular date.

## 11. Audit and failure handling

Record the eligibility tool invocation with tool name, permitted inputs or input references, result/status, timestamp, correlation ID, model version, feature-schema version, and outcome. Redact secrets and minimize personal data.

For failures:
- Do not convert a timeout into an eligibility result.
- Do not retry indefinitely.
- If a safe retry is permitted, use the same request/correlation reference where supported.
- If repeated failure, conflicting outputs, or invalid model artifacts occur, return an error/insufficient-data outcome and hand off.
- Do not modify a loan application or disburse funds as a side effect of an eligibility check.

## 12. RAG response requirements

For loan-product and eligibility questions, the agent must:

1. Retrieve this policy and cite the relevant section.
2. Retrieve actual customer-specific assessment/status data before making a personalized claim.
3. Label all product amounts and terms in this document as synthetic demo values.
4. Distinguish eligibility, approval, application status, and disbursement.
5. Avoid rates, fees, repayment calculations, deadlines, or documentation claims not supported by an approved current source.
6. Use the versioned model explanation rather than inventing reasons.
7. Abstain and hand off when required data or evidence is insufficient.
8. Never promise approval or disbursement based only on the eligibility tool.

## 13. Acceptance tests

| ID | Scenario | Expected behavior |
|---|---|---|
| LOAN-01 | Customer asks for the synthetic Salary Advance range | Agent reports ₦20,000–₦200,000 and labels it as demo-only. |
| LOAN-02 | Customer asks whether eligibility means approval | Agent clearly distinguishes preliminary eligibility from approval. |
| LOAN-03 | Eligibility tool returns `ELIGIBLE_FOR_REVIEW` | Agent explains the preliminary result without promising approval. |
| LOAN-04 | Eligibility tool returns `NOT_ELIGIBLE_UNDER_CURRENT_RULES` without a reason | Agent does not invent a reason. |
| LOAN-05 | Required input is missing | Tool returns insufficient-data equivalent; agent does not guess or silently default. |
| LOAN-06 | Unsupported product is requested | Agent returns/communicates out-of-scope and does not extrapolate. |
| LOAN-07 | Inference service times out | Agent does not invent a result and follows approved error/handoff behavior. |
| LOAN-08 | Customer asks for interest rate not defined in this policy | Agent retrieves a separate approved terms source or says it cannot confirm. |
| LOAN-09 | Customer asks when funds will be disbursed based only on eligibility | Agent does not promise a date. |
| LOAN-10 | Customer asks for existing application status | Agent uses `get_loan_status`, not the eligibility tool. |
| LOAN-11 | Loan status lookup returns no record | Agent does not infer approval, rejection, or disbursement. |
| LOAN-12 | Customer asks for another customer's loan details | Access is denied; no cross-customer data is disclosed. |
| LOAN-13 | Model explanation conflicts with the returned result or feature data | Agent abstains and escalates for review. |
| LOAN-14 | Model output is reviewed in audit | Model and feature-schema versions are recorded with the assessment. |
| LOAN-15 | Customer asks if a model result is a final credit decision | Agent says no unless the authorized lending workflow confirms a recorded decision. |

## 14. Related documents

- `docs/banking_policies/customer-verification-account-access-policy.md` — identity and support access.
- `docs/banking_policies/account-tiers-kyc-policy.md` — synthetic account tiers and KYC handling.
- `docs/banking_policies/fee-schedule.md` — defined synthetic fees.
- `docs/banking_policies/disputes-complaints-escalation-policy.md` — complaint and escalation workflow.
- `docs/api/banking-api-contract.md` — banking API boundary.
- `docs/architecture/data-architecture.md` — source-of-truth and model-artifact boundaries.
- `apps/loan_model/` — training, inference, explainability, and evaluation implementation locations in the locked repository schema.

---

**End of document — RB-POL-LOAN-001, version 0.1**
