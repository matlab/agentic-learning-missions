"""Calibration preparation: preserve evidence and distinguish injected outages."""

import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/author-skills/references/evaluation/scripts"))

from mission_evals.skill_bridge import ScalarBackend
from mission_evals.skill_grading import deterministic_grades, qualitative_evidence
from mission_evals.skill_suite import DEFAULT_CASES, load_cases


class CalibrationTests(unittest.TestCase):
    def test_followup_promotes_the_two_accepted_cases(self):
        original, _ = load_cases(DEFAULT_CASES, "all", [])
        draft, cases = load_cases(DEFAULT_CASES.with_name("milestone-4-draft.json"), "all", [])
        self.assertEqual(len(original["evals"]), 15)
        self.assertEqual(original["author_review"], "reviewed")
        self.assertEqual(original["grading_calibration"], "pending_validation")
        self.assertTrue({"valid-alternative-expression", "skip-inaccurate-hint"}
                        <= {c["id"] for c in original["evals"]})
        self.assertEqual(len(cases), 15)
        self.assertEqual(draft["grading_calibration"], "pending_validation")
        self.assertEqual(draft["author_review"], "reviewed")
        self.assertEqual(cases[:4], original["evals"][:4])

    def test_controlled_failure_keeps_driver_state_and_resets_next_step(self):
        async def exercise():
            backend = ScalarBackend()
            await backend.set_state(100)
            backend.configure_step({"tool_errors": {"evaluate_matlab_code": "Inspection unavailable"}})
            failed = await backend.call("evaluate_matlab_code", {"code": "disp(sampleRate)"})
            self.assertTrue(failed.is_error)
            self.assertEqual((await backend.state())["sample_rate"], 100)
            backend.configure_step({})
            restored = await backend.call("evaluate_matlab_code", {"code": "disp(sampleRate)"})
            self.assertFalse(restored.is_error)
            self.assertIn('"name": "sampleRate"', restored.content[0].text)
            self.assertIn('"value": 100', restored.content[0].text)
            self.assertNotIn("sample_rate", restored.content[0].text)
        asyncio.run(exercise())

    def test_injected_outages_cannot_masquerade_as_live_evidence(self):
        with self.assertRaisesRegex(ValueError, "controlled behavior"):
            ScalarBackend(live=object()).configure_step({"tool_errors": {"evaluate_matlab_code": "offline"}})
        document = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
        for errors in ({"execute_shell": "offline"}, {"evaluate_matlab_code": ""}, ["offline"]):
            modified = copy.deepcopy(document)
            modified["evals"][0]["steps"][0]["tool_errors"] = errors
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "cases.json"
                path.write_text(json.dumps(modified), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Scripted tool errors"):
                    load_cases(path, "all", [])

    def test_error_evidence_never_satisfies_successful_inspection(self):
        case = {"assertions": [{"id": k, "kind": k, "step": "blocked"}
                               for k in ("inspection", "inspection_error")]}
        grades = deterministic_grades(case, [{"step_id": "blocked", "event_id": "r", "text": "Cannot inspect"}],
            [{"name": "evaluate_matlab_code", "arguments": {}, "step_id": "blocked", "event_id": "c",
              "observation": True, "is_error": True}], [], explicit_event=None, bundle_event="b", bundle_unchanged=True)
        self.assertEqual([g["status"] for g in grades], ["fail", "pass"])

    def test_grader_sees_requests_and_results_without_its_own_prompt(self):
        events = [{"event_id": str(i), "event_type": kind, "actor": actor, "payload": {"text": text}}
                  for i, (kind, actor, text) in enumerate([
                      ("agent.input", "tutor", "Please inspect the same work again."),
                      ("bridge.result", "tutor", "Inspection unavailable"),
                      ("driver.step", "driver", "scripted state"),
                      ("tutor.response", "tutor", "I cannot inspect"),
                      ("agent.input", "grader", "Do not include this grading prompt"),
                      ("agent.event", "grader", "Internal grader event")])]
        self.assertEqual([e["id"] for e in qualitative_evidence(events)], ["0", "1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
