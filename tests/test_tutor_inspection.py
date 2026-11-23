"""Offline tests for the live inspection regression's independent assertions."""

from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_tutor_inspection import InspectionBackend, model_state_preserved, trial_assertions
from mission_evals.skill_bridge import text_result


class InspectionAssertionsTests(unittest.TestCase):
    def setUp(self):
        self.state = {"ans_preserved": True, "learner_variables_preserved": True, "temporaries": []}
        self.progress = {"completedStepIds": ["t01", "t02", "t03", "t04"], "currentStepId": "t05"}

    def grade(self, case="ans", *, before="pass", after="pass", message=">>> CORRECT! <<<", errors=0):
        model_state = {"block_parameters": [], "model_parameters": {}, "models": "fixture"}
        return trial_assertions(case, {"status": before, "state": model_state},
                                {"status": after, "state": model_state}, self.state, message,
                                self.progress, True, errors)

    def test_model_parameter_change_fails_even_when_task_still_passes(self):
        before = {"status": "pass", "state": {"block_parameters": [], "models": "fixture",
                                              "model_parameters": {"StopTime": "10"}}}
        after = {"status": "pass", "state": {"block_parameters": [], "models": "fixture",
                                             "model_parameters": {"StopTime": "20"}}}
        grades = trial_assertions("ans", before, after, self.state, ">>> CORRECT! <<<", self.progress, True, 0)
        self.assertFalse(grades["model_state_preserved"])

    def test_scope_autoscaling_is_not_semantic_state_by_default(self):
        before = {"block_parameters": [{"path": "fixture/Scope", "type": "Scope",
                                        "ActiveDisplayYMinimum": "-10",
                                        "ActiveDisplayYMaximum": "10"}],
                  "model_parameters": {}, "models": "fixture"}
        after = {"block_parameters": [{"path": "fixture/Scope", "type": "Scope",
                                       "ActiveDisplayYMinimum": "-12.6",
                                       "ActiveDisplayYMaximum": "18.3"}],
                 "model_parameters": {}, "models": "fixture"}
        self.assertTrue(model_state_preserved(before, after))

    def test_authored_scope_limits_remain_semantic_when_requested(self):
        before = {"block_parameters": [{"path": "fixture/Scope", "type": "Scope",
                                        "ActiveDisplayYMinimum": "-10",
                                        "ActiveDisplayYMaximum": "10"}],
                  "model_parameters": {}, "models": "fixture"}
        after = {"block_parameters": [{"path": "fixture/Scope", "type": "Scope",
                                       "ActiveDisplayYMinimum": "-12.6",
                                       "ActiveDisplayYMaximum": "18.3"}],
                 "model_parameters": {}, "models": "fixture"}
        self.assertFalse(model_state_preserved(
            before, after, {"ActiveDisplayYMinimum", "ActiveDisplayYMaximum"}))

    def test_correct_work_is_accepted_and_preserved(self):
        self.assertTrue(all(self.grade().values()))

    def test_ans_loss_fails_even_when_general_task_observations_pass(self):
        self.state["ans_preserved"] = False
        grades = self.grade()
        self.assertFalse(grades["ans_preserved"])
        self.assertTrue(grades["required_task_evidence"])
        self.assertFalse(all(grades.values()))

    def test_correct_work_withheld_is_a_failure(self):
        self.progress = {"completedStepIds": ["t01", "t02", "t03"], "currentStepId": "t04"}
        grades = self.grade(message="Please run the model again.")
        self.assertFalse(grades["task_acceptance"])
        self.assertFalse(grades["progress"])

    def test_missing_result_cannot_receive_acceptance(self):
        grades = self.grade("missing", before="fail", after="fail")
        self.assertFalse(grades["task_acceptance"])
        self.assertFalse(grades["progress"])

    def test_wrong_model_result_can_be_correctly_withheld(self):
        self.progress = {"completedStepIds": ["t01", "t02", "t03"], "currentStepId": "t04"}
        self.assertTrue(all(self.grade("wrong-model", before="fail", after="fail", message="Incomplete.").values()))

    def test_completed_task_flag_without_advancement_is_not_withheld_progress(self):
        self.progress["currentStepId"] = "t04"
        self.assertFalse(self.grade("missing", before="fail", after="fail", message="Incomplete.")["progress"])

    def test_inspection_error_must_actually_be_exercised(self):
        self.progress = {"completedStepIds": ["t01", "t02", "t03"], "currentStepId": "t04"}
        self.assertFalse(self.grade("inspection-error", message="Inspection unavailable.")["inspection_error_exercised"])
        self.assertTrue(all(self.grade("inspection-error", message="Inspection unavailable.", errors=1).values()))

    def test_unavailable_inspection_cannot_receive_completion(self):
        self.assertFalse(self.grade("inspection-error", errors=1)["task_acceptance"])


