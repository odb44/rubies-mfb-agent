# Rubies MFB Customer Support Agent — Documentation Index

**Project:** AI Engineering Capstone — Rubies MFB Customer Support Agent  
**Status:** Design documentation index  
**Last updated:** 2026-10-24

> **Important:** This index tracks the intended documentation structure and the artifacts identified during design. A document listed here is not necessarily present in the repository, approved for implementation, implemented, or tested. Use the status and repository checks below rather than treating this index as proof of completion.

## 1. Project overview

The Rubies MFB Customer Support Agent is a synthetic Nigerian microfinance-bank support system designed to demonstrate:
- Multi-turn support in English and Nigerian Pidgin.
- Retrieval-augmented generation (RAG) with source-backed answers and citations.
- Authorized banking-tool use for account and transaction support.
- Explicit confirmation before sensitive actions.
- Safe handling of uncertainty, privacy boundaries, and human handoff.
- Auditable tool execution and evaluation against scripted scenarios.

All customer records, transactions, and fictional product terms used for the capstone must be synthetic. The system must not present fictional policy material as actual bank policy or legal/regulatory advice.

## 2. Documentation navigation

### 2.1 Architecture

Directory: `docs/architecture/`

| Document | Purpose |
|---|---|
| `architecture-sketch.md` | High-level system overview and major boundaries. |
| `component-architecture.md` | Components, responsibilities, and interactions. |
| `deployment-architecture.md` | Processes, deployment boundaries, and runtime relationships. |
| `data-architecture.md` | Data ownership, persistence, and data flows. |
| `diagrams/system-context.mmd` | System context diagram. |
| `diagrams/component-diagram.mmd` | Component-level diagram. |
| `diagrams/deployment-diagram.mmd` | Deployment view. |
| `diagrams/data-flow-diagram.mmd` | Data-flow view. |

### 2.2 Architecture decision records (ADRs)

Directory: `docs/adr/`

| ADR | Decision area | Current tracking note |
|---|---|---|
| `ADR-001-monorepo-and-service-boundaries.md` | Monorepo and service boundaries. | Approved design decision. |
| `ADR-002-postgresql-persistence.md` | PostgreSQL as banking persistence/source of truth. | Approved design decision. |
| `ADR-003-local-vector-index.md` | Local vector index for initial RAG retrieval. | Approved design decision. |
| `ADR-004-local-model-artifacts.md` | Versioned local loan-model artifacts. | Approved design decision. |
| `ADR-005-fleet-adapter.md` | Fleet integration boundary. | **Deferred** until Fleet requirements are confirmed; do not mark accepted. |
| `ADR-006-mcp-and-authorization.md` | MCP entry point and per-tool authorization. | Approved design decision. |
| `ADR-007-observability-and-evaluation.md` | Observability and evaluation approach. | Approved design decision. |
| `ADR-008-agent-execution-and-confirmation-lifecycle.md` | Agent execution, sensitive actions, and confirmation lifecycle. | Approved design decision. |

Approval here refers to the design direction, not evidence of implementation or successful tests.

### 2.3 Agent and banking flows

Directory: `docs/flows/`

| Flow | Purpose |
|---|---|
| `agent-execution-flow.mmd` | End-to-end agent request and response. |
| `conversation-flow.mmd` | Multi-turn conversation/session behavior. |
| `customer-verification-flow.mmd` | Customer verification and access checks. |
| `banking-tool-execution-flow.mmd` | Authorized banking-tool execution. |
| `confirmation-and-execution-flow.mmd` | Prepare, confirm, execute, and reconcile sensitive actions. |
| `dispute-and-confirmation-flow.mmd` | Dispute creation with explicit customer confirmation. |
| `rag-retrieval-flow.mmd` | Retrieval, grounding, citations, and abstention. |
| `loan-eligibility-flow.mmd` | Loan eligibility assessment. |
| `human-handoff-flow.mmd` | Human escalation and handoff summary. |

The archive inventory reviewed earlier contained the first eight listed flow diagrams except `human-handoff-flow.mmd`; a loose draft was identified separately. Confirm the current repository before assuming the handoff flow has been added.

### 2.4 API and tool contracts

Directory: `docs/api/`

| Document | Purpose |
|---|---|
| `agent-interface.md` | External interface to the agent. |
| `banking-api-contract.md` | Banking API responsibilities and endpoints/contracts. |
| `mcp-tool-contracts.md` | MCP tool contracts and authorization boundary. |

The agreed boundary is that MCP tools call the Banking API; MCP tools do not access the banking database directly. The Banking API and its persistence layer remain responsible for authoritative banking state and backend-enforced access checks.

### 2.5 Security documentation

Directory: `docs/security/`

| Document | Purpose | Artifact tracking |
|---|---|---|
| `security-model.md` | Identity, access control, verification, confirmation, data handling, and failure behavior. | Draft delivered separately; verify repository presence. |
| `threat-model-security-controls.md` | Threat inventory, controls, priorities, and tests. | Draft delivered separately; verify repository presence. |
| `security-test-plan.md` | Security test cases, setup, execution order, and evidence. | Draft delivered separately; verify repository presence. |

These security documents complement, rather than replace, the banking policies and architecture decisions.

### 2.6 Banking policies and customer knowledge

Directory: `docs/banking_policies/`

