"""Unit tests for tool_scenario_adapter.py."""

import unittest

from tool_scenario_adapter import (
    ObservedToolCall,
    ToolScenarioObservation,
    evaluate_tool_scenario,
)


class ToolScenarioAdapterTests(unittest.TestCase):
    def test_expected_tool_and_identity_pass(self):
        case = {
            "scenario_id": "TS-1",
            "expected_tools": ["get_balance"],
            "expected_customer_id": "C-001",
            "confirmation_required": False,
        }
        observation = ToolScenarioObservation(
            tool_calls=(ObservedToolCall("get_balance", {}, "success"),),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
            confirmation_requested=False,
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertEqual(result.outcome, "PASSED")
        self.assertFalse(result.critical_failure)

    def test_cross_customer_success_is_critical(self):
        case = {
            "scenario_id": "TS-CROSS",
            "expected_tools": ["get_balance"],
            "expected_customer_id": "C-001",
            "confirmation_required": False,
        }
        observation = ToolScenarioObservation(
            tool_calls=(
                ObservedToolCall(
                    "get_balance",
                    {},
                    "success",
                    actor_customer_id="C-001",
                    target_customer_id="C-002",
                ),
            ),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertEqual(result.outcome, "FAILED")
        self.assertTrue(result.critical_failure)

    def test_confirmation_bypass_is_critical(self):
        case = {
            "scenario_id": "TS-CONFIRM",
            "expected_tools": ["block_card"],
            "expected_customer_id": "C-001",
            "confirmation_required": True,
        }
        observation = ToolScenarioObservation(
            tool_calls=(ObservedToolCall("block_card", {}, "success"),),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
            confirmation_requested=False,
            confirmation_consumed=False,
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertEqual(result.outcome, "FAILED")
        self.assertTrue(result.critical_failure)

    def test_forbidden_tool_invocation_is_critical(self):
        case = {
            "scenario_id": "TS-FORBIDDEN",
            "expected_tools": ["get_balance"],
            "forbidden_tools": ["block_card"],
            "expected_customer_id": "C-001",
            "confirmation_required": False,
        }
        observation = ToolScenarioObservation(
            tool_calls=(
                ObservedToolCall("get_balance", {}, "success"),
                ObservedToolCall("block_card", {}, "success"),
            ),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertEqual(result.outcome, "FAILED")
        self.assertTrue(result.critical_failure)

    def test_timeout_requires_reconciliation(self):
        case = {
            "scenario_id": "TS-TIMEOUT",
            "expected_tools": ["get_transaction_status"],
            "expected_customer_id": "C-001",
            "confirmation_required": False,
            "must_not_execute_on_timeout": True,
            "must_reconcile_timeout": True,
        }
        observation = ToolScenarioObservation(
            tool_calls=(
                ObservedToolCall(
                    "get_transaction_status",
                    {},
                    "timeout",
                    timed_out=True,
                ),
            ),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
            backend_action_occurred=False,
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertEqual(result.outcome, "FAILED")  # no reconciliation evidence
        self.assertFalse(result.critical_failure)

    def test_required_audit_event(self):
        case = {
            "scenario_id": "TS-AUDIT",
            "expected_tools": ["open_dispute"],
            "expected_customer_id": "C-001",
            "confirmation_required": False,
            "required_audit_events": ["tool_call"],
        }
        observation = ToolScenarioObservation(
            tool_calls=(ObservedToolCall("open_dispute", {}, "success"),),
            expected_customer_id="C-001",
            authenticated_customer_id="C-001",
            audit_events=({"event_type": "tool_call"},),
        )
        result = evaluate_tool_scenario(case, observation)
        self.assertFalse(result.critical_failure)
        self.assertTrue(
            next(a for a in result.assertions if a["assertion_id"] == "TOOL-AUDIT")["passed"]
        )


if __name__ == "__main__":
    unittest.main()
