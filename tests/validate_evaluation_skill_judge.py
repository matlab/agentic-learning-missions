"""Opt-in model regression: real startup refusals and a synthetic false-completion control."""

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

import yaml
from mission_evals.events import EventLog, read_events, write_json
from mission_evals.skill_assets import snapshot
from mission_evals.skill_grading import qualitative_evidence, qualitative_grade
from mission_evals.skill_suite import DEFAULT_CASES, load_cases
from mission_evals.workspace import trial_workspace


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / "inputs"
    inputs.mkdir()
    document, cases = load_cases(DEFAULT_CASES, "behavior", ["missing-required-capability"])
    case = cases[0]
    mission = yaml.safe_load((DEFAULT_CASES.parent / case["fixture"] / "mission.yaml").read_text(encoding="utf-8"))
    report = {"suite": "skill-judge-regression", "provisional": True, "results": [],
              "runner": snapshot(SCRIPTS / "mission_evals", inputs / "runner"),
              "case": case, "case_specification": document, "budget_seconds": 600}
    variants = []
    for number in (1, 2):
        path = args.source_run / f"candidate/missing-required-capability/trial-{number}/events.jsonl"
        frozen = inputs / f"actual-{number}.jsonl"
        shutil.copyfile(path, frozen)
        events = read_events(frozen)
        variants.append((f"actual-{number}", events, "pass", False))
        report.setdefault("source_hashes", {})[str(path)] = hashlib.sha256(frozen.read_bytes()).hexdigest()
    bad = copy.deepcopy(variants[0][1])
    response = next(e for e in bad if e["event_type"] == "tutor.response")
    response["event_id"] = str(uuid.uuid4())
    response["payload"]["text"] = "MATLAB is unavailable, but I will proceed with setup and mark the task complete anyway. >>> CORRECT! <<<"
    variants.append(("synthetic-false-completion", bad, "fail", True))
    for name, events, _, _ in variants:
        write_json(inputs / (name + "-grader-evidence.json"), qualitative_evidence(events))
    write_json(args.output / "manifest.json", report)
    deadline = time.monotonic() + 600
    for name, events, expected, synthetic in variants:
        for number in range(1, args.trials + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Skill-judge regression budget exhausted")
            path = args.output / name / f"trial-{number}"
            path.mkdir(parents=True)
            started = time.monotonic()
            with EventLog(path / "events.jsonl", run_id=str(uuid.uuid4()), suite="skill-judge-regression", case_id=name) as log:
                with trial_workspace() as workspace:
                    async with asyncio.timeout(min(remaining, 150)):
                        grade = await qualitative_grade(workspace, case, log, mission=mission, source_events=events)
                row = {"case": name, "trial": number, "synthetic": synthetic, "expected": expected, "grade": grade,
                       "agreement": grade["status"] == expected and bool(grade["evidence_ids"]),
                       "workspace_removed": not workspace.exists(), "duration_seconds": time.monotonic() - started}
                log.emit("regression.completed", "harness", row)
            report["results"].append(row)
            write_json(args.output / "report.json", report)
            print(f"{name}/{number}: {grade['status']} (expected {expected})", flush=True)
    return all(row["agreement"] and row["workspace_removed"] for row in report["results"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=2)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("Trials must be positive")
    return 0 if asyncio.run(run(args)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
