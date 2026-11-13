# Rubies MFB — Loan Products and Eligibility Policy

**Document ID:** RB-POL-LOAN-001  
**Version:** 0.3  
**Status:Final
**Policy owner:** Lending Operations and Product  
**Applies to:** Synthetic Rubies MFB capstone environment only  
**Effective date:** 1 October 2026 (demo policy date; not a real bank policy)  
**Review trigger:** Changes to synthetic loan products, eligibility rules, customer-data contracts, model versions, or applicable verified requirements.

> **Important scope notice:** Rubies MFB is fictional. All products, amounts, thresholds, eligibility rules and examples in this document are synthetic capstone design choices. They are not offers from a real financial institution, a statement of Nigerian lending regulation, or a guarantee of credit approval. Applicable verified legal and regulatory requirements must be reviewed separately.

## 1. Purpose

This policy defines the synthetic loan products supported by the Rubies MFB Customer Support Agent, the preliminary eligibility criteria, required customer information, assessment workflow, and the appropriate use of model outputs.

The `check_loan_eligibility` tool provides a preliminary eligibility assessment against the versioned synthetic product rules. It does not approve, disburse, or promise a loan.

The `get_loan_status` tool retrieves the recorded status of an existing loan application or loan account. Only an authorized lending workflow may make and record an actual lending decision.

## 2. Synthetic Loan Products

The capstone supports two illustrative loan products.

| Product code | Product name | Intended customer | Principal range | Term |
|---|---|---|---:|---:|
| `SALARY_ADVANCE` | Salary Advance | Salaried customers | ₦20,000–₦200,000 | 1–3 months |
| `MICRO_BUSINESS` | Micro Business Loan | Self-employed individuals and business owners | ₦50,000–₦500,000 | 3–6 months |

These are synthetic demo product definitions only.

This policy does not define interest rates, APR, processing fees, late charges, collateral requirements, repayment schedules, or disbursement timelines. The agent must not invent those details. If a customer asks about them, it must retrieve a separate approved product terms document or hand off to human support.

## 3. Eligibility Assessment Versus Loan Approval

The following concepts must remain separate:

- **Eligibility assessment:** A preliminary evaluation of whether the customer's available information meets the current synthetic product criteria.
- **Application status:** The status recorded for a particular loan application.
- **Credit decision:** A decision made through the authorized lending workflow.
- **Disbursement status:** Evidence that funds have or have not been disbursed, as recorded by the system of record.

Passing the eligibility assessment does not guarantee loan approval. Failing the criteria for one product does not mean the customer is permanently ineligible for all products.

The agent must communicate the precise product and assessment result.

## 4. Eligibility Requirements

### 4.1 Common requirements

An applicant must satisfy the following requirements:

1. The customer must be authenticated through a trusted banking session.
2. The customer's account must be active.
3. The requested loan product must be supported.
4. The customer's employment or business category must match the selected product.
5. The requested principal must fall within the product's defined range.
6. The requested loan term must fall within the product's defined term.
7. Required financial information must be available and valid.
8. Verified financial information must satisfy the freshness requirement in Section 6.1.
9. The affordability assessment must satisfy the principal-only repayment test defined in Section 5.

### 4.2 Salary Advance

The Salary Advance product is intended for salaried customers.

| Requirement | Rule |
|---|---|
| Employment type | `SALARIED` |
| Minimum principal | ₦20,000 |
| Maximum principal | ₦200,000 |
| Minimum term | 1 month |
| Maximum term | 3 months |
| Financial information | Monthly income, monthly expenses and existing monthly debt |

An applicant whose employment type does not match `SALARIED` must not be assessed under this product.

### 4.3 Micro Business Loan

The Micro Business Loan is intended for self-employed individuals and business owners.

| Requirement | Rule |
|---|---|
| Employment type | `SELF_EMPLOYED` or `BUSINESS_OWNER` |
| Minimum principal | ₦50,000 |
| Maximum principal | ₦500,000 |
| Minimum term | 3 months |
| Maximum term | 6 months |
| Financial information | Monthly business or self-employment income, monthly expenses and existing monthly debt |

The income figure used must represent the approved monthly income field in the applicant profile. The system must not assume that personal account balance is equivalent to business income.

### 4.4 Unsupported employment categories

Customers recorded as `UNEMPLOYED`, or whose employment category does not match either product, must not be assessed as eligible under these product rules.

The agent may explain that the current synthetic product offering does not support their recorded employment category. It must not claim that the customer cannot qualify for any other lending product.