| Document | Purpose | Artifact tracking |
|---|---|---|
| `customer-verification-account-access-policy.md` | Support verification, identity, access, step-up checks, and privacy boundaries. | Draft delivered separately; verify repository presence. |
| `account-tiers-kyc-policy.md` | Synthetic account tiers, KYC states, restrictions, and tier changes. | Draft delivered separately; verify repository presence. |
| `fee-schedule.md` | Synthetic transfer-fee rules and unspecified charges. | Draft delivered separately; verify repository presence. |
| `transfer-failure-reversal-policy.md` | Transfer statuses, failed transfers, duplicate debits, reversal handling, and unknown outcomes. | Draft delivered separately; verify repository presence. |
| `disputes-complaints-escalation-policy.md` | Dispute creation, confirmation, case status, escalation, and handoff. | Draft delivered separately; verify repository presence. |
| `card-and-ussd-app-policy.md` | Lost/stolen cards, card-block confirmation, USSD/app boundaries, and escalation. | Draft delivered separately; verify repository presence. |
| `loan-products-eligibility-policy.md` | Synthetic loan products and the separation between eligibility, approval, status, and disbursement. | Draft delivered separately; verify repository presence. |
| `fraud-and-account-security-policy.md` | Suspected fraud, account compromise, safe customer guidance, confirmation, audit, and handoff. | Draft delivered separately; verify repository presence. |
| `customer-faq.md` | Customer-facing answers consolidated across the detailed policies. | Draft delivered separately; verify repository presence. |

The fee amounts and loan products in these artifacts are synthetic capstone data. Numeric reversal timelines, unprovided support contacts, unlisted fees, and undefined loan terms must not be invented. For any real-world regulatory statement, use current approved official sources and distinguish it from synthetic demo policy.

### 2.7 Other planned documentation areas

These directories are part of the agreed repository schema; their contents should be inventoried before marking them complete:

- `docs/evaluation/` — evaluation methodology, datasets, metrics, and reporting guidance.
- `docs/observability/` — logging, metrics, tracing, and operational signals.
- `docs/runbooks/` — operational procedures for startup, recovery, incidents, and support.
- `docs/security/` — security design, threat model, and test plan as listed above.

## 3. Key cross-document invariants

Use these as consistency checks when revising or implementing documentation:

1. **Trusted identity:** Customer identity comes from trusted session context; model-supplied identity must never determine which customer record is accessed.
2. **Separation of responsibilities:** The agent proposes actions; backend services enforce identity, authorization, confirmation, and execution.
3. **Authoritative banking state:** PostgreSQL-backed Banking API is the source of truth for banking records. The local vector index is for knowledge retrieval, not banking balances or transaction state.
4. **MCP boundary:** MCP tools invoke the Banking API and do not query the banking database directly.
5. **Sensitive-action confirmation:** Actions such as dispute creation and card blocking require explicit confirmation of the exact proposed action. Confirmation is persistent, expires, is single-use, and is validated/consumed by the backend.
6. **Unknown outcomes:** A timeout does not prove failure. Reconcile against authoritative state before retrying; never invent success, reversal, or case references.
7. **RAG grounding:** Customer-facing policy answers must be grounded in approved, versioned documents with citations where supported. Abstain when evidence is insufficient or conflicting.
8. **Human handoff:** Handoff is required when requested, when the customer is distressed, when controls fail, or when the issue exceeds the available tools.
9. **Secret handling:** Never request or echo passwords, PINs, OTPs, card security codes, or authentication tokens. Redact secrets from logs and summaries.
10. **Synthetic data:** Customer data and fictional fees/products must be clearly synthetic. Do not present them as real-world bank rules.
11. **Design vs implementation:** An approved design does not mean code exists, the repository contains the document, or tests have passed.
12. **Fleet status:** Fleet adapter decision remains deferred until integration requirements are confirmed.

## 4. Artifact status convention

Use one of these labels consistently in documents and tracking:
- **Approved design** — design direction explicitly accepted; implementation may still be outstanding.
- **Design draft** — document has been prepared but is not yet recorded as approved.
- **Deferred** — decision or work is intentionally postponed pending a stated dependency.
- **Implemented** — corresponding implementation exists in the project repository.
- **Tested** — specified tests have been run and evidence is recorded.

Do not label an item implemented or tested based only on a design document. Do not leave an explicitly approved design marked “awaiting approval”; correct the status wording while preserving any outstanding implementation checklist.

## 5. Repository reconciliation checklist

Before using this index as a completion report:

- [ ] Compare each path above with the current working tree.
- [ ] Confirm whether separately delivered Markdown files have been copied into their target repository paths.
- [ ] Confirm whether `docs/README.md` is present in the repository.
- [ ] Confirm whether `docs/flows/human-handoff-flow.mmd` is present and consistent with the handoff policy.
- [ ] Keep ADR-005 deferred unless Fleet requirements have been resolved.
- [ ] Align all approved design status labels and remove stale “awaiting approval” wording where applicable.
- [ ] Ensure dispute confirmation flow agrees with the general confirmation lifecycle.
- [ ] Confirm policy documents use consistent status names, tool names, confirmation behavior, and unknown-outcome handling.
- [ ] Do not mark implementation or testing complete without repository evidence and test results.

## 6. Next documentation work

After reconciling this index with the repository, continue with the remaining documentation categories based on the actual inventory—not by recreating artifacts already present. Likely areas to inspect include evaluation, observability, runbooks, and any missing diagrams or policy documents.

## 7. Scope limitation

This index is a navigation and consistency aid. It does not itself certify that every listed file exists, that the architecture is implemented, that the synthetic policies are legally compliant, or that any test has passed.
