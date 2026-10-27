# Customer Verification and Account-Access Policy

- **Document ID:** RUBIES-POL-SEC-001
- **Status:** Design draft
- **Owner:** Project owner / Banking policy owner (to be assigned)
- **Applies to:** Rubies MFB Customer Support Agent, Agent API, tool router, MCP server, Banking API/services, and human-handoff preparation
- **Related documents:** `docs/security/security-model.md`; `docs/security/threat-model-security-controls.md`; `docs/security/security-test-plan.md`; `docs/api/agent-interface.md`; `docs/api/banking-api-contract.md`; `docs/api/mcp-tool-contracts.md`
- **Implementation status:** Policy requirements for the synthetic capstone; not evidence of regulatory approval or implemented controls

## 1. Purpose

This policy defines how the Rubies MFB Customer Support Agent establishes the customer context for a support conversation, decides whether customer-specific information may be disclosed, and determines when additional verification is required before a sensitive action.

This is a **support-access policy**, not a complete customer-onboarding, anti-money-laundering, or regulatory Customer Due Diligence (CDD) procedure. The fictional bank's onboarding and account-tier rules must be documented separately and maintained against applicable Central Bank of Nigeria (CBN) requirements.

## 2. Policy principles

1. Verify identity through the configured trusted authentication and verification process; do not infer identity from conversational claims.
2. Treat identity verification and authorization as separate checks.
3. Derive customer identity from trusted server-side session context, never from model-generated arguments or free text.
4. Apply least privilege and customer/resource ownership checks to every customer-scoped operation.
5. Require explicit confirmation for confirmation-required state changes, in addition to any required verification.
6. Never request or expose a customer's PIN, password, one-time passcode, full card security code, or access token in the chat.
7. If verification or authorization cannot be established, do not disclose protected data or perform the operation.
8. Minimize personal and financial information in prompts, logs, tool outputs, and human handoffs.
9. Do not reveal whether another person's account or record exists when the requester is not authorized to access it.
10. If the system cannot determine an operation's outcome, communicate uncertainty and follow the reconciliation procedure; do not guess.

## 3. Scope and terminology

- **Trusted session context:** Server-established context that identifies the authenticated principal and any customer binding.
- **Customer verification:** The configured process used to establish that the person using the support channel is entitled to the customer context being accessed.
- **Step-up verification:** An additional verification procedure required for a sensitive operation or elevated risk.
- **Authorization:** The backend decision that a verified principal may perform a particular operation on a particular resource.
- **Confirmation:** The customer's explicit approval of the exact pending action presented to them. Confirmation does not replace verification or authorization.
- **Customer-scoped data:** Balance, mini-statement, transaction status, card information, dispute information, loan information, and other data linked to a customer.
- **Sensitive action:** An operation that changes customer or banking state or has a material security impact.

## 4. Establishing the customer context

1. The Agent API must obtain the authenticated principal and customer binding from the configured trusted authentication/session mechanism.
2. The system must not establish or change the customer binding based only on a name, phone number, account number, customer ID, BVN, NIN, or other identifier typed into a conversation.
3. Where a customer identifier is supplied to help locate a record, it may be treated only as a lookup input to an approved verification flow. It is not proof of identity or authority.
4. If the trusted context is missing, invalid, expired, or inconsistent, the system must deny protected customer-specific operations and direct the user to the approved authentication or recovery path.
5. The system must not fall back to a customer identity inferred from conversation history, a retrieved document, or model-generated tool arguments.
6. The Banking API/service must enforce the customer binding and resource ownership independently of the model's interpretation and the MCP caller's request.

## 5. Access classes and required checks

The following table defines the initial support-agent policy. The exact verification levels and factors must be mapped to the chosen authentication mechanism and approved operational policy before implementation.