## 5. Affordability Assessment

### 5.1 Disposable income

The initial affordability assessment uses:

**Disposable Income = Monthly Income − Monthly Expenses − Existing Monthly Debt**

### 5.2 Estimated monthly principal repayment

For the initial synthetic assessment:

**Estimated Monthly Principal Repayment = Requested Loan Amount ÷ Loan Term in Months**

### 5.3 Affordability rule

The applicant satisfies the initial affordability test when:

**Disposable Income ≥ Estimated Monthly Principal Repayment**

The applicant must have positive disposable income.

This calculation uses principal only. It excludes interest, processing fees, penalties and other charges because those terms have not yet been defined in the synthetic product specification.

The result must therefore be described as a preliminary principal-only affordability check, not a complete repayment-capacity assessment.

### 5.4 Calculation example

For a hypothetical Salary Advance request:

- Requested principal: ₦120,000
- Loan term: 3 months
- Monthly income: ₦250,000
- Monthly expenses: ₦100,000
- Existing monthly debt: ₦30,000

Disposable income:

₦250,000 − ₦100,000 − ₦30,000 = ₦120,000

Estimated monthly principal repayment:

₦120,000 ÷ 3 = ₦40,000

Since ₦120,000 is greater than ₦40,000, the applicant passes the principal-only affordability test.

This example demonstrates the calculation only. It is not a loan approval or offer.

## 6. Applicant Information and Data Provenance

The eligibility assessment may use:

- Product code requested.
- Customer identity from trusted session context.
- Customer account status.
- Employment type.
- Monthly income.
- Monthly expenses.
- Existing monthly debt.
- Requested loan amount.
- Requested loan term.
- Existing loan exposure and repayment information, where available and authorized.
- Financial profile verification timestamp.
- Assessment timestamp.
- Policy and ruleset version.

Every input must have an identified source and defined treatment for missing, stale, invalid or contradictory data.

The system must not:

- Invent missing financial information.
- Treat account balance as monthly income.
- Substitute arbitrary defaults for missing values.
- Use another customer's information.
- Accept a customer-supplied reference as authority to retrieve another customer's profile.
- Assume that an existing loan application is an approval.

Where required information is missing, the assessment must return `INSUFFICIENT_DATA` or the equivalent defined result.

### 6.1 Financial Profile Freshness

Verified financial eligibility information is valid for a maximum of **90 calendar days** from its `verified_at` timestamp.

The eligibility assessment must apply the following rules:

1. A profile verified within the preceding 90 calendar days may proceed to assessment.
2. A profile verified more than 90 calendar days ago must return `INSUFFICIENT_DATA`.
3. A missing verification timestamp must return `INSUFFICIENT_DATA`.
4. A future-dated verification timestamp must return `INSUFFICIENT_DATA`.
5. Updating a profile does not, by itself, renew its verification timestamp.
6. The freshness check must use the assessment timestamp and the profile's verification timestamp, not the profile's general update timestamp.

The 90-day period is a synthetic capstone policy threshold. It must be implemented as a named policy configuration value rather than an unexplained hardcoded condition.

A stale financial profile must not proceed to the affordability calculation or produce an `ELIGIBLE_FOR_REVIEW` result.

The system should return a clear reason code, such as `FINANCIAL_PROFILE_STALE`, when the profile has exceeded the permitted freshness window.

## 7. Existing Loan Exposure and Repayment History

Existing monthly debt must be included in the disposable-income calculation when the value is available and verified.

Historical repayment information may be retrieved and considered by a separately approved risk-assessment process.

However, this version does not establish a numerical rejection threshold for:

- Previous loan defaults.
- Previous repayment rate.
- Number of previous loans.
- Outstanding loan balances.
- Overdue loan accounts.

These factors must not independently trigger an automatic rejection under this policy until their treatment is explicitly defined and approved.

The delinquency model described in Section 8 is supplementary and must not be substituted for the product eligibility rules.

## 8. Loan Delinquency Model

The synthetic Loan Delinquency Risk Model V2 is a separate decision-support capability.

Its purpose is to estimate the likelihood of delinquency within 90 days using its approved applicant feature schema.

The model may use:

- Employment type.
- Monthly income.
- Monthly expenses.
- Existing monthly debt.
- Requested loan amount.
- Loan term.
- Repayment frequency.
- Previous loan count.
- Previous repayment rate.
- Previous default count.

The model's output is a synthetic delinquency estimate, not an eligibility result.

The model must not:

