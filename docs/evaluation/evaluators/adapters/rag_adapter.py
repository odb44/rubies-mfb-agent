"""RAG evaluation adapter for the Rubies MFB Customer Support Agent.

This module evaluates an already-produced answer and its retrieval evidence.
It does not call an LLM or retrieve documents itself. Connect it to the real
agent by supplying a response provider that returns a ``RAGObservation``.

Deterministic checks cover required concepts, citation validity/relevance,
abstention, language matching, and safety parity. Semantic correctness is
intentionally represented as an explicit assessment input rather than guessed
from string similarity.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievedEvidence:
    """One retrieved source chunk made available to the answer generator."""

    source_id: str
    section: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RAGObservation:
    """Observed output from a RAG-enabled agent for one evaluation case."""

    answer: str
    retrieved_evidence: tuple[RetrievedEvidence, ...] = ()
    cited_sources: tuple[str, ...] = ()
    cited_sections: tuple[str, ...] = ()
    # Human/judge assessment, if available. Must be explicit; never inferred
    # solely from string overlap by this adapter.
    correctness_score: int | None = None  # 0 incorrect, 1 partial, 2 correct
    grounding_score: int | None = None    # 0 unsupported, 1 partially supported, 2 supported
    abstention_expected: bool | None = None
    abstention_observed: bool | None = None
    language_observed: str | None = None  # "en" or "pcm"
    safety_result: bool | None = None
    handoff_observed: bool | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RAGCaseResult:
    """RAG case evaluation in a runner-friendly, serialisable form."""

    case_id: str
    outcome: str
    assertions: tuple[dict[str, Any], ...]
    scores: Mapping[str, float]
    language: str | None
    expected_response_language: str | None
    language_match_pass: bool | None
    content_correctness_pass: bool | None
    citation_pass: bool | None
    safety_parity_pass: bool | None
    handoff_pass: bool | None
    citations: tuple[str, ...]
    critical_failure: bool
    critical_failures: tuple[dict[str, Any], ...]
    block_reason: str | None = None
    reviewer_notes: str | None = None


class RAGAdapterError(ValueError):
    """Raised when an evaluation case or observation is malformed."""


ResponseProvider = Callable[[Mapping[str, Any]], RAGObservation]
AssessmentProvider = Callable[[Mapping[str, Any], RAGObservation], Mapping[str, Any]]


def _first_nonempty(case: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = case.get(key)
        if value not in (None, ""):
            return value
    return None


def _case_id(case: Mapping[str, Any]) -> str:
    value = _first_nonempty(case, ("case_id", "id"))
    if not isinstance(value, str) or not value.strip():
        raise RAGAdapterError("RAG case must contain a non-empty 'case_id' or 'id'.")
    return value.strip()


def _normalise_language(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"pcm", "pidgin", "nigerian pidgin", "pidgin english"}:
        return "pcm"
    if lowered in {"en", "english"}:
        return "en"
    return None


def _expected_language(case: Mapping[str, Any]) -> str | None:
    # Dataset fields have changed across drafts; support explicit aliases only.
    value = _first_nonempty(
        case,
        ("expected_response_language", "expected_language", "language_expected"),
    )
    return _normalise_language(value)


def _observed_language(case: Mapping[str, Any], observation: RAGObservation) -> str | None:
    return _normalise_language(
        observation.language_observed
        or _first_nonempty(case, ("detected_language", "customer_language", "language"))
    )


def _required_terms(case: Mapping[str, Any]) -> list[str]:
    value = _first_nonempty(case, ("required_concepts", "required_terms", "must_include"))
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RAGAdapterError("Required concepts must be a list of strings.")
    return [item.strip() for item in value if item.strip()]


def _expected_sources(case: Mapping[str, Any]) -> set[str]:
    value = _first_nonempty(case, ("expected_sources", "expected_citations", "source_ids"))
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RAGAdapterError("Expected sources must be a list of strings.")
    return {item.strip() for item in value if item.strip()}


def _is_abstention_case(case: Mapping[str, Any]) -> bool:
    explicit = case.get("abstention_expected")
    if isinstance(explicit, bool):
        return explicit
    case_type = str(_first_nonempty(case, ("case_type", "expected_behavior", "category")) or "").lower()
    if any(token in case_type for token in ("abstain", "insufficient", "conflict", "unknown")):
        return True
    return bool(case.get("must_abstain", False))


def _abstention_lexicon(language: str | None) -> tuple[str, ...]:
    common = (
        "i don't have enough information",
        "i do not have enough information",
        "i can't confirm",
        "i cannot confirm",
        "i'm unable to verify",
        "i am unable to verify",
        "i don't want to guess",
        "i cannot determine",
        "i can't determine",
        "let me connect you to a support representative",
        "i'll connect you to a support representative",
    )
    pidgin = (
        "i no get enough information",
        "i no fit confirm",
        "make i no guess",
        "i no wan guess",
        "i no fit verify",
        "make i connect you to support",
        "i go connect you to support",
    )
    return common + (pidgin if language == "pcm" else ())


def _contains_abstention(answer: str, language: str | None) -> bool:
    lowered = re.sub(r"\s+", " ", answer.lower()).strip()
    return any(phrase in lowered for phrase in _abstention_lexicon(language))


def _evidence_source_ids(observation: RAGObservation) -> set[str]:
    return {item.source_id for item in observation.retrieved_evidence if item.source_id.strip()}


def _evidence_sections(observation: RAGObservation) -> set[str]:
    return {item.section for item in observation.retrieved_evidence if item.section.strip()}


def _assertion(assertion_id: str, passed: bool | None, details: str) -> dict[str, Any]:
    return {
        "assertion_id": assertion_id,
        "passed": passed,
        "notes": details,
    }


def evaluate_rag_case(
    case: Mapping[str, Any],
    observation: RAGObservation,
    *,
    assessment: Mapping[str, Any] | None = None,
) -> RAGCaseResult:
    """Evaluate one case against its reference metadata and observed RAG output.

    ``assessment`` may provide explicit fields: ``correctness_score`` (0..2),
    ``grounding_score`` (0..2), ``safety_pass`` (bool), and ``handoff_pass``
    (bool). These can later be populated by a calibrated judge or human review.
    Missing semantic assessments lead to NEEDS_REVIEW, not an invented score.
    """
    case_id = _case_id(case)
    if not isinstance(observation, RAGObservation):
        raise RAGAdapterError("observation must be a RAGObservation.")
    if not isinstance(observation.answer, str):
        raise RAGAdapterError(f"{case_id}: answer must be a string.")

    expected_language = _expected_language(case)
    observed_language = _observed_language(case, observation)
    language_match: bool | None = None
    if expected_language is not None and observed_language is not None:
        language_match = expected_language == observed_language

    required_terms = _required_terms(case)
    answer_lower = observation.answer.casefold()
    missing_terms = [term for term in required_terms if term.casefold() not in answer_lower]
    required_terms_pass = not missing_terms if required_terms else None

    cited_sources = set(observation.cited_sources)
    cited_sections = set(observation.cited_sections)
    retrieved_sources = _evidence_source_ids(observation)
    retrieved_sections = _evidence_sections(observation)
    expected_sources = _expected_sources(case)

    citation_ids_valid = cited_sources.issubset(retrieved_sources)
    citation_sections_valid = cited_sections.issubset(retrieved_sections)
    expected_sources_present = expected_sources.issubset(cited_sources) if expected_sources else None
    citation_pass = citation_ids_valid and citation_sections_valid
    if expected_sources_present is False:
        citation_pass = False

    expected_abstention = _is_abstention_case(case)
    abstention_observed = (
        observation.abstention_observed
        if observation.abstention_observed is not None
        else _contains_abstention(observation.answer, observed_language)
    )
    abstention_pass = (abstention_observed == expected_abstention)

    assessment = dict(assessment or {})
    correctness_score = assessment.get("correctness_score", observation.correctness_score)
    grounding_score = assessment.get("grounding_score", observation.grounding_score)
    safety_pass = assessment.get("safety_pass", observation.safety_result)
    handoff_pass = assessment.get("handoff_pass")
    if handoff_pass is None and observation.handoff_observed is not None:
        handoff_expected = case.get("handoff_expected")
        handoff_pass = (
            observation.handoff_observed == handoff_expected
            if isinstance(handoff_expected, bool)
            else observation.handoff_observed
        )

    if correctness_score is not None and (
        not isinstance(correctness_score, int) or correctness_score not in (0, 1, 2)
    ):
        raise RAGAdapterError(f"{case_id}: correctness_score must be 0, 1, or 2.")
    if grounding_score is not None and (
        not isinstance(grounding_score, int) or grounding_score not in (0, 1, 2)
    ):
        raise RAGAdapterError(f"{case_id}: grounding_score must be 0, 1, or 2.")
    for field_name, value in (("safety_pass", safety_pass), ("handoff_pass", handoff_pass)):
        if value is not None and not isinstance(value, bool):
            raise RAGAdapterError(f"{case_id}: {field_name} must be a boolean or None.")

    assertions = [
        _assertion("RAG-CITATION-IDS-VALID", citation_ids_valid,
                   "Every cited source must be present in the retrieved evidence."),
        _assertion("RAG-CITATION-SECTIONS-VALID", citation_sections_valid,
                   "Every cited section must be present in the retrieved evidence."),
        _assertion("RAG-EXPECTED-SOURCES", expected_sources_present,
                   "Expected source coverage is checked when the case defines expected sources."),
        _assertion("RAG-REQUIRED-CONCEPTS", required_terms_pass,
                   "Required concepts are checked literally; semantic equivalence requires assessment."),
        _assertion("RAG-ABSTENTION", abstention_pass,
                   f"Expected abstention={expected_abstention}; observed={abstention_observed}."),
        _assertion("RAG-LANGUAGE-MATCH", language_match,
                   "Language matching is checked when expected and observed language are known."),
        _assertion("RAG-CONTENT-CORRECTNESS", correctness_score == 2 if correctness_score is not None else None,
                   "Correctness requires an explicit calibrated assessment."),
        _assertion("RAG-GROUNDING", grounding_score == 2 if grounding_score is not None else None,
                   "Grounding requires an explicit assessment of answer against retrieved evidence."),
        _assertion("RAG-SAFETY", safety_pass,
                   "Safety assessment must be provided by deterministic checks or a calibrated reviewer."),
        _assertion("RAG-HANDOFF", handoff_pass,
                   "Handoff is checked when the case defines an expectation or assessment."),
    ]

    critical_failures: list[dict[str, Any]] = []
    # Deterministic citation fabrication is a critical failure.
    if not citation_ids_valid or not citation_sections_valid:
        critical_failures.append({
            "failure_id": f"CF-{case_id}-FABRICATED-CITATION",
            "category": "fabricated_or_unretrieved_citation",
            "evidence_ref": None,
            "status": "OPEN",
            "notes": "A cited source or section was not present in retrieved evidence.",
        })
    if safety_pass is False:
        critical_failures.append({
            "failure_id": f"CF-{case_id}-RAG-SAFETY",
            "category": "rag_safety_failure",
            "evidence_ref": None,
            "status": "OPEN",
            "notes": "The explicit safety assessment failed.",
        })

    content_correctness_pass = correctness_score == 2 if correctness_score is not None else None
    if critical_failures:
        outcome = "FAILED"
    elif (
        required_terms_pass is False
        or citation_pass is False
        or abstention_pass is False
        or language_match is False
        or content_correctness_pass is False
        or (grounding_score is not None and grounding_score < 2)
        or safety_pass is False
        or handoff_pass is False
    ):
        outcome = "FAILED"
    elif (
        content_correctness_pass is None
        or grounding_score is None
        or safety_pass is None
        or language_match is None and expected_language is not None
        or handoff_pass is None and isinstance(case.get("handoff_expected"), bool)
    ):
        outcome = "NEEDS_REVIEW"
    else:
        outcome = "PASSED"

    scores = {
        "correctness": float(correctness_score) if correctness_score is not None else None,
        "grounding": float(grounding_score) if grounding_score is not None else None,
        "citation_validity": 1.0 if citation_pass else 0.0,
        "required_concepts": 1.0 if required_terms_pass is True else (0.0 if required_terms_pass is False else None),
        "abstention": 1.0 if abstention_pass else 0.0,
    }
    return RAGCaseResult(
        case_id=case_id,
        outcome=outcome,
        assertions=tuple(assertions),
        scores=scores,
        language=observed_language,
        expected_response_language=expected_language,
        language_match_pass=language_match,
        content_correctness_pass=content_correctness_pass,
        citation_pass=citation_pass,
        safety_parity_pass=safety_pass,
        handoff_pass=handoff_pass,
        citations=tuple(sorted(cited_sources | cited_sections)),
        critical_failure=bool(critical_failures),
        critical_failures=tuple(critical_failures),
        block_reason=None,
        reviewer_notes=observation.notes,
    )


def make_rag_case_adapter(
    response_provider: ResponseProvider,
    assessment_provider: AssessmentProvider | None = None,
) -> Callable[[str, dict[str, Any]], Any]:
    """Create an evaluator-runner-compatible adapter for suite name ``rag``."""
    # Import lazily to keep this module independently testable.
    from evaluator_runner import CaseExecution

    def adapter(suite: str, case: dict[str, Any]) -> CaseExecution:
        if suite != "rag":
            raise RAGAdapterError(f"RAG adapter cannot handle suite {suite!r}.")
        observation = response_provider(case)
        assessment = assessment_provider(case, observation) if assessment_provider else None
        result = evaluate_rag_case(case, observation, assessment=assessment)
        return CaseExecution(
            outcome=result.outcome,
            assertions=result.assertions,
            critical_failure=result.critical_failure,
            critical_failures=result.critical_failures,
            scores=result.scores,
            language=result.language,
            expected_response_language=result.expected_response_language,
            language_match_pass=result.language_match_pass,
            content_correctness_pass=result.content_correctness_pass,
            citation_pass=result.citation_pass,
            safety_parity_pass=result.safety_parity_pass,
            handoff_pass=result.handoff_pass,
            citations=result.citations,
            block_reason=result.block_reason,
            reviewer_notes=result.reviewer_notes,
        )

    return adapter
