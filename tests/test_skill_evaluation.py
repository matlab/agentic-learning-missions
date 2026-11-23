"""Tutor-skill harness tests; no model calls or MATLAB process is required."""

import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

import httpx2

from mission_evals.cli import finish_report, merge_runs
from mission_evals.codex_runtime import ApprovalReviewUnavailable, capture_turn
from mission_evals.events import EventLog, read_events
from mission_evals.skill_assets import prepare_behavior_workspace, prepare_live_workspace, protected_hashes, snapshot
from mission_evals.skill_bridge import ScalarBackend, TutorBridge, serve_bridge, text_result
from mission_evals.skill_grading import deterministic_grades, grade_status
from mission_evals.skill_suite import DEFAULT_CASES, comparison, load_cases, summarize, verify_fixture_state
from mission_evals.workspace import prepare_codex_home, trial_workspace


class CaseTests(unittest.TestCase):
    def test_layers_select_independent_cases(self):
        _, behavior = load_cases(DEFAULT_CASES, "behavior", [])
        _, live = load_cases(DEFAULT_CASES, "live", [])
        self.assertEqual(len(behavior), 14)
        self.assertEqual(len(live), 1)
        self.assertFalse({c["id"] for c in behavior} & {c["id"] for c in live})

    def test_unknown_selected_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown selected"):
            load_cases(DEFAULT_CASES, "all", ["missing-case"])

    def test_behavior_bundle_is_practice_only_and_uses_copied_skill(self):
        with trial_workspace() as root:
            workspace = root / "workspace"
            skill = prepare_behavior_workspace(workspace, DEFAULT_CASES.parent / "fixtures/scalar-sampling",
                                               ROOT / "src/skills/mission-tutoring")
            manifest = json.loads((workspace / ".interactive-missions/manifest.json").read_text())
            self.assertEqual(manifest["mode"], "practice")
            self.assertFalse(manifest["allowAgentEdits"])
            self.assertFalse((workspace / ".interactive-missions/progress.json").exists())
            self.assertEqual((skill / "SKILL.md").read_bytes(),
                             (ROOT / "src/skills/mission-tutoring/SKILL.md").read_bytes())
            hashes = protected_hashes(workspace)
            (skill / "SKILL.md").write_text("changed")
            self.assertNotEqual(hashes, protected_hashes(workspace))

    def test_snapshot_rejects_recursive_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            with self.assertRaisesRegex(ValueError, "outside its input"):
                snapshot(source, source / "recursive")

    def test_custom_model_catalog_and_review_policy_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            catalog = '{"models":[{"slug":"example","auto_review_model_override":null}]}'
            (source / "models.json").write_text(catalog)
            (source / "config.toml").write_text('model_catalog_json="models.json"\napprovals_reviewer="auto_review"\n')
            with patch.dict(os.environ, {"CODEX_HOME": str(source)}):
                with trial_workspace() as root:
                    generated = prepare_codex_home(root)
                    settings = tomllib.loads((generated / "config.toml").read_text())
                    self.assertEqual(settings["approvals_reviewer"], "auto_review")
                    self.assertEqual(Path(settings["model_catalog_json"]).read_text(), catalog)
                    self.assertNotEqual(Path(settings["model_catalog_json"]), source / "models.json")


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_visible_commentary_is_included_in_tutor_grading(self):
        class Payload:
            def __init__(self, value):
                self.value = value

            def model_dump(self, **kwargs):
                return self.value

        class Handle:
            id = "turn"

            async def stream(self):
                for message in ("Enter sampleRate = 100.", "Here is a hint."):
                    yield SimpleNamespace(method="item/completed", payload=Payload({
                        "item": {"type": "agentMessage", "text": message}}))
                yield SimpleNamespace(method="turn/completed", payload=Payload({"turn": {"status": "completed"}}))

        class Thread:
            id = "thread"

            async def turn(self, *args, **kwargs):
                return Handle()

        with trial_workspace() as root:
            with EventLog(root / "events.jsonl", run_id="r", suite="tutor-skill", case_id="c") as log:
                response = await capture_turn(Thread(), "help", "tutor", log, include_commentary=True)
        self.assertIn("sampleRate = 100", response)
        self.assertIn("Here is a hint", response)

    async def test_matlab_error_with_false_error_flag_does_not_complete_provisioning(self):
        class Broker:
            async def call(self, *args):
                return text_result("Error using prepareWorkspace: setup did not complete")

        with self.assertRaisesRegex(RuntimeError, "provisioning did not complete"):
            await prepare_live_workspace(Broker(), Path("workspace"), Path("fixture"), Path("skill"), ROOT)

    async def test_live_inspection_requires_success_marker(self):
        class Broker:
            async def call(self, *args):
                return text_result("Error using sampleRate: invalid inspection")

        result = await ScalarBackend(Broker()).call("evaluate_matlab_code", {"code": "sampleRate"})
        self.assertTrue(result.is_error)

    async def test_file_escape_and_unknown_tool_are_denied(self):
        with trial_workspace() as root:
            workspace = root / "workspace"
            workspace.mkdir()
            (root / "private.txt").write_text("private evidence")
            with EventLog(root / "events.jsonl", run_id="r", suite="tutor-skill", case_id="c") as log:
                bridge = TutorBridge(workspace, ScalarBackend(), log)
                denied = await bridge.call("read_workspace_file", {"path": "../private.txt"})
                unknown = await bridge.call("execute_shell", {"command": "anything"})
            self.assertTrue(denied.is_error)
            self.assertNotIn("private evidence", denied.content[0].text)
            self.assertTrue(unknown.is_error)

    async def test_annotations_describe_actual_capabilities(self):
        with trial_workspace() as root:
            with EventLog(root / "events.jsonl", run_id="r", suite="tutor-skill", case_id="c") as log:
                controlled = TutorBridge(root, ScalarBackend(), log)
                live = TutorBridge(root, ScalarBackend(live=object()), log)
                controlled_tools = {t.name: t for t in controlled.tools}
                live_tools = {t.name: t for t in live.tools}
                self.assertTrue(controlled_tools["evaluate_matlab_code"].annotations.read_only_hint)
                self.assertFalse(live_tools["evaluate_matlab_code"].annotations.read_only_hint)
                self.assertTrue(live_tools["read_workspace_file"].annotations.read_only_hint)

    async def test_controlled_backend_does_not_execute_learner_assignment(self):
        backend = ScalarBackend()
        await backend.set_state(None)
        reply = await backend.call("evaluate_matlab_code", {"code": "sampleRate = 100;"})
        self.assertTrue(reply.is_error)
        self.assertIsNone((await backend.state())["sample_rate"])

    async def test_controlled_observation_names_the_actual_variable_and_preserves_absence(self):
        backend = ScalarBackend()
        for value in (None, 0, 100):
            await backend.set_state(value)
            reply = await backend.call("evaluate_matlab_code", {"code": "whos sampleRate"})
            observed = json.loads(reply.content[0].text.split(": ", 1)[1])
            variable = observed["variables"][0]
            self.assertEqual(variable["name"], "sampleRate")
            self.assertEqual(variable["exists"], value is not None)
            self.assertNotIn("sample_rate", reply.content[0].text)
            if value is None:
                self.assertNotIn("value", variable)
            else:
                self.assertEqual(variable["value"], value)

    async def test_bridge_rejects_missing_authentication(self):
        with trial_workspace() as root:
            with EventLog(root / "events.jsonl", run_id="r", suite="tutor-skill", case_id="c") as log:
                bridge = TutorBridge(root, ScalarBackend(), log)
                async with serve_bridge(bridge) as (servers, environment):
                    async with httpx2.AsyncClient(trust_env=False) as client:
                        response = await client.post(servers["matlab"]["url"], json={})
                    self.assertEqual(response.status_code, 401)
                    self.assertTrue(environment["IM_EVAL_BRIDGE_TOKEN"])
                    self.assertEqual(bridge.calls, [])

    async def test_approval_service_failure_interrupts_instead_of_grading_tutor(self):
        class Payload:
            def model_dump(self, **kwargs):
                return {"item": {"type": "mcpToolCall", "error": {
                    "message": "Automatic approval review failed: 404 no matching LLM client found"}}}

        class Handle:
            id = "turn"
            interrupted = False

            async def stream(self):
                yield SimpleNamespace(method="item/completed", payload=Payload())

            async def interrupt(self):
                self.interrupted = True

        handle = Handle()

        class Thread:
            id = "thread"

            async def turn(self, *args, **kwargs):
                return handle

        with trial_workspace() as root:
            with EventLog(root / "events.jsonl", run_id="r", suite="tutor-skill", case_id="c") as log:
                with self.assertRaises(ApprovalReviewUnavailable):
                    await capture_turn(Thread(), "start", "tutor", log, allow_tools=True)
            self.assertTrue(handle.interrupted)
            self.assertEqual(read_events(root / "events.jsonl")[-1]["event_type"], "agent.event")