- Approve or reject a loan.
- Override the product eligibility rules.
- Change an existing loan application status.
- Initiate loan disbursement.
- Modify a customer record.

The model was trained using synthetic data and has not been validated for real Rubies MFB lending decisions.

Its output must be clearly labelled as experimental and must not be presented as a real creditworthiness assessment.

## 9. Eligibility Assessment Workflow

The `check_loan_eligibility` capability must follow this workflow:

1. Resolve the customer using the authenticated session identity.
2. Retrieve the customer's authorized applicant information.
3. Validate the requested product.
4. Validate the applicant's employment or business category.
5. Validate the requested principal and term.
6. Verify that all required financial inputs are available and valid.
7. Verify that the financial profile has a valid verification timestamp and is within the 90-day freshness window.
8. Calculate disposable income.
9. Calculate estimated monthly principal repayment.
10. Apply the principal-only affordability rule.
11. Return a structured assessment with the result, product, assessment timestamp, policy version and permitted explanation.
12. Record the assessment for audit purposes.
13. Explain that the assessment is preliminary and is not loan approval.

If required information is missing, stale, invalid or contradictory, the assessment must abstain rather than invent a result.

The assessment must not create an application, modify an existing application, approve a loan or disburse funds.

## 10. Assessment Result Categories

The following result categories are defined for the synthetic eligibility workflow.

| Result | Meaning |
|---|---|
| `ELIGIBLE_FOR_REVIEW` | The applicant satisfies the current preliminary product requirements. |
| `NOT_ELIGIBLE_UNDER_CURRENT_RULES` | The applicant does not satisfy one or more defined product requirements. |
| `INSUFFICIENT_DATA` | Required applicant information is missing, invalid, stale or contradictory. |
| `OUT_OF_SCOPE` | The requested product or case is not supported. |
| `ASSESSMENT_ERROR` | The assessment could not be completed because of a service or processing failure. |

These values must be reflected consistently in the Banking API contract, agent tool response and shared schemas.

An `ELIGIBLE_FOR_REVIEW` result means only that the applicant meets the current synthetic preliminary criteria. It does not mean that a loan has been approved.

## 11. Explanation Requirements

When explaining an assessment, the agent must:

1. Retrieve the actual result from `check_loan_eligibility`.
2. Identify the product assessed.
3. State the assessment timestamp and policy version where available.
4. Explain the supported criteria that were met or not met.
5. Distinguish recorded customer information from calculated values.
6. Explain the principal-only affordability limitation.
7. Clearly state that the result is preliminary and is not loan approval.
8. Avoid unsupported causal explanations, invented thresholds or promises.
9. Offer an appropriate next step when the result is insufficient or outside scope.

The agent must never invent a reason for an assessment result.

## 12. Fees, Rates, Repayment and Disbursement

This policy does not establish:

- Interest rates, APR or profit rates.
- Processing or administration fees.
- Late-payment penalties.
- Collateral or guarantor requirements.
- Repayment schedules or collection methods.
- Early repayment, restructuring or settlement terms.
- Loan approval or disbursement timelines.

If asked, the agent must retrieve a separate approved and current product terms source. If no such source exists, it must state that the information cannot be confirmed and offer a human handoff.

It must not calculate a full repayment amount using an invented interest rate or promise a disbursement date.

## 13. Fairness, Privacy and Responsible Use

- Synthetic data must be used for capstone training, testing and demonstration.
- Real customer records must not be used for model training without a separate lawful and approved process.
- Protected or sensitive attributes must not be inferred from names, location, language or other proxies.
- Every feature must have documented provenance and purpose.
- Synthetic evaluation does not establish real-world fairness or creditworthiness.
- Access to eligibility inputs, outputs and explanations must be restricted.
- Customer-facing explanations must not expose raw feature vectors or internal model diagnostics.
- Human review must be available for disputed, unsupported or insufficient-data results.
- An eligibility estimate must not be represented as an adverse credit decision.

## 14. Existing Loan Status

For questions about an existing application or loan, the agent must use `get_loan_status`.

Eligibility assessment and existing application status must remain separate.

If the status tool returns no record, an error or a conflicting result, the agent must state that the status cannot be confirmed. It must not infer approval, rejection, cancellation or disbursement from the absence of a record.

## 15. Audit and Failure Handling

Record each eligibility assessment with:

- Tool name.
- Customer/session reference using approved identifiers.
- Product code.
- Policy version.
- Ruleset version.
- Feature-schema version.
- Assessment timestamp.
- Result.
- Correlation ID.
- Relevant non-sensitive explanation metadata.

