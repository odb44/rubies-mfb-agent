# Rubies MFB Agent Integration Contract

**Status:** integration design draft  
**Purpose:** define the boundary between the real customer-support agent and the evaluation framework. This document is not evidence that the agent has been integrated or evaluated.

## 1. Scope and safety boundary

The evaluation runner executes one case through a suite adapter and records a `CaseExecution`. The adapter must call the real application path and obtain observations from trusted components.

The model's final answer is not proof that a backend action occurred, identity was verified, confirmation was consumed, or an audit event was written. For these properties, use service/database/tool-gateway/audit observations. Do not let the model grade its own behavior.

Until a provider is connected, a case must remain `BLOCKED` or `NEEDS_REVIEW`; do not synthesize observations or report a pass.

## 2. Shared adapter signature

The existing runner contract is:

```python
CaseAdapter = Callable[[str, dict[str, Any]], CaseExecution]
```

The suite names are:
- `rag`
- `tool`
- `safety`

Each adapter factory should return this signature:
- `make_rag_case_adapter(response_provider, assessment_provider=None)`
- `make_tool_scenario_adapter(observation_provider)`
- `make_safety_case_adapter(observation_provider)`

**Integration note:** confirm the exact callable signatures in the checked-in adapter files before wiring them. The safety provider currently expects `(suite, case)`; the RAG provider expects the case; the tool provider's signature should be verified from its implementation. Wrap them in a small registry/closure if their provider signatures differ. The runner-facing adapter signature must stay `(suite, case)`.

## 3. RAG provider contract

For each RAG case, the provider must run the actual customer-support application and return a `RAGObservation`.

Required evidence:
- final answer text;
- retrieved evidence actually supplied to the answer generator, each with source ID, section, and text;
- source IDs and sections actually cited in the answer;
- observed response language;
- whether abstention was expected and whether it occurred, when relevant;
- handoff result, when relevant;
- explicit correctness and grounding assessment from a qualified judge or reviewer, when used.

Do not invent source IDs or mark a citation valid merely because its text looks plausible. Source/section IDs must resolve against the real knowledge-base manifest. A semantic judge must be independently configured and its model/version/prompt should be captured in run metadata where available.

## 4. Tool-scenario provider contract

For each tool scenario, the provider must run the actual agent through the normal application path and return a `ToolScenarioObservation` based on trusted traces.

Required evidence as applicable:
- tool name and redacted argument summary;
- result status from the tool gateway/backend;
- trusted actor/customer identity and target record identity;
- confirmation request and consumption state from the confirmation service/store;
- whether a backend action occurred;
- idempotency key and reconciliation result for timeout/unknown outcomes;
- handoff event;
- audit event evidence.

Never include access tokens, passwords, full account numbers, PINs, OTPs, or unnecessary customer data in evaluation reports. Preserve enough secured evidence to investigate a failure, but keep raw evidence outside broadly accessible reports.

## 5. Safety provider contract

For each safety case, the provider must return a `SafetyObservation` using actual application output plus trusted backend/security observations.

Required evidence as applicable:
- expected trusted customer ID and authenticated session customer ID;
- whether untrusted prompt instructions affected tool use;
- whether sensitive action was required, whether valid confirmation was received, and whether action occurred;
- whether backend outcome was known, and whether a retry happened before reconciliation;
- whether secret material was exposed;
- whether an audit event was recorded;
- whether unsupported deadline claims occurred;
- independently assessed response language;
- whether handoff occurred.

For text-only claims such as “no secret was exposed” or “no unsupported deadline was stated,” use deterministic checks or a documented independent reviewer/judge. The adapter's boolean inputs are evidence supplied by the provider; they are not independently proven by the adapter.

## 6. Provider implementation rules

1. **Use the normal app path.** Do not call internal model helpers if production requests go through a different route.
2. **Use synthetic fixtures only.** All test customers, balances, transactions, loans, and account identifiers must be synthetic.
3. **Reset fixture state.** Each case should start from a known fixture or use isolated data. Avoid test-order dependence.
4. **Make side effects safe.** Use disposable test records and prevent real transfers, card blocks, disputes, or customer notifications.
5. **Use trusted identity.** Never accept the model's customer ID as the authority for the test identity.
6. **Capture provenance.** Record app/build, prompt/tool schema, retrieval index/source manifest, fixture version, evaluator version, and dataset hashes where available.
7. **Redact by default.** Reports must not contain secrets, raw credentials, full account numbers, or unnecessary PII.
8. **Treat timeouts as unknown.** Reconcile the prior operation before retrying.
9. **Fail closed.** Missing required evidence results in `BLOCKED` or `NEEDS_REVIEW`, not a pass.
10. **No silent skips.** Every dataset case must appear in the report, even if execution cannot proceed.

## 7. Suggested integration layout

```text
evaluation/
  evaluators/
    integration/
      __init__.py
      agent_client.py              # Calls the real app using test configuration
      observation_collectors.py    # Reads trusted test/backend/audit evidence
      adapter_registry.py          # Builds runner-facing suite adapters
      fixtures.py                  # Synthetic fixture setup/reset
      README.md
```

This is a proposed layout, not a statement that these files already exist. Keep the integration code separate from pure evaluator logic so adapter unit tests remain fast and deterministic.

## 8. Acceptance checklist

Integration is ready for a first end-to-end evaluation only when all are true:

- [ ] Actual agent entry point and test configuration are identified.
- [ ] All three datasets and schemas load from their repository paths.
- [ ] Every suite has a runner-compatible adapter.
- [ ] Providers execute the real application path.
- [ ] Tool, confirmation, identity, and audit evidence comes from trusted components.
- [ ] All fixture data is synthetic and state reset is deterministic.
- [ ] Sensitive actions cannot affect real customers or systems.
- [ ] Reports are schema-valid and contain no secrets or unnecessary PII.
- [ ] Missing observations are blocked/reviewed rather than passed.
- [ ] At least one integration test per suite demonstrates an observed pass and an observed failure.
- [ ] The 37-case run completes and its result is reviewed; no acceptance claim is made merely because the harness ran.

## 9. Inputs needed to implement the integration

The integration cannot be completed reliably from the evaluator files alone. It needs:
- the agent's actual application entry point or request API;
- agent/tool wiring and tool schemas;
- the retrieval implementation and source manifest;
- test-only backend/service configuration;
- confirmation and audit mechanisms;
- current `pyproject.toml` dependency setup and repository paths.

Once these are available, implement the provider/registry against the real application rather than inventing a placeholder interface.
