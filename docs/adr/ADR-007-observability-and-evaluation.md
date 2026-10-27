# ADR-007: Observability and Evaluation

- **Status:** Accepted
- **Decision date:** 2026-10-24
- **Scope:** Operational visibility, tool-call auditability, and systematic quality evaluation

## Context

The Rubies MFB Customer Support Agent combines language-model orchestration, retrieval-augmented generation, banking tools, confirmation workflows, loan-model inference, and human handoff. A user-facing answer can fail in several different ways: retrieval may provide weak evidence, a tool may reject a request, authorization may deny access, a confirmation may expire, a backend call may time out, or the agent may produce an unsupported answer.

The project therefore needs a consistent way to understand what happened during a request and a repeatable way to measure whether changes improve or regress system behavior. Operational telemetry and audit records serve related but distinct purposes: telemetry supports diagnosis and performance monitoring, while audit records support accountability for sensitive actions.

## Decision

Use the shared `packages/observability/` boundary for reusable logging, metrics, tracing, and instrumentation conventions. Apply those conventions across the agent, banking API, MCP server, knowledge-base pipeline, and loan-model components where relevant.

Maintain automated evaluation assets under the locked `evaluation/` structure and tests under `tests/`. Evaluation must cover retrieval quality, tool behavior, safety controls, and end-to-end customer-support scenarios. The system must not rely on informal manual testing alone for regression detection.

Observability and evaluation must follow the data-minimization and security requirements defined in the architecture and related ADRs. Logs, traces, metrics, and reports must not become an alternate source of banking truth or a repository for unnecessary sensitive customer data.

## Observability conventions

### Structured logs

Application logs should be structured and consistently identify the component, event type, severity, timestamp, and correlation/request identifier where available. Tool invocation logs should include the tool name, a safe representation of inputs, result category, and duration where appropriate.

Sensitive values must be excluded or redacted. Do not log passwords, authentication factors, access tokens, full card credentials, or unnecessary account and transaction details. Logging a tool call does not replace the authoritative audit event required for a sensitive banking action.

### Correlation and tracing

Requests should carry a correlation identifier across the agent, tool router, MCP boundary, banking API, and relevant downstream operations. Where distributed tracing is used, spans should make the sequence and duration of significant operations visible without recording sensitive payloads.

A trace should help answer questions such as:

- Did retrieval occur, and which knowledge version was used?
- Which tool was invoked, and what outcome category did it return?
- Was a confirmation required, issued, approved, expired, or rejected?
- Did the banking API complete the operation, reject it, or return an indeterminate result?
- Was a human handoff initiated?

### Metrics

Capture a focused set of operational metrics, including:

- Request volume and response latency.
- Error and timeout rates by component and tool.
- Tool invocation success, rejection, and indeterminate-outcome rates.
- Confirmation creation, approval, expiry, and rejection counts.
- Retrieval latency and no-evidence/low-confidence rates.
- Handoff frequency and handoff completion outcomes where available.
- Evaluation pass rates and regression counts.
- Loan-model inference failures and model-version usage.

Metrics should use bounded labels. Do not use customer IDs, account numbers, transaction references, or free-form user messages as metric labels.

### Audit records

Authoritative audit records for sensitive actions remain part of the banking persistence boundary. They should record the action, trusted actor/session reference, authorization and confirmation outcome, result category, timestamp, and correlation identifier as appropriate. Audit data must be access-controlled and protected from unauthorized modification.

Operational logs and traces may link to audit events using a correlation or event identifier, but must not replace the audit record or duplicate unnecessary sensitive fields.

## Evaluation strategy

Evaluation assets are stored in the locked repository paths:

- `evaluation/datasets/rag_questions/`
- `evaluation/datasets/tool_scenarios/`
- `evaluation/datasets/safety_cases/`
- `evaluation/evaluators/`
- `evaluation/metrics/`
- `evaluation/regression/`
- `evaluation/reports/`

The initial evaluation scope follows the capstone requirements:

