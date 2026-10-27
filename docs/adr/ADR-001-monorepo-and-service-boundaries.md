# ADR-001: Monorepo and Service Boundaries

- **Status:** Accepted
- **Decision date:** 2026-10-24
- **Scope:** Repository organization and logical application boundaries

## Context

Rubies MFB Customer Support Agent combines several related capabilities:

- A conversational agent that interprets customer requests and coordinates work.
- Banking APIs and persistence for customer, account, transaction, card, dispute, loan, confirmation, and audit records.
- A knowledge-base pipeline and retrieval components for policy-grounded answers.
- A loan-model training and inference capability.
- An MCP server boundary for exposing approved tools with authorization checks.
- Shared security, schemas, configuration, and observability utilities.
- Evaluation datasets, automated tests, documentation, and synthetic data.

These capabilities belong to one capstone project and need coordinated changes, shared conventions, reproducible local development, and a clear view of the system as a whole. At the same time, combining every responsibility into one tightly coupled application would make security boundaries, testing, and later deployment choices harder to reason about.

## Decision

Organize the project as a **single monorepo** with explicit logical boundaries for applications, shared packages, data, artifacts, evaluation, tests, documentation, scripts, and infrastructure.

The repository will follow the approved directory schema. In particular:

- `apps/agent/` owns conversation handling, orchestration, tool routing, confirmation coordination, and handoff coordination.
- `apps/banking_api/` owns banking-domain APIs and the authoritative banking persistence boundary.
- `apps/loan_model/` owns loan-model training, inference, explainability, and model evaluation.
- `apps/mcp_server/` exposes the approved MCP tool surface and applies its authorization boundary.
- `packages/` contains reusable shared, security, knowledge-base, and observability capabilities.
- `data/` contains synthetic project data, knowledge-source material, and model datasets.
- `artifacts/` contains versioned model artifacts and manifests.
- `evaluation/`, `tests/`, `docs/`, `scripts/`, and `infra/` contain their corresponding project assets.

These are **logical ownership boundaries**, not a requirement that every directory run as a separate process or be independently deployed. Application processes will be separated where appropriate to the responsibility, security boundary, or operational need. The monorepo alone does not dictate deployment topology.

The existing locked directory names and ordering remain the baseline. Changes to that schema require an explicit decision rather than an incidental implementation convenience.

## Rationale

1. **Coordinated development:** API contracts, tool schemas, tests, documentation, and application code can be reviewed together.
2. **Clear ownership:** Each application and package has an identifiable responsibility and intended boundary.
3. **Shared conventions:** Common schemas, exceptions, configuration patterns, and instrumentation can be reused without copying code between repositories.
4. **End-to-end verification:** Integration and regression tests can exercise the agent, banking API, retrieval, model, and MCP boundaries within one versioned project.
5. **Capstone reproducibility:** A reviewer can inspect the architecture, synthetic fixtures, evaluation assets, and implementation history in one repository.
6. **Room to evolve:** Logical boundaries allow a component to be extracted into a separate repository or deployed independently later if a demonstrated need justifies the cost.

## Alternatives considered

### Separate repositories from the outset

**Rejected for the initial capstone.** Multiple repositories would introduce extra coordination, versioning, and contract-management overhead before independent ownership or deployment has been shown to be necessary.

### One tightly coupled application with no explicit boundaries

**Rejected.** This would blur responsibility for banking records, agent orchestration, model inference, retrieval, and MCP authorization. It would also make it harder to test the boundaries independently and to explain which component is trusted to enforce a control.

### Monorepo with a separate process for every directory

**Rejected as a blanket rule.** A directory is not automatically a deployable service. Process boundaries should follow actual runtime, security, and operational requirements rather than mirror the folder tree mechanically.

## Consequences

### Positive

- One versioned source tree for the capstone and its documentation.
- Cross-component changes can be reviewed and tested together.
- Shared security and observability utilities can be maintained consistently.
- The repository layout communicates ownership and supports a staged implementation plan.

### Trade-offs and constraints

- The repository needs clear import and dependency rules to prevent circular dependencies and accidental coupling.
- Shared packages must remain reusable; application-specific business logic should not migrate into them merely for convenience.
- Changes to common schemas can affect multiple applications and should be accompanied by appropriate tests.
- A monorepo does not itself provide runtime isolation, access control, or deployment independence; those controls must be designed and enforced separately.

## Boundary rules

1. **Banking source of truth:** Banking records are owned by the banking API and its PostgreSQL persistence boundary. The agent and model must not bypass that boundary to mutate banking data.
2. **Identity and authorization:** Trusted identity and permissions are enforced by backend security controls. The model may propose an action but is not the authority that grants access.
3. **Tool boundary:** The agent invokes approved tool contracts. The MCP server, where used, applies its own defined authorization checks; it does not replace banking-domain authorization.
4. **Shared packages:** Shared packages provide reusable capabilities and must not become a second home for application-specific workflows.
5. **Knowledge and model artifacts:** Knowledge indexes and model artifacts are versioned assets, not authoritative banking records.
6. **Deployment flexibility:** Deployment placement, container topology, and cloud hosting are intentionally not decided by this ADR.

## Intentionally deferred

This ADR does not decide:

- The exact Docker or deployment topology for local development, staging, or production.
- Whether every application boundary will run as a separate process in every environment.
- Cloud hosting, production networking, or production secret-management services.
- The detailed Fleet integration or registration process.
- The implementation details of each application or shared package.

Those decisions belong in their relevant architecture documents and ADRs and must remain consistent with the locked repository schema.

## Acceptance criteria

This decision is considered implemented when:

- The repository follows the approved directory schema without unapproved renaming or reordering.
- Each application and shared package has a documented responsibility.
- Banking persistence and authorization boundaries are enforced by backend code rather than model instructions alone.
- Tests and documentation are kept alongside the components they describe.
- Any later proposal to change repository or service boundaries is recorded explicitly and reviewed against this ADR.