| Access class | Examples | Minimum policy requirement |
|---|---|---|
| General public information | Published fees, product descriptions, general process FAQs | No customer-specific identity verification; answer from approved, current knowledge sources |
| Customer-specific read | `get_balance`, `get_mini_statement`, `get_transaction_status`, `get_loan_status` | Valid trusted customer context, required verification state, resource ownership, and authorization |
| Customer-specific assessment | `check_loan_eligibility` | Valid trusted customer context and applicable permission/verification checks; clearly explain that an eligibility assessment is not a loan approval |
| Sensitive state change | `open_dispute`, `block_card` | Trusted customer context, applicable verification/step-up checks, authorization, persistent pending action, explicit confirmation, and backend enforcement |
| Human handoff | `handoff_to_human` | Follow the channel's identity and privacy rules; include only the minimum information needed; do not imply that handoff succeeded without a confirmed result |
| Verification or recovery | `verify_customer` | Use only the configured verification workflow; do not disclose protected account data before the required checks pass |

No tool may bypass these requirements because the user is distressed, claims urgency, asks in Pidgin, or instructs the agent to ignore policy. The language used by the customer does not change the access rules.

## 6. Step-up verification

The implementation must define a policy mapping each sensitive operation to its required verification level. When step-up verification is required:

1. Explain the need for additional verification without disclosing sensitive internal risk signals.
2. Direct the customer to the approved verification process.
3. Validate the result in the backend or designated security component.
4. Do not ask the customer to paste a PIN, password, one-time passcode, or other secret into the conversational model.
5. Do not treat a successful step-up check as permission to access unrelated customer records or perform unrelated actions.
6. Recheck relevant verification status when a pending action is approved if the policy requires current verification.
7. Apply configured attempt limits, expiry, recovery, and lockout controls. Numeric values must be established in the implementation policy rather than guessed in this document.

If verification fails or cannot be completed, do not disclose protected data or proceed with the sensitive action. Provide the approved recovery path without revealing whether an identifier or verification factor matched a customer record.

## 7. Resource ownership and authorization

Before any customer-scoped read or state change, the Banking API/service must verify that:

- The request has a valid trusted principal/customer context.
- The target customer and resource are within that context or explicitly accessible under a separately approved authorization rule.
- The principal has permission for the requested operation.
- Any required verification and action-specific checks are satisfied.
- The request complies with applicable business rules.

The agent and MCP server must not be treated as substitutes for backend authorization. A resource identifier supplied by a caller is a selector, not proof of ownership.

### Cross-customer requests

If a user asks for a relative's, neighbour's, colleague's, or other customer's account information, the agent must not disclose it or switch context based on the request. It should briefly explain that it can only help with accounts available to the authenticated customer and offer an approved alternative, such as asking the other customer to sign in themselves.

Responses must not disclose whether the other person's account or record exists.

## 8. Confirmation-required actions

For `open_dispute` and `block_card`, and any other operation later classified as confirmation-required:

1. Validate the request and all required inputs.
2. Check trusted identity, ownership, permissions, and required verification.
3. Create a persistent pending action bound to the customer/session and canonical action details.
4. Present the customer with a clear summary of the exact action and return a confirmation reference.
5. Wait for explicit approval. Questions, ambiguity, silence, or a decline are not approval.
6. On approval, validate the confirmation reference, binding, expiry, action details, current permissions, and required verification.
7. Atomically consume the confirmation and execute through the Banking API with the approved idempotency mechanism.
8. Record the outcome. If it is unknown, reconcile before retrying or claiming success/failure.

Approval for one action cannot be reused for another action or for materially changed details. A confirmation reference is not an authentication credential and must not override identity or authorization checks.

## 9. Tiered KYC and regulatory boundary

Rubies MFB is fictional and its account-tier configuration is synthetic. This support policy does not create regulatory KYC tiers or invent account limits.

For any separate account-opening or tiered-KYC policy:

- Use the applicable current CBN rules and circulars, including the Central Bank of Nigeria (Customer Due Diligence) Regulations, 2023 and relevant subsequent guidance.
- Validate the current requirements for BVN/NIN, electronic identity verification, account tier, customer type, and any applicable transaction or balance limits before defining synthetic policy values.
- Do not use placeholder BVN/NIN values as if they were validated identifiers.
- Do not continue onboarding where required identity checks fail or source identity details conflict; follow the approved regulatory workflow.
- Maintain a source register with the official instrument, publication/effective date where available, review date, and the policy statements it supports.
- Have any claim of regulatory compliance reviewed by a qualified compliance/legal owner before the project represents it as compliant.