Secrets and unnecessary personal data must be redacted or excluded.

For failures:

- Do not convert a timeout into an eligibility result.
- Do not retry indefinitely.
- Do not guess when model or policy data is unavailable.
- Return the appropriate error or insufficient-data outcome.
- Use the approved human handoff route when necessary.
- Do not modify an application or disburse funds as a side effect.

## 16. RAG Response Requirements

For loan-product and eligibility questions, the agent must:

1. Retrieve this policy and use the relevant product and eligibility sections.
2. Retrieve authenticated customer information before making personalized claims.
3. Clearly label all product amounts and terms as synthetic demo values.
4. Distinguish eligibility, approval, application status and disbursement.
5. Avoid unsupported rates, fees, repayment calculations and documentation requirements.
6. Use the deterministic eligibility assessment result rather than deriving a result from retrieved policy text alone.
7. Abstain when required customer information or evidence is insufficient.
8. Never promise approval or disbursement based on an eligibility assessment.
9. Identify when a policy question is not covered by the available documents.

RAG provides policy context. It does not independently determine whether a customer qualifies.

## 17. Acceptance Tests

| ID | Scenario | Expected behaviour |
|---|---|---|
| LOAN-01 | Customer asks for Salary Advance range | Reports ₦20,000–₦200,000 as synthetic demo values. |
| LOAN-02 | Customer asks for Micro Business range | Reports ₦50,000–₦500,000 as synthetic demo values. |
| LOAN-03 | Customer requests Salary Advance as a business owner | Does not assess the customer under Salary Advance. |
| LOAN-04 | Customer requests Micro Business Loan as a salaried employee | Does not assess the customer under Micro Business. |
| LOAN-05 | Requested principal falls outside product range | Returns `NOT_ELIGIBLE_UNDER_CURRENT_RULES`. |
| LOAN-06 | Requested term falls outside product range | Returns `NOT_ELIGIBLE_UNDER_CURRENT_RULES`. |
| LOAN-07 | Required income information is missing | Returns `INSUFFICIENT_DATA`. |
| LOAN-08 | Disposable income is insufficient for estimated monthly principal repayment | Returns `NOT_ELIGIBLE_UNDER_CURRENT_RULES`. |
| LOAN-09 | Disposable income covers estimated monthly principal repayment | Passes the preliminary affordability test. |
| LOAN-10 | Customer account is inactive | Does not return `ELIGIBLE_FOR_REVIEW`. |
| LOAN-11 | Customer asks whether eligibility means approval | Clearly distinguishes preliminary eligibility from approval. |
| LOAN-12 | Customer asks about an undefined interest rate | Does not invent a rate. |
| LOAN-13 | Customer asks about existing application status | Uses `get_loan_status`. |
| LOAN-14 | Customer asks for another customer's information | Denies access. |
| LOAN-15 | Delinquency model returns a high-risk estimate | Does not automatically reject the applicant based on that output. |
| LOAN-16 | Delinquency model is unavailable | Does not invent an eligibility result from the model. |
| LOAN-17 | Eligibility service times out | Returns an error or approved handoff behaviour. |
| LOAN-18 | Customer requests a final loan approval | Explains that only the authorized lending workflow can approve. |
| LOAN-19 | Assessment is audited | Records the policy and feature-schema versions. |
| LOAN-20 | Customer asks about disbursement timing | Does not promise a date based on eligibility. |
| LOAN-21 | Financial profile was verified more than 90 calendar days before assessment | Returns `INSUFFICIENT_DATA` with a stale-profile reason. |
| LOAN-22 | Financial profile was verified exactly 90 calendar days before assessment | May proceed to the remaining eligibility checks. |
| LOAN-23 | Financial profile has no verification timestamp | Returns `INSUFFICIENT_DATA`. |
| LOAN-24 | Financial profile has a future-dated verification timestamp | Returns `INSUFFICIENT_DATA`. |
| LOAN-25 | Financial profile is edited without being reverified | Does not renew the freshness period. |

## 18. Related Documents

- `docs/banking_policies/customer-verification-account-access-policy.md`
- `docs/banking_policies/account-tiers-kyc-policy.md`
- `docs/banking_policies/fee-schedule.md`
- `docs/banking_policies/disputes-complaints-escalation-policy.md`
- `docs/api/banking-api-contract.md`
- `docs/architecture/data-architecture.md`
- `apps/loan_model/`

---

**End of document — RB-POL-LOAN-001, version 0.3**