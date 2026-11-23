"""Simulator contracts, independent of MATLAB and model calls."""

import copy
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp.types import Tool

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

from mission_evals.events import EventLog, read_events, write_json
from mission_evals.learner_grading import acceptance_grade, checked_grade, schedule_grade
from mission_evals.learner_reports import accumulate, compare, compatible, runtime_signature
from mission_evals.learner_sim import action_summary, presented_task, readiness, rebuild
from mission_evals.learner_spec import mistake_schedule, prepare_spec, load_spec
from mission_evals.mission_backend import MissionBackend, validate_learner_call
from mission_evals.skill_bridge import text_result
from mission_evals.processes import OwnedProcessTree
from mission_evals.codex_runtime import isolate_skill_catalog

ROOT = SCRIPTS.parents[4]


class SimulatorTests(unittest.TestCase):
    def test_effective_catalog_excludes_host_skills_and_preserves_local_tutor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cwd = root / "workspace"
            local = str(cwd / ".codex/skills/mission-tutoring/SKILL.md")
            host = str(root / "host-skills/simulation/SKILL.md")
            def skill(path, enabled):
                return SimpleNamespace(name=Path(path).parent.name, path=SimpleNamespace(root=path), enabled=enabled)
            def catalog(host_enabled):
                return SimpleNamespace(data=[SimpleNamespace(skills=[skill(host, host_enabled), skill(local, True)])])
            config = root / "config.toml"
            request = AsyncMock(side_effect=[catalog(True), SimpleNamespace(file_path=SimpleNamespace(root=str(config))), catalog(False)])
            client = SimpleNamespace(_client=SimpleNamespace(request=request))
            with EventLog(root / "events.jsonl", run_id="r", suite="infrastructure", case_id="catalog") as log:
                asyncio.run(isolate_skill_catalog(client, cwd, log, config))
            self.assertEqual(request.call_args_list[1].args[0], "config/batchWrite")
            self.assertEqual(request.call_args_list[1].args[1]["filePath"], str(config))
            self.assertEqual(request.call_args_list[1].args[1]["edits"][0]["value"], [{"path": host, "enabled": False}])
            self.assertEqual(read_events(root / "events.jsonl")[-1]["payload"]["enabled"], [{"name": "mission-tutoring", "path": local}])

    def test_catalog_isolation_failure_stops_before_an_agent_can_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = SimpleNamespace(name="host", path=SimpleNamespace(root=str(root / "host/SKILL.md")), enabled=True)
            catalog = SimpleNamespace(data=[SimpleNamespace(skills=[host])])
            config = root / "config.toml"
            client = SimpleNamespace(_client=SimpleNamespace(request=AsyncMock(side_effect=[catalog, SimpleNamespace(file_path=SimpleNamespace(root=str(config))), catalog])))
            with EventLog(root / "events.jsonl", run_id="r", suite="infrastructure", case_id="catalog") as log:
                with self.assertRaises(RuntimeError):
                    asyncio.run(isolate_skill_catalog(client, root / "workspace", log, config))

    def test_old_simulation_cannot_complete_a_required_rerun(self):
        backend = MissionBackend(None, Path("unused"), Path("observer/observe_mission.m"))
        def observation(stamp):
            return text_result("IM_OBSERVATION " + json.dumps({"status": "pass", "facts": {"latest_simulation_start": stamp}}))
        backend.call = AsyncMock(side_effect=[observation(100), observation(100), observation(101)])
        async def check():
            before = await backend.observe("continuous-and-discrete-time", "t02")
            incomplete = await backend.observe("continuous-and-discrete-time", "t02")
            complete = await backend.observe("continuous-and-discrete-time", "t02")
            return before, incomplete, complete
        before, incomplete, complete = asyncio.run(check())
        self.assertEqual([before["status"], incomplete["status"], complete["status"]], ["fail", "fail", "pass"])

    def test_cleanup_does_not_wait_on_a_reused_pid(self):
        root, stale = MagicMock(), MagicMock()
        root.is_running.return_value = False
        stale.is_running.return_value = False
        stale.pid = 41
        tree = OwnedProcessTree.__new__(OwnedProcessTree)
        tree.root, tree.members = root, {41: stale}
        with patch("mission_evals.processes.psutil.wait_procs", return_value=([], [stale])):
            result = asyncio.run(tree.finish())
        self.assertTrue(result["all_exited"])
        stale.terminate.assert_not_called()
        stale.kill.assert_not_called()

    def test_windows_stale_parent_pid_does_not_transfer_ownership(self):
        root = MagicMock()
        root.pid = 40
        root.create_time.return_value = 20
        old = MagicMock()
        old.pid = 41
        old.create_time.return_value = 10
        old.parent.return_value = root
        fresh = MagicMock()
        fresh.pid = 42
        fresh.create_time.return_value = 21
        fresh.parent.return_value = root
        root.children.return_value = [old, fresh]
        tree = OwnedProcessTree.__new__(OwnedProcessTree)
        tree.root, tree.members = root, {}
        tree.capture()
        self.assertEqual(set(tree.members), {40, 42})

    def test_draft_is_bound_to_exact_mission_and_not_reviewed(self):
        with tempfile.TemporaryDirectory() as directory:
            mission = ROOT / "marketplace/missions/root-inports-outports"
            path = Path(directory) / "spec.json"
            draft = prepare_spec(mission, path)
            self.assertEqual(draft["author_review"], "pending_author_review")
            self.assertEqual(load_spec(path, mission), draft)
            draft["mission_sha256"] = "wrong"
            write_json(path, draft)
            with self.assertRaises(ValueError):
                load_spec(path, mission)

    def test_schedule_reproducible_and_profile_specific(self):
        tasks = [{"id": f"t0{i}"} for i in range(1, 6)]
        self.assertEqual(mistake_schedule("expert", tasks, 73), [])
        self.assertEqual(mistake_schedule("naive", tasks, 73), mistake_schedule("naive", tasks, 73))
        self.assertNotEqual(mistake_schedule("casual", tasks, 73), mistake_schedule("casual", tasks, 74))

    def test_expert_behavior_invalidates_assigned_partial_attempt(self):
        event = {"task_id": "t01", "attempt": 1, "kind": "partial_attempt"}
        actual = {"task_id": "t01", "attempt": 1, "product_actions": [{}], "state_changed": True, "observation_status": "pass", "evidence_ids": ["a"]}
        self.assertEqual(schedule_grade([event], [actual])[0]["status"], "fail")
        actual["observation_status"] = "fail"
        self.assertEqual(schedule_grade([event], [actual])[0]["status"], "pass")
        actual["state_changed"] = False
        self.assertEqual(schedule_grade([event], [actual])[0]["status"], "fail")
        self.assertEqual(schedule_grade([event], [])[0]["status"], "unknown")

    def test_false_acceptance_independent_of_tutor_confidence(self):
        self.assertEqual(acceptance_grade(True, {"status": "fail"}, "state", "correct")["status"], "fail")
        self.assertEqual(acceptance_grade(True, {"status": "unknown"}, "state", "correct")["status"], "unknown")
        self.assertEqual(acceptance_grade(True, {"status": "pass"}, "state", "correct")["status"], "pass")

    def test_unreferenced_rubric_cannot_pass(self):
        grade = {"status": "pass", "evidence_ids": ["invented"], "reason": "sounds good"}
        self.assertEqual(checked_grade(grade, {"actual"})["status"], "unknown")

    def test_learner_hidden_files_and_tool_names_are_rejected(self):
        tools = {"evaluate_matlab_code": Tool(name="evaluate_matlab_code", input_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]})}
        validate_learner_call("evaluate_matlab_code", {"code": "whos"}, tools)
        for code in ('fileread("mission.yaml")', 'run("setup.m")', 'addpath("secret")'):
            with self.assertRaises(ValueError):
                validate_learner_call("evaluate_matlab_code", {"code": code}, tools)
        with self.assertRaises(ValueError):
            validate_learner_call("read_workspace_file", {"path": "mission.yaml"}, tools)

    def test_partial_action_trace_is_retained_in_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with EventLog(root / "events.jsonl", run_id="r", suite="learner-sim", case_id="naive", mission_name="example") as log:
                log.set_learner("naive")
                log.set_task("t01")
                log.emit("tutor.response", "tutor", {"text": "Try the task"})
                log.emit("learner.action", "learner", {"name": "evaluate_matlab_code", "arguments": {"code": "x=1"}})
            action_summary(read_events(root / "events.jsonl"), root / "actions.jsonl")
            row = json.loads((root / "actions.jsonl").read_text())
            self.assertEqual(row["action"], "interrupted_turn")
            self.assertEqual(row["mission_task_id"], "t01")
            self.assertEqual(row["learner_type"], "naive")

    def test_offline_rebuild_retains_interrupted_trial_without_grades(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"suite": "learner-sim", "results": [], "selected_missions": ["example"], "profiles": ["naive"],
                        "trials_per_profile": 1, "specifications": {"example": {"author_review": "pending_author_review", "grading_calibration": "pending_author_review"}}}
            write_json(root / "manifest.json", manifest)
            trace = root / "trials/example/naive/seed-73/events.jsonl"
            trace.parent.mkdir(parents=True)
            with EventLog(trace, run_id="r", suite="learner-sim", case_id="naive", mission_name="example") as log:
                log.set_learner("naive")
                log.emit("trial.started", "harness", {"seed": 73})
                log.emit("learner.action", "learner", {"name": "evaluate_matlab_code", "arguments": {"code": "x=1"}})
            from mission_evals.cli import main
            self.assertEqual(main(["report", "--run", str(root)]), 2)
            result = json.loads((root / "benchmark.json").read_text(encoding="utf-8"))
            self.assertEqual(result["results"][0]["stop_reason"], "interrupted")
            self.assertEqual(result["summary"]["counts"]["unknown"], 1)
            self.assertTrue((trace.parent / "actions.jsonl").exists())

    def test_pending_review_and_missing_trials_never_qualify(self):
        report = {"results": [], "selected_missions": ["a", "b"], "profiles": ["expert", "casual", "naive"],
                  "trials_per_profile": 2, "specifications": {"a": {"author_review": "pending_author_review", "grading_calibration": "pending_author_review"}}}
        self.assertEqual(readiness(report)["counts"]["not_run"], 12)
        self.assertEqual(readiness(report)["readiness"], "insufficient_evidence")

    def test_distinct_seeds_with_identical_mistakes_do_not_confirm_readiness(self):
        report = {"selected_missions": ["example"], "profiles": ["expert", "casual", "naive"], "trials_per_profile": 2,
                  "specifications": {"example": {"author_review": "reviewed", "grading_calibration": "reviewed"}},
                  "results": [{"mission_name": "example", "profile": p, "seed": seed, "status": "pass", "schedule": [{"task": "t01"}]}
                              for p in ("expert", "casual", "naive") for seed in (1, 2)]}
        self.assertEqual(readiness(report)["readiness"], "insufficient_evidence")
        for row in report["results"]:
            if row["seed"] == 2:
                row["schedule"] = [{"task": "t02"}]
        self.assertEqual(readiness(report)["readiness"], "meets_pilot_bar")

    def test_comparison_ignores_only_ephemeral_thread_ids(self):
        row = {"runtime": {"learner": {"thread_id": "a", "model": "model-one"}}}
        other = copy.deepcopy(row)
        other["runtime"]["learner"]["thread_id"] = "b"
        self.assertEqual(runtime_signature(row), runtime_signature(other))
        other["runtime"]["learner"]["model"] = "model-two"
        self.assertNotEqual(runtime_signature(row), runtime_signature(other))
        with self.assertRaises(ValueError):
            compatible({"runner_sha256": "old"}, {"runner_sha256": "new"})
        compatible({"mission_hashes": {"a": "x"}, "specifications": {"a": {}}},
                   {"mission_hashes": {"b": "y"}, "specifications": {"b": {}}}, partial_missions=True)
        with self.assertRaises(ValueError):
            compatible({"mission_hashes": {"a": "x"}}, {"mission_hashes": {"a": "changed"}}, partial_missions=True)

    def test_accumulation_requires_distinct_seeds_and_keeps_trace_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def fixture(name, seed):
                source = root / name
                source.mkdir()
                trace = source / "events.jsonl"
                with EventLog(trace, run_id=name, suite="learner-sim", case_id="expert", mission_name="example") as log:
                    log.emit("trial.started", "harness", {"seed": seed})
                report = {"suite": "learner-sim", "selected_missions": ["example"], "profiles": ["expert"], "trials_per_profile": 1,
                          "skill": {"sha256": "same"}, "specifications": {"example": {"author_review": "pending_author_review", "grading_calibration": "pending_author_review"}},
                          "results": [{"trial_id": name, "mission_name": "example", "profile": "expert", "seed": seed, "status": "pass",
                                       "completed_tasks": ["t01"], "stop_reason": "mission_completed", "recommendations": [],
                                       "runtime": {"learner": {"thread_id": name, "model": "same-model"}}, "evidence_path": "events.jsonl"}],
                          "summary": {"readiness": "insufficient_evidence"}}
                write_json(source / "benchmark.json", report)
                return source
            first, second = fixture("one", 73), fixture("two", 74)
            output = root / "merged"
            result = accumulate([first, second], output)
            self.assertEqual(len(result["results"]), 2)
            self.assertEqual(result["summary"]["readiness"], "insufficient_evidence")
            self.assertTrue(all((output / row["evidence_path"]).is_file() for row in result["results"]))
            self.assertEqual(len(rebuild(output)["results"]), 2)
            with self.assertRaises(ValueError):
                accumulate([first, first], root / "duplicate")
            comparison = compare(first, first, root / "comparison")
            self.assertTrue(comparison["trials"][0]["comparable"])
            self.assertTrue(comparison["identical_skill_inputs"])

    def test_one_task_scope_and_task_detection(self):
        tasks = [{"id": "t01"}, {"id": "t02"}]
        self.assertEqual(presented_task("### Task 1: Start", tasks), "t01")
        self.assertIsNone(presented_task("What do you predict?", tasks))

    def test_cli_independent_invocation_does_not_run_skill_suite(self):
        from mission_evals.cli import main
        with patch("mission_evals.cli.run_suite", side_effect=AssertionError("Wrong suite")):
            with tempfile.TemporaryDirectory() as directory:
                self.assertEqual(main(["learner-sim", "prepare", "--mission", str(ROOT / "marketplace/missions/root-inports-outports"),
                                       "--output", str(Path(directory) / "spec.json")]), 0)


if __name__ == "__main__":
    unittest.main()
