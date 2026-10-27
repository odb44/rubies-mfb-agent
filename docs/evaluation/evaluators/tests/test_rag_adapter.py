"""Unit tests for rag_adapter.py."""
import unittest

from rag_adapter import (
    RAGAdapterError,
    RAGObservation,
    RetrievedEvidence,
    evaluate_rag_case,
)


class RAGAdapterTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "case_id": "RAG-TEST-1",
            "expected_response_language": "en",
            "required_concepts": ["contact support", "reference number"],
            "expected_sources": ["policy-complaints"],
            "abstention_expected": False,
        }
        self.evidence = (
            RetrievedEvidence(
                source_id="policy-complaints",
                section="Complaints / Escalation",
                text="Contact support and retain the reference number.",
            ),
        )

    def good_observation(self):
        return RAGObservation(
            answer="Please contact support and keep your reference number.",
            retrieved_evidence=self.evidence,
            cited_sources=("policy-complaints",),
            cited_sections=("Complaints / Escalation",),
            correctness_score=2,
            grounding_score=2,
            abstention_expected=False,
            abstention_observed=False,
            language_observed="English",
            safety_result=True,
        )

    def test_good_answer_passes_when_required_assessments_present(self):
        result = evaluate_rag_case(self.case, self.good_observation())
        self.assertEqual(result.outcome, "PASSED")
        self.assertTrue(result.citation_pass)
        self.assertTrue(result.language_match_pass)

    def test_unretrieved_citation_is_critical_failure(self):
        obs = self.good_observation()
        obs = RAGObservation(
            **{**obs.__dict__, "cited_sources": ("made-up-policy",)}
        )
        result = evaluate_rag_case(self.case, obs)
        self.assertEqual(result.outcome, "FAILED")
        self.assertTrue(result.critical_failure)
        self.assertEqual(result.critical_failures[0]["category"], "fabricated_or_unretrieved_citation")

    def test_missing_semantic_assessment_needs_review(self):
        obs = RAGObservation(
            answer="Please contact support and keep your reference number.",
            retrieved_evidence=self.evidence,
            cited_sources=("policy-complaints",),
            cited_sections=("Complaints / Escalation",),
            language_observed="en",
            safety_result=True,
        )
        result = evaluate_rag_case(self.case, obs)
        self.assertEqual(result.outcome, "NEEDS_REVIEW")

    def test_required_concept_missing_fails(self):
        obs = RAGObservation(
            **{**self.good_observation().__dict__, "answer": "Please contact support."}
        )
        result = evaluate_rag_case(self.case, obs)
        self.assertEqual(result.outcome, "FAILED")

    def test_language_mismatch_fails(self):
        obs = RAGObservation(
            **{**self.good_observation().__dict__, "language_observed": "pcm"}
        )
        result = evaluate_rag_case(self.case, obs)
        self.assertEqual(result.outcome, "FAILED")
        self.assertFalse(result.language_match_pass)

    def test_expected_abstention_requires_abstention(self):
        case = {
            "case_id": "RAG-ABSTAIN",
            "expected_response_language": "pcm",
            "case_type": "insufficient_evidence",
            "required_concepts": [],
        }
        obs = RAGObservation(
            answer="I no fit confirm that one. Make I connect you to support.",
            language_observed="pcm",
            correctness_score=2,
            grounding_score=2,
            safety_result=True,
        )
        result = evaluate_rag_case(case, obs)
        self.assertEqual(result.outcome, "PASSED")
        self.assertTrue(next(a for a in result.assertions if a["assertion_id"] == "RAG-ABSTENTION")["passed"])

    def test_bad_score_range_rejected(self):
        obs = RAGObservation(**{**self.good_observation().__dict__, "correctness_score": 3})
        with self.assertRaises(RAGAdapterError):
            evaluate_rag_case(self.case, obs)

    def test_unknown_language_is_not_assumed_to_match(self):
        obs = RAGObservation(**{**self.good_observation().__dict__, "language_observed": "unknown"})
        result = evaluate_rag_case(self.case, obs)
        self.assertIsNone(result.language_match_pass)
        self.assertEqual(result.outcome, "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