class SimulationCompletionAssertionsTests(unittest.TestCase):
    def grade(self, case, *, complete=True, accepted=True, clock=0, failed_run=True,
              tutor_simulations=0, current_step=None):
        status = "pass" if complete else "fail"
        model_state = {"block_parameters": [], "model_parameters": {}, "models": "fixture"}
        before = {"status": status, "state": model_state,
                  "facts": {"simulation_time": clock, "simulation_failure_exercised": failed_run}}
        after = {"status": status, "state": model_state}
        state = {"ans_preserved": True, "learner_variables_preserved": True, "temporaries": []}
        progress = {"completedStepIds": ["t01"] if accepted else [],
                    "currentStepId": current_step or ("t02" if accepted else "t01")}
        return trial_assertions(case, before, after, state,
            ">>> CORRECT! <<<" if accepted else "The run is not verified.", progress, True, 0,
            task_id="t01", next_task_id="t02", tutor_simulations=tutor_simulations)

    def test_successful_run_with_zero_current_clock_can_advance(self):
        self.assertTrue(all(self.grade("time-zero").values()))

    def test_zero_clock_scenario_must_actually_exercise_zero(self):
        self.assertFalse(self.grade("time-zero", clock=1)["zero_timing_exercised"])

    def test_never_run_model_cannot_advance_even_with_zero_clock(self):
        grades = self.grade("time-never-run", complete=False)
        self.assertFalse(grades["task_acceptance"])
        self.assertFalse(grades["progress"])

    def test_failed_run_with_zero_clock_is_correctly_withheld(self):
        self.assertTrue(all(self.grade("time-failed-run", complete=False, accepted=False).values()))

    def test_failed_run_scenario_must_execute_a_failure(self):
        grades = self.grade("time-failed-run", complete=False, accepted=False, failed_run=False)
        self.assertFalse(grades["failed_run_exercised"])

    def test_verification_cannot_run_the_learner_simulation(self):
        self.assertFalse(self.grade("time-zero", tutor_simulations=1)["no_tutor_simulation"])

    def test_completion_requires_the_correct_next_task(self):
        self.assertFalse(self.grade("time-zero", current_step="t03")["progress"])


