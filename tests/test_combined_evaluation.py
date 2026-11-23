"""Composition, orchestration, and standalone independence without live agents."""

import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/author-skills/references/evaluation/scripts"))

from mission_evals import cli, combined, learner_cli
from mission_evals.events import EventLog, write_json


def source(root, label, status="pass", *, partial=False):
    root.mkdir(parents=True, exist_ok=False)
    is_skill = label == "skill-eval"
    relative = "candidate/example/trial-1/events.jsonl" if is_skill else "trials/example/expert/seed-73/events.jsonl"
    trace = root / relative
    trace.parent.mkdir(parents=True)
    with EventLog(trace, run_id=label, suite=combined.SUITES[label], case_id="example", mission_name="example") as log:
        log.emit("trial.started", "harness", {"seed": 73})
    row = {"trial_id": label, "status": status, "grades": [{"id": "boundary", "status": "unknown", "task_id": "5"}],
           "runtime": {"model": "test-model"}, "evidence_path": relative,
           "configuration": "candidate", "case_id": "example", "trial_number": 1,
           "mission_name": "example", "profile": "expert", "seed": 73,
           "review_context": {"author_review": "accepted", "limitation": "expression not executed"}}
    summary = {"counts": {"pass": int(status == "pass"), "fail": int(status == "fail"),
                          "unknown": int(status == "unknown"), "not_run": 0},
               "readiness": "insufficient_evidence", "provisional": True}
    report = {"schema_version": "1.0", "suite": combined.SUITES[label], "results": [] if partial else [row],
              "runner_sha256": "skill-runner" if is_skill else "learner-runner", "packages": {},
              "grading_calibration": "pending_validation", "configurations": {"candidate": {"sha256": "skill"}},
              "skill": {"sha256": "other-skill"}, "trials_per_case": 1, "selected_cases": ["example"],
              "selected_missions": ["example"], "profiles": ["expert"], "trials_per_profile": 1,
              "specifications": {"example": {"author_review": "pending_author_review", "grading_calibration": "pending_validation"}}}
    if not partial:
        report.update(summaries={"candidate": summary}, summary=summary)
        write_json(root / "benchmark.json", report)
        write_json(trace.parent / "grading.json", row)
    write_json(root / "manifest.json", report)
    (root / "report.md").write_text("Original report: limitations and historical independent unknown.\n", encoding="utf-8")
    return report


def options(output):
    return SimpleNamespace(output=output, timeout_seconds=60, skill=ROOT / "src/skills/mission-tutoring",
                           skill_baseline=None, cases_file=combined.DEFAULT_CASES, layer="behavior", case=[],
                           skill_trials=1, learner_trials=1, skill_trial_timeout_seconds=20,
                           learner_trial_timeout_seconds=30, mission=[ROOT / "marketplace/missions/continuous-and-discrete-time"],
                           spec_dir=Path("specs"), profile=["expert"], seed=73, turns_per_task=12, max_tasks=1,
                           model=None, matlab_server=Path("server"), matlab_root=Path("matlab"), toolbox_root=ROOT,
                           extension_file=[Path("tools.json")], toolkit_root=Path("toolkit"))


class SavedCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill, self.learner, self.output = (self.root / name for name in ("skill", "learner", "combined"))

    def test_preserves_failure_unknown_labels_and_provisional_readiness_without_source_writes(self):
        old = source(self.skill, "skill-eval", "fail")
        new = source(self.learner, "learner-sim")
        before = {p: p.read_bytes() for root in (self.skill, self.learner) for p in root.rglob("*") if p.is_file()}
        report = combined.compose(self.skill, self.learner, self.output)
        self.assertEqual(combined.exit_code(report), 1)
        self.assertEqual(report["components"]["skill-eval"]["source_report"], old)
        self.assertEqual(report["components"]["learner-sim"]["source_report"], new)
        self.assertEqual(combined.rebuild(self.output)["components"], report["components"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        for part in report["components"].values():
            self.assertTrue((self.output / part["report_link"]).is_file())
            self.assertTrue((self.output / part["evidence"][0]["trace"]).is_file())
        self.assertNotIn("summary", report)
        self.assertIn("other-skill", (self.output / "report.md").read_text())

    def test_missing_initial_evidence_and_wrong_suite_rejected_before_output(self):
        source(self.skill, "skill-eval")
        source(self.learner, "learner-sim")
        with self.assertRaisesRegex(ValueError, "Expected a tutor-skill"):
            combined.compose(self.learner, self.skill, self.output)
        next(self.skill.rglob("events.jsonl")).unlink()
        with self.assertRaises(OSError):
            combined.compose(self.skill, self.learner, self.output)
        self.assertFalse(self.output.exists())

    def test_rebuild_retains_failure_when_source_evidence_disappears(self):
        source(self.skill, "skill-eval", "fail")
        source(self.learner, "learner-sim")
        combined.compose(self.skill, self.learner, self.output)
        next(self.skill.rglob("events.jsonl")).unlink()
        report = combined.rebuild(self.output)
        self.assertEqual(combined.exit_code(report), 1)
        part = report["components"]["skill-eval"]
        self.assertEqual(part["state"], "unavailable")
        self.assertEqual(part["source_report"]["results"][0]["status"], "fail")

    def test_missing_evidence_after_pass_never_remains_success(self):
        source(self.skill, "skill-eval")
        source(self.learner, "learner-sim")
        combined.compose(self.skill, self.learner, self.output)
        next(self.learner.rglob("events.jsonl")).unlink()
        self.assertEqual(combined.exit_code(combined.rebuild(self.output)), 2)

    def test_interrupted_ungraded_trial_is_unknown_for_each_suite(self):
        for label in combined.SUITES:
            path = self.root / label
            source(path, label, partial=True)
            part = combined.component(path, label, self.output)
            self.assertEqual(part["exit_code"], 2)
            self.assertTrue(part["recovered_partial_evidence"])
            self.assertEqual(part["source_report"]["results"][0]["status"], "unknown")
            self.assertFalse((path / "benchmark.json").exists())

    def test_corrupt_or_mismatched_trace_rejected(self):
        source(self.skill, "skill-eval")
        trace = next(self.skill.rglob("events.jsonl"))
        event = json.loads(trace.read_text())
        event["trial_id"] = "wrong"
        trace.write_text(json.dumps(event) + "\n")
        with self.assertRaisesRegex(ValueError, "does not match"):
            combined.component(self.skill, "skill-eval", self.output)
        event["sequence"] = 2
        trace.write_text(json.dumps(event) + "\n")
        with self.assertRaisesRegex(ValueError, "Out-of-order"):
            combined.component(self.skill, "skill-eval", self.output)

    def test_mode_mixing_and_nested_output_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            combined.main(["--skill-run", str(self.skill), "--learner-run", str(self.learner),
                           "--output", str(self.output), "--skill-trials", "2"])
        with self.assertRaisesRegex(ValueError, "outside source"):
            combined.compose(self.skill, self.learner, self.skill / "nested")
        self.assertFalse(self.output.exists())

    def test_report_cli_uses_offline_combined_rebuild(self):
        source(self.skill, "skill-eval")
        source(self.learner, "learner-sim", "unknown")
        combined.compose(self.skill, self.learner, self.output)
        with patch("mission_evals.combined.run_suite") as skill, patch("mission_evals.learner_sim.run") as learner:
            self.assertEqual(cli.main(["report", "--run", str(self.output)]), 2)
            skill.assert_not_called()
            learner.assert_not_called()


class CombinedExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_serial_execution_shared_budget_and_failure_does_not_gate_learner(self):
        with tempfile.TemporaryDirectory() as directory:
            args = options(Path(directory) / "combined")
            called = []
            async def skill(opt):
                called.append("skill")
                self.assertEqual(opt.trial_timeout_seconds, 20)
                return source(opt.output, "skill-eval", "fail")
            async def learner(opt):
                self.assertEqual(called, ["skill"])
                self.assertLess(opt.timeout_seconds, 60)
                self.assertEqual(opt.stop_file, args.output / "STOP")
                self.assertEqual(opt.trial_timeout_seconds, 30)
                called.append("learner")
                return source(opt.output, "learner-sim")
            with patch("mission_evals.combined.run_suite", skill), patch("mission_evals.learner_sim.run", learner):
                report = await combined.run(args)
            self.assertEqual(called, ["skill", "learner"])
            self.assertEqual(combined.exit_code(report), 1)

    async def test_stop_and_budget_exhaustion_preserve_first_component(self):
        for reason in ("stop", "budget"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                args = options(Path(directory) / "combined")
                async def skill(opt):
                    result = source(opt.output, "skill-eval")
                    if reason == "stop":
                        opt.stop_file.touch()
                    else:
                        # Shared deadline already elapsed before the second component.
                        clock.return_value = 1000
                    return result
                with patch("mission_evals.combined.time.monotonic", return_value=0) as clock, \
                        patch("mission_evals.combined.run_suite", skill), \
                        patch("mission_evals.learner_sim.run", new_callable=AsyncMock) as learner:
                    report = await combined.run(args)
                learner.assert_not_called()
                self.assertEqual(report["components"]["skill-eval"]["exit_code"], 0)
                self.assertEqual(combined.exit_code(report), 2)

    async def test_cancellation_preserves_partial_evidence_and_skips_second_suite(self):
        with tempfile.TemporaryDirectory() as directory:
            args = options(Path(directory) / "combined")
            async def skill(opt):
                source(opt.output, "skill-eval", partial=True)
                raise asyncio.CancelledError()
            with patch("mission_evals.combined.run_suite", skill), \
                    patch("mission_evals.learner_sim.run", new_callable=AsyncMock) as learner:
                report = await combined.run(args)
            learner.assert_not_called()
            self.assertEqual(combined.exit_code(report), 2)
            self.assertTrue(report["components"]["skill-eval"]["recovered_partial_evidence"])

    async def test_component_exception_is_recorded_and_other_suite_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = options(Path(directory) / "combined")
            async def learner(opt):
                return source(opt.output, "learner-sim")
            with patch("mission_evals.combined.run_suite", side_effect=RuntimeError("startup failed")), \
                    patch("mission_evals.learner_sim.run", learner):
                report = await combined.run(args)
            self.assertEqual(report["components"]["learner-sim"]["exit_code"], 0)
            self.assertIn("startup failed", report["components"]["skill-eval"]["error"])
            self.assertEqual(combined.exit_code(report), 2)


class IndependentCommandTests(unittest.TestCase):
    def test_standalone_commands_do_not_run_other_evaluator(self):
        result = {"results": [], "summaries": {"candidate": {"counts": {"unknown": 0, "not_run": 0}}}}
        with patch("mission_evals.cli.run_suite", new_callable=AsyncMock, return_value=result) as skill, \
                patch("mission_evals.learner_sim.run", new_callable=AsyncMock) as learner:
            self.assertEqual(cli.main(["skill-eval", "--skill", ".", "--layer", "behavior", "--output", "unused"]), 0)
            skill.assert_awaited_once()
            learner.assert_not_called()
        result = {"summary": {"counts": {"fail": 0, "unknown": 0, "not_run": 0}}}
        with patch("mission_evals.learner_cli.run", new_callable=AsyncMock, return_value=result) as learner, \
                patch("mission_evals.cli.run_suite", new_callable=AsyncMock) as skill:
            flags = ["--mission", "--spec-dir", "--skill", "--output", "--matlab-server", "--matlab-root",
                     "--toolbox-root", "--extension-file", "--toolkit-root"]
            self.assertEqual(learner_cli.main(["run", *[v for flag in flags for v in (flag, "unused")]]), 0)
            learner.assert_awaited_once()
            skill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