class GradingTests(unittest.TestCase):
    def test_unestablished_fixture_is_not_a_tutor_failure(self):
        with self.assertRaisesRegex(RuntimeError, "fixture state was not established"):
            verify_fixture_state({"sample_rate": None, "protected_sentinel": 2718}, 100)

    def test_false_success_and_recipe_are_rejected(self):
        _, cases = load_cases(DEFAULT_CASES, "behavior", ["hint-before-effort"])
        grades = deterministic_grades(cases[0], [{"step_id": "answer", "text":
            ">>> CORRECT! <<< Enter sampleRate = 100.", "event_id": "response"}], [], [],
            explicit_event="invocation", bundle_event="bundle", bundle_unchanged=True)
        by_id = {g["id"]: g for g in grades}
        self.assertEqual(by_id["not_complete"]["status"], "fail")
        self.assertEqual(by_id["no_recipe"]["status"], "fail")
        self.assertEqual(by_id["untouched"]["status"], "unknown")
        self.assertEqual(grade_status(grades), "fail")

    def test_missing_trial_and_uncalibrated_grader_prevent_readiness(self):
        self.assertEqual(summarize([{"status": "pass"}], 2, "reviewed")["readiness"], "insufficient_evidence")
        self.assertEqual(summarize([{"status": "pass"}], 1, "pending_author_review")["readiness"], "insufficient_evidence")

    def test_missing_runtime_is_not_comparable(self):
        report = {"configurations": {"baseline": {"sha256": "a"}, "candidate": {"sha256": "b"}},
                  "results": [{"case_id": "c", "trial_number": 1, "status": "unknown", "configuration": v}
                              for v in ("baseline", "candidate")]}
        self.assertFalse(comparison(report)["trials"][0]["comparable"])

    def test_separate_runs_require_matching_fixture_and_grader_inputs(self):
        baseline = {"schema_version": "1.0", "suite": "tutor-skill", "case_spec_sha256": "a",
                    "fixture_hashes": {}, "runner_sha256": "r", "selected_cases": ["c"],
                    "trials_per_case": 2, "packages": {}, "grading_calibration": "reviewed",
                    "configurations": {"candidate": {"sha256": "skill"}}, "results": []}
        candidate = copy.deepcopy(baseline)
        candidate["case_spec_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "case_spec_sha256"):
            merge_runs(baseline, candidate)
        rebuilt = finish_report(baseline)
        self.assertEqual(rebuilt["summaries"]["candidate"]["counts"]["not_run"], 2)


if __name__ == "__main__":
    unittest.main()