class ConflictingConfigurationAssertionsTests(unittest.TestCase):
    def grade(self, case, *, complete=True, accepted=True, conflicts=1, direct_reads=1,
              direct_errors=0, message=None):
        status = "pass" if complete else "fail"
        model_state = {"block_parameters": [], "model_parameters": {}, "models": "fixture"}
        before = {"status": status, "state": model_state, "facts": {}}
        after = {"status": status, "state": model_state}
        state = {"ans_preserved": True, "learner_variables_preserved": True, "temporaries": []}
        progress = {"completedStepIds": ["t01", "t02", "t03"] if accepted else ["t01", "t02"],
                    "currentStepId": "t04" if accepted else "t03"}
        return trial_assertions(case, before, after, state,
            message or (">>> CORRECT! <<<" if accepted else "Configuration verification unavailable."),
            progress, True, 0, task_id="t03", next_task_id="t04",
            injected_conflicts=conflicts, direct_config_inspections=direct_reads,
            direct_config_errors=direct_errors)

    def test_conflicting_summary_with_direct_confirmation_advances(self):
        self.assertTrue(all(self.grade("config-conflict").values()))

    def test_conflict_case_must_inject_the_conflicting_summary(self):
        self.assertFalse(self.grade("config-conflict", conflicts=0)["config_conflict_exercised"])

    def test_conflict_case_requires_a_direct_configuration_read(self):
        self.assertFalse(self.grade("config-conflict", direct_reads=0)["direct_config_inspection"])

    def test_disabled_configuration_stays_on_the_current_task(self):
        self.assertTrue(all(self.grade("config-disabled", complete=False, accepted=False,
                                       conflicts=0, direct_reads=0).values()))

    def test_unavailable_direct_read_withholds_without_false_rejection(self):
        self.assertTrue(all(self.grade("config-direct-error", complete=True, accepted=False,
                                       direct_errors=1).values()))

    def test_unavailable_direct_read_requires_the_injected_error(self):
        self.assertFalse(self.grade("config-direct-error", complete=True, accepted=False,
                                    direct_errors=0)["direct_config_error_exercised"])

    def test_unavailable_direct_read_cannot_call_the_work_correctly_disabled(self):
        grades = self.grade("config-direct-error", complete=True, accepted=False, direct_errors=1,
                            message="External input is disabled. Turn it on.")
        self.assertFalse(grades["unresolved_conflict_not_false_rejected"])


class InspectionErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_permanent_outage_keeps_fixture_checks_available(self):
        live = AsyncMock()
        live.call.return_value = text_result("status: ok")
        backend = InspectionBackend(live, Path("workspace"), Path("observer.m"))
        backend.inspection_unavailable = True
        arguments = {"model": "fixture", "scope": "root", "depth": "0"}
        fixture_reply = await backend.call("model_read", arguments, "fixture")
        first = await backend.call("model_read", arguments)
        second = await backend.call("evaluate_matlab_code", {"code": "whos"})
        self.assertFalse(fixture_reply.is_error)
        self.assertTrue(first.is_error)
        self.assertTrue(second.is_error)
        self.assertEqual(backend.injected_errors, 2)
        self.assertEqual(live.call.await_count, 1)

    async def test_one_error_is_injected_only_for_tutor_inspection(self):
        live = AsyncMock()
        live.call.return_value = text_result("status: ok")
        backend = InspectionBackend(live, Path("workspace"), Path("observer.m"))
        backend.fail_next_inspection = True
        arguments = {"model": "fixture", "scope": "root", "depth": "0"}
        fixture_reply = await backend.call("model_read", arguments, "fixture")
        first = await backend.call("model_read", arguments)
        second = await backend.call("model_read", arguments)
        self.assertFalse(fixture_reply.is_error)
        self.assertTrue(first.is_error)
        self.assertFalse(second.is_error)
        self.assertEqual(backend.injected_errors, 1)
        self.assertEqual(live.call.await_count, 2)

    async def test_simulation_counter_distinguishes_fixture_actions_from_tutor_calls(self):
        live = AsyncMock()
        live.call.return_value = text_result("status: ok")
        backend = InspectionBackend(live, Path("workspace"), Path("observer.m"))
        await backend.call("evaluate_matlab_code", {"code": 'sensorRun = sim("fixture");'}, "fixture")
        await backend.call("evaluate_matlab_code", {"code": "disp(sensorRun.getSimulationMetadata);"})
        self.assertEqual(backend.tutor_simulations, 0)
        await backend.call("evaluate_matlab_code", {"code": 'mcpTmp_result = sim("fixture");'})
        self.assertEqual(backend.tutor_simulations, 1)


if __name__ == "__main__":
    unittest.main()