1. **RAG evaluation:** At least 20–30 questions covering approved policy documents, with expected supporting sources or sections. Evaluate retrieval relevance, citation support, and appropriate abstention when evidence is missing or conflicting.
2. **Tool scenarios:** Ten scripted scenarios covering tool selection, input validation, authorization, tool outcomes, confirmation requirements, and user-facing explanation.
3. **Safety cases:** At least five cases covering attacks or unsafe requests, including cross-customer data access, requests to bypass confirmation, prompt injection in retrieved content, and pressure to disclose protected information.
4. **End-to-end flows:** Exercise the agreed demo scenarios, including fee questions, a double-debit dispute, a missing card, loan eligibility, a failed transfer in Nigerian Pidgin, unauthorized access to another person's balance, and an upset customer requesting a human.
5. **Regression checks:** Re-run relevant evaluation cases after changes to prompts, tool schemas, policies, retrieval configuration, model artifacts, or orchestration behavior.

The exact scoring thresholds and grading methodology will be defined in the evaluation plan. A passing aggregate score must not hide a critical safety failure: authorization bypass, confirmation bypass, cross-customer disclosure, or fabricated completion of a consequential action must be treated as release-blocking failures.

## Change and release discipline

Changes that can alter user-visible behavior or safety controls should be evaluated against the relevant regression set. At minimum, this includes changes to:

- System and tool-policy prompts.
- Tool schemas, handlers, or authorization rules.
- Confirmation lifecycle logic.
- Knowledge documents, chunking, embeddings, or index versions.
- Loan-model artifacts or feature schemas.
- Agent orchestration and response construction.

Evaluation reports should identify the code/version under test, dataset or knowledge-index version where relevant, metrics, known failures, and the decision to accept or reject the change. Do not promote a change solely because it improves average answer quality if it weakens a critical safety control.

## Failure handling and alerting

Failures should be classified so the system can distinguish validation or authorization denials from infrastructure errors, model failures, retrieval gaps, and indeterminate banking-operation outcomes. User-facing responses must remain honest about what is known.

For example, a timeout after a state-changing request must not be logged or presented as definite failure unless the operation's outcome has been reconciled. The system should preserve the correlation identifier and use the approved idempotency/reconciliation workflow.

The initial capstone may use local logs, metrics, traces, and evaluation reports. A production observability platform, alert routing, service-level objectives, and on-call process are outside this ADR's initial scope.

## Alternatives considered

### Rely on manual testing and console output

**Rejected as the sole approach.** Manual testing is useful during development but is not sufficient to detect repeatable regressions across retrieval, tools, safety controls, and end-to-end flows.

### Put all telemetry into the banking audit table

**Rejected.** Operational telemetry and authoritative audit records have different purposes, retention needs, access patterns, and data-minimization requirements. They should be linked where useful, not conflated.

### Add a hosted observability platform immediately

**Deferred.** A hosted platform may become useful for production operations, but the capstone can establish consistent instrumentation and evaluation contracts without selecting a specific external service at this stage.

### Use one aggregate score as the release criterion

**Rejected.** An aggregate score can mask critical safety failures. Mandatory safety invariants must be evaluated independently and treated as release gates.

## Consequences

### Positive

- Failures can be traced across component boundaries.
- Tool behavior and sensitive action outcomes can be investigated without relying on conversation text alone.
- Retrieval, tool selection, and safety behavior can be evaluated systematically.
- Regression checks provide evidence for changes to prompts, tools, knowledge, and models.
- The project can start locally and adopt a production platform later without changing its basic instrumentation principles.

### Trade-offs and constraints

- Instrumentation must be added consistently across components.
- Evaluation datasets need maintenance as policies and tool contracts evolve.
- Sensitive telemetry requires redaction, access control, and retention decisions.
- Automated evaluation cannot replace human review of high-risk or ambiguous behavior.

## Intentionally deferred

This ADR does not select a logging, metrics, or tracing vendor; define production service-level objectives; establish alert thresholds; specify retention periods; or prescribe an on-call process. It also does not finalize numeric quality thresholds for every evaluation metric. These decisions will be made as the implementation and operating environment become clearer.

## Acceptance criteria

This decision is considered implemented when:

- Components emit consistent structured logs with correlation identifiers where applicable.
- Tool invocations and sensitive banking actions are auditable without exposing unnecessary sensitive data.
- Metrics cover latency, errors, tool outcomes, confirmation lifecycle, retrieval behavior, and handoff.
- The required RAG, tool, and safety evaluation datasets are present and executable.
- Regression evaluation runs for changes that can affect user-visible behavior or safety.
- Critical safety failures cannot be masked by aggregate evaluation scores.
- Evaluation reports identify the versions and datasets used and document known failures and release decisions.
