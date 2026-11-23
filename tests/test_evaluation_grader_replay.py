"""Saved-evidence calibration must not leak labels or claim held-out accuracy."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/author-skills/references/evaluation/scripts"))

from mission_evals.calibration import compare_labels, prepare_sources, source_record, summary
from mission_evals.events import EventLog
from mission_evals.learner_grading import criterion_inputs, rubric_evidence, rubric_inputs


class GraderReplayTests(unittest.TestCase):
    def test_projection_excludes_original_judgments_and_grader_context(self):
        types = ["checkpoint", "tutor.response", "probe.response", "rubric.result", "agent.input", "agent.event", "trial.completed"]
        events = [{"event_id": str(i), "event_type": kind, "actor": "checker", "task_id": "t01",
                   "payload": {"text": kind}} for i, kind in enumerate(types)]
        projected = rubric_evidence(events)
        self.assertEqual([e["type"] for e in projected], types[:3])

    def test_possible_mistakes_are_not_expert_assignments(self):
        spec = {"mission_name": "example", "mistakes": ["partial_attempt", "help_before_effort"]}
        event = {"event_id": "schedule", "event_type": "schedule.assigned", "actor": "harness",
                 "task_id": None, "payload": {"schedule": []}}
        inputs = rubric_inputs(spec, "expert", [event])
        self.assertEqual(inputs["assigned_schedule"], [])
        self.assertNotIn("mistakes", inputs["specification"])
        self.assertEqual(inputs["specification"]["possible_mistake_types_not_assignments"], spec["mistakes"])
        self.assertIsNone(rubric_inputs(spec, "expert", [])["assigned_schedule"])
        self.assertIsNone(rubric_inputs(spec, "expert", [event, event])["assigned_schedule"])
        self.assertIn("mistakes", spec)

    def fixture(self, root):
        trace = root / "run/trials/example/casual/seed-1/events.jsonl"
        trace.parent.mkdir(parents=True)
        with EventLog(trace, run_id="r", suite="learner-sim", case_id="casual", mission_name="example") as log:
            log.set_learner("casual")
            log.emit("trial.started", "harness", {})
        (root / "run/manifest.json").write_text(json.dumps({"specifications": {"example": {"mission_name": "example"}}}))
        return trace, hashlib.sha256(trace.read_bytes()).hexdigest()

    def test_reviewed_and_unlabeled_sources_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace, fingerprint = self.fixture(root)
            case = {"id": "casual", "category": "persona_fidelity", "author_status": "pass",
                    "source_trace": trace.relative_to(root).as_posix(), "source_sha256": fingerprint}
            with self.assertRaisesRegex(ValueError, "multiple cohorts"):
                prepare_sources({"cases": [case]}, root, [trace])
            case["follow_up"] = {"status": "needs_reconciliation"}
            sources, excluded = prepare_sources({"cases": [case]}, root, [trace])
            self.assertEqual(sources[0]["targets"], [])
            self.assertEqual(sources[0]["cohort"], "unlabeled_holdout")
            self.assertEqual(excluded[0]["id"], "casual")

    def test_changed_source_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace, fingerprint = self.fixture(root)
            self.assertEqual(source_record(trace, root, fingerprint)["profile"], "casual")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                source_record(trace, root, "wrong")

    def test_trace_metadata_cannot_redirect_output_outside_its_source_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace, _ = self.fixture(root)
            event = json.loads(trace.read_text(encoding="utf-8"))
            event["mission_name"] = "../../outside"
            trace.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "metadata"):
                source_record(trace, root)

    def test_unknown_reference_is_valid_but_missing_grade_is_not_agreement(self):
        targets = [{"id": "recovery", "category": "recovery", "author_status": "unknown"}]
        self.assertTrue(compare_labels(targets, [{"id": "recovery", "status": "unknown", "evidence_ids": ["a"]}])[0]["agreement"])
        self.assertFalse(compare_labels(targets, [{"id": "recovery", "status": "unknown", "evidence_ids": []}])[0]["agreement"])
        self.assertFalse(compare_labels(targets, [])[0]["agreement"])

    def test_task_scoped_judgments_cannot_replace_whole_trace_or_other_task_labels(self):
        targets = [{"id": "task", "category": "tutor_boundaries", "task_id": "t05", "author_status": "unknown"}]
        grades = [{"id": "tutor_boundaries", "status": "pass", "evidence_ids": ["whole"]},
                  {"id": "tutor_boundaries", "task_id": "t06", "status": "fail", "evidence_ids": ["other"]}]
        self.assertFalse(compare_labels(targets, grades)[0]["agreement"])
        grades.append({"id": "tutor_boundaries", "task_id": "t05", "status": "unknown", "evidence_ids": ["task"]})
        self.assertTrue(compare_labels(targets, grades)[0]["agreement"])

    def test_task_grader_receives_only_relevant_evidence_without_author_labels(self):
        spec = {"mission_name": "example", "tasks": [{"id": "t05"}, {"id": "t06"}]}
        events = [{"event_id": task, "event_type": "tutor.response", "actor": "tutor", "task_id": task,
                   "payload": {"text": task}} for task in ("t05", "t06")]
        inputs = criterion_inputs(spec, "expert", events, "tutor_boundaries", "t05", {"limitation": "Checker also ran a simulation"})
        self.assertEqual([e["id"] for e in inputs["evidence"]], ["t05"])
        self.assertNotIn("author_status", inputs)
        self.assertNotIn("targets", inputs)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            criterion_inputs(spec, "expert", events, "tutor_boundaries", "missing")

    def test_incomplete_trials_and_unlabeled_traces_cannot_inflate_agreement(self):
        report = {"sources": [{"targets": [{"author_status": "pass"}]}, {"targets": []}], "trials_per_source": 2,
                  "results": [{"cohort": "author_reviewed_examples", "comparisons": [{"agreement": True}]},
                              {"cohort": "author_reviewed_examples", "comparisons": [{"agreement": True}], "error": "cleanup failed"},
                              {"cohort": "unlabeled_holdout", "comparisons": []}]}
        result = summary(report)
        self.assertEqual(result["reviewed_example_agreements"], 1)
        self.assertEqual(result["reviewed_example_comparisons"], 1)
        self.assertEqual(result["expected_reviewed_example_comparisons"], 2)
        self.assertEqual(result["not_run"], 1)
        self.assertEqual(result["unlabeled_holdout_trials"], 1)
        self.assertEqual(result["qualification"], "provisional")

    def test_unlabeled_disagreement_is_repeatability_not_reference_accuracy(self):
        report = {"sources": [{"targets": []}], "trials_per_source": 2,
                  "results": [{"source_id": "holdout", "trial_number": i, "cohort": "unlabeled_holdout", "comparisons": [],
                               "grades": [{"id": "tutor_boundaries", "status": status, "evidence_ids": ["event"]}]}
                              for i, status in ((1, "pass"), (2, "fail"))]}
        result = summary(report)
        self.assertEqual(result["reviewed_example_comparisons"], 0)
        self.assertEqual(result["unlabeled_category_pairs"], 1)
        self.assertEqual(result["unlabeled_category_agreements"], 0)
        self.assertEqual(result["unlabeled_disagreements"][0]["category"], "tutor_boundaries")
        self.assertEqual(result["qualification"], "provisional")


if __name__ == "__main__":
    unittest.main()
