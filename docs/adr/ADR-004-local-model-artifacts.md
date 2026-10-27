# ADR-004: Local Model Artifacts

- **Status:** Accepted
- **Decision date:** 2026-10-24
- **Scope:** Storage, versioning, and promotion of loan-model artifacts

## Context

The Rubies MFB Customer Support Agent includes a loan-model capability for eligibility-related assessment and explanations. The capstone may train and evaluate a model using synthetic data. Model outputs must be traceable to a specific model version and must not silently become authoritative banking records or bypass the bank's defined lending policy.

The locked repository schema places model datasets under `data/model/` and versioned model artifacts under `artifacts/loan_model/`, with supporting training, inference, explainability, and evaluation code under `apps/loan_model/`.

## Decision

Store trained loan-model artifacts locally in a **versioned artifact directory**, following the approved repository structure:

- `artifacts/loan_model/versions/` contains distinct, immutable model versions.
- `artifacts/loan_model/manifests/` contains metadata describing each version.
- `data/model/training/`, `data/model/validation/`, and `data/model/test/` contain the corresponding synthetic datasets or controlled dataset references.
- `apps/loan_model/training/`, `apps/loan_model/inference/`, `apps/loan_model/explainability/`, and `apps/loan_model/evaluation/` contain the code responsible for training, serving predictions, generating explanations, and evaluating models.

Each model version must have a manifest identifying, at minimum, its version identifier, artifact location, training-data version or fingerprint, feature/schema version, training configuration, evaluation results, creation timestamp, and intended use. The manifest should also record the code or commit reference where practical. Secrets and unnecessary personal information must not be embedded in artifacts or manifests.

Model artifacts are **versioned decision-support assets**, not the source of truth for customers, accounts, transactions, loan application status, or final approval records. The loan model may provide a prediction and an explanation; the application must apply the approved business policy and authorization rules before communicating an eligibility result or taking any consequential action.

## Rationale

1. **Reproducibility:** Versioned artifacts and manifests make it possible to identify how a model was trained and evaluated.
2. **Local-first capstone:** Local storage avoids requiring a model registry or hosted artifact platform before the need is established.
3. **Rollback:** Keeping distinct versions allows the application to return to a previously validated model if a newer version regresses.
4. **Evaluation discipline:** A model version can be promoted only when its evaluation evidence is recorded and reviewed.
5. **Clear authority:** Separating model predictions from banking records reduces the risk that a prediction is mistaken for a confirmed loan decision.

## Alternatives considered

### Overwrite one model file for every training run

**Rejected.** Overwriting removes the ability to compare versions, identify the model used for a past result, or roll back reliably.

### Store model binaries in PostgreSQL

**Not selected.** The relational database remains the authoritative store for structured banking records and workflow state. Large model artifacts have a different lifecycle and are more naturally managed as versioned files for this local-first capstone.

### Introduce a hosted model registry immediately

**Deferred.** A registry could improve team collaboration, lineage, promotion, and access management at larger scale. The initial capstone can establish these controls with local versioned artifacts and manifests. A registry can be considered later if operational needs justify it.

## Version lifecycle

1. **Prepare data:** Use the designated training, validation, and test data areas. Record dataset versions or stable fingerprints and document the feature schema.
2. **Train:** Produce a candidate artifact without overwriting an existing version.
3. **Evaluate:** Measure the agreed performance and safety criteria, including relevant subgroup behavior where the dataset supports it. Keep test-set use separate from iterative tuning.
4. **Explain:** Verify that the inference and explanation outputs are understandable and consistent with the features used.
5. **Record provenance:** Write a manifest that links the candidate artifact to its data, feature schema, training configuration, and evaluation results.
6. **Review and promote:** Promote a candidate only after the required evaluation checks pass and the version is explicitly designated as approved for use.
7. **Serve with identity:** Inference responses must identify the model version used and distinguish predictions from policy outcomes.
8. **Rollback:** If monitoring or regression evaluation shows unacceptable behavior, switch back to a previously approved version and record the change.
9. **Retain evidence:** Preserve enough metadata and evaluation output to reproduce or investigate a result. Retention and cleanup rules will be specified in operational design.

A model artifact should be treated as immutable after promotion. Changes to training data, feature definitions, training configuration, or model parameters create a new version rather than silently changing an existing one.

## Runtime and safety rules

- The inference component loads only an explicitly configured, approved model version; it must not automatically choose an arbitrary file found in the artifact directory.
- Model input must be validated against the declared feature schema.
- Missing, invalid, or out-of-range inputs must be handled explicitly; they must not be silently converted into a confident eligibility result.
- Responses must distinguish a model prediction, its explanation, and any business-policy decision.
- A prediction must not directly create or update authoritative loan records. Such changes go through the banking API and its authorization and workflow controls.
- If the model is unavailable or returns an invalid result, the system must follow a documented fallback or handoff path rather than fabricate a result.
- Model artifacts and manifests must be protected from unauthorized modification.
- Synthetic data is used for the capstone; any future use of real customer data would require a separate privacy, governance, and security review.

## Consequences

### Positive

- Model versions are traceable and can be compared.
- Failed releases can be rolled back without retraining the prior model.
- Evaluation evidence travels with the artifact version.
- The application can explain which model produced a prediction.

### Trade-offs and constraints

- Local artifact directories need access controls and backup practices appropriate to the environment.
- Version and manifest conventions must be maintained consistently.
- Manual promotion is less automated than a dedicated model registry.
- Model quality and fairness cannot be inferred from the existence of a manifest; the evaluation methodology and results still require review.

## Intentionally deferred

This ADR does not select the model family, feature set, training framework, model file format, exact performance thresholds, registry technology, deployment topology, or production model-monitoring service. These are implementation and evaluation decisions. The chosen approach must continue to provide immutable versions, provenance, validation evidence, explicit promotion, and rollback.

## Acceptance criteria

This decision is considered implemented when:

- Model versions are stored under `artifacts/loan_model/versions/` and are not silently overwritten.
- Every candidate or promoted version has a manifest under `artifacts/loan_model/manifests/`.
- Manifests identify the model, data, feature schema, training configuration, and evaluation evidence.
- Inference loads an explicitly approved version and reports its version identifier.
- Tests distinguish model predictions from authoritative loan status and policy decisions.
- Promotion and rollback are documented and testable.
- Unauthorized changes to model artifacts are prevented or detected.