The CBN's official Customer Due Diligence Regulations, 2023 cover identification, verification, ongoing due diligence, risk-based CDD, tiered KYC, enhanced CDD, and record keeping. CBN guidance on BVN and tiered accounts/wallets has also been updated over time. Therefore, values copied from an older tier table must not be assumed current without checking the relevant instrument.

## 10. Privacy, confidentiality, and data minimization

- Disclose customer information only to an authorized customer or through a legally approved exception handled by the bank's established process.
- Return only the fields required to answer the customer's request.
- Do not reveal full account identifiers, full card credentials, verification secrets, or unrelated customer data.
- Do not put passwords, tokens, PINs, one-time passcodes, or full card security codes into logs, prompts, or handoff summaries.
- Apply the approved redaction and access-control rules to tool-call logs and audit events.
- Include only necessary, verified context in human handoff.
- Treat information returned by retrieval as evidence for an answer, not as authority to disclose protected records or bypass access controls.

## 11. Failure and escalation behavior

| Situation | Required behavior |
|---|---|
| Trusted identity absent or invalid | Deny protected access and direct the customer to authentication/recovery |
| Verification fails or expires | Do not disclose protected data or perform the protected action; provide the approved recovery path |
| Resource ownership or permission check fails | Deny without confirming another customer's record exists |
| Verification service unavailable | Fail closed for operations requiring verification; do not invent a successful result |
| Confirmation is missing, expired, reused, or mismatched | Do not execute; restart the appropriate preparation/confirmation flow |
| Customer requests an unauthorized third-party lookup | Explain the access boundary without revealing record existence |
| Agent is uncertain or customer asks for a human | Use the approved handoff path, minimize the payload, and report only the confirmed handoff status |
| State-changing operation times out | Report an unknown outcome until backend reconciliation provides evidence |
| Policy or source documents conflict | Do not guess; abstain or hand off for review and record the conflict |

## 12. Audit and review

For relevant verification and access decisions, record a protected, redacted audit event containing the decision category, tool/operation, timestamp, correlation identifier, and outcome. Do not record verification secrets or unnecessary raw personal data.

The operational policy owner must review this policy when relevant CBN instruments, authentication mechanisms, supported channels, or tool permissions change. The review date and resulting changes should be recorded in the policy source register.

## 13. Implementation acceptance checks

Before this policy is treated as implemented, tests must demonstrate that:

- Customer context comes from a trusted server-side source.
- User- or model-supplied identifiers cannot switch customer context.
- Every customer-scoped tool enforces resource ownership and authorization.
- The required verification level is enforced for each operation.
- Confirmation-required actions cannot execute before explicit approval.
- Verification, authorization, confirmation, and privacy failures fail safely.
- Responses do not disclose whether unauthorized third-party records exist.
- Secrets are not exposed in prompts, logs, tool results, or handoff payloads.
- The source register for any tiered-KYC policy is current and reviewed.

## 14. Official reference sources

These official CBN sources inform the regulatory boundary described above. They should be checked again before implementation because rules and guidance may change.

1. **Central Bank of Nigeria (Customer Due Diligence) Regulations, 2023** — official PDF: https://www.cbn.gov.ng/Out/2023/CCD/CBN%20Customer%20Due%20diligence%20Reg.%202023-combined.pdf
2. **CBN BVN information and related regulatory updates** — https://www.cbn.gov.ng/PaymentsSystem/BVN.html
3. **CBN Customer Bill of Rights and Duties** — https://www.cbn.gov.ng/FinInc/FinLit/BillOfRights.html
4. **CBN Consumer Protection Framework** — official PDF: https://www.cbn.gov.ng/out/2016/cfpd/consumer%20protection%20framework%20%28final%29.pdf

This policy is a design artifact for a fictional capstone system and is not legal advice or a certification of regulatory compliance.
