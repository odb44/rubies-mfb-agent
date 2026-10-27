# RAG adapter artifact (v0.1)

## Target repository paths
- `evaluation/evaluators/adapters/rag_adapter.py`
- `evaluation/evaluators/tests/test_rag_adapter.py`

## Responsibilities
- Validate RAG observation structure.
- Check cited source IDs and section labels against the evidence actually retrieved.
- Check explicitly specified required concepts and expected source coverage.
- Check abstention behaviour and language matching when the case supplies expectations.
- Accept explicit correctness, grounding, safety, and handoff assessments.
- Mark missing semantic assessments as `NEEDS_REVIEW` rather than guessing.
- Mark fabricated/unretrieved citations and explicit safety failures as critical.

## Deliberate limitation
This artifact does not call the agent, retrieve documents, or use an LLM-as-judge.
A `response_provider` must call the real agent and return a `RAGObservation`.
An optional `assessment_provider` can supply calibrated correctness/grounding
and safety/handoff assessments. Do not treat fixture tests as evidence of real
agent quality.

## Integration
The returned adapter can be passed to `run_evaluation` under the `rag` key:
```python
adapters = {"rag": make_rag_case_adapter(response_provider, assessment_provider)}
```
The adapter returns `CaseExecution` from `evaluator_runner.py`. Keep both files
available on the Python import path (the repository's test configuration may
use package imports instead).

## Dependency
Uses `jsonschema` only indirectly through the evaluator runner; this module
itself uses the Python standard library.


# Tool-scenario adapter artifact (v0.1)

## Target repository paths
- `evaluation/evaluators/adapters/tool_scenario_adapter.py`
- `evaluation/evaluators/tests/test_tool_scenario_adapter.py`

## Responsibilities
- Check expected and forbidden tool calls.
- Check session identity and cross-customer isolation evidence.
- Check confirmation evidence for protected actions.
- Check timeout reconciliation, handoff, backend action and required audit events.
- Mark cross-customer access, forbidden calls and confirmation bypasses as critical.
- Redact raw arguments and customer identifiers from the report-facing tool trace.

## Boundary
This module consumes an observed trace; it does not call banking APIs or prove
backend enforcement on its own. The integration harness must capture trustworthy
backend/tool evidence. Never rely only on the assistant's final prose.

## Runner integration
```python
adapters = {
    "tool": make_tool_scenario_adapter(observation_provider),
}
```
The observation provider receives a case and returns `ToolScenarioObservation`.


# Safety Evaluation Adapter

**Status:** implementation draft; unit tests cover evaluator logic only.

## Repository destinations
- `safety_adapter.py` → `evaluation/evaluators/adapters/safety_adapter.py`
- `test_safety_adapter.py` → `evaluation/evaluators/tests/test_safety_adapter.py`
- Merge this README content into the existing `evaluation/evaluators/adapters/README.md`; do not overwrite existing adapter documentation.

## Purpose
Evaluates observed safety outcomes for the Rubies MFB customer-support agent. It covers prompt-injection resistance, identity binding, confirmation gating, unknown backend outcomes, retry-before-reconciliation, unsupported deadline claims, secret exposure, audit evidence, language matching, and cross-customer successful actions.

## Important boundary
This is an **observation-based evaluator**, not a security control. It does not execute or authorize banking tools, verify authentication, infer truth from the final response, or independently prove backend enforcement. Integrate it with trusted session, service, tool, confirmation, and audit observations. Missing evidence should remain `NEEDS_REVIEW`, not be treated as a pass.

## Runner integration
`make_safety_case_adapter(observation_provider)` returns a runner-compatible adapter with the same `(suite, case)` signature and `CaseExecution` output contract used by the RAG and tool adapters. The provider receives `(suite, case)` and must execute the case against the real agent, returning a `SafetyObservation` built from trusted observations. Do not let the model generate the evidence used to grade itself.

## Current limitations / integration checks
- The case dataset's actual field names and expected-behavior structure must be mapped and verified during integration.
- Prompt-injection and unsupported-deadline checks rely on explicit observation flags; this module does not semantically judge free text.
- Language matching relies on an upstream language assessment.
- Confirmation correctness depends on trusted confirmation-store/backend evidence.
- Cross-customer checks need reliable actor/target IDs and tool result statuses.
- The current logic uses case text heuristics to infer whether confirmation is relevant unless `expected_behavior.confirmation_required` is supplied.
- Unit tests do not prove the live agent is safe; add integration and adversarial regression tests.

