"""Draft mission specifications and reproducible persona schedules."""

import json
import random
from pathlib import Path

import yaml

from .events import write_json
from .skill_assets import digest, file_hashes

PROFILES = {
    "expert": "You meet the prerequisites. Work accurately and independently; ask about real ambiguity.",
    "casual": "You meet the prerequisites but sometimes skim or omit a step. Make real attempts and recover from feedback.",
    "naive": "You meet the prerequisites (basic MATLAB and creating, connecting and configuring Simulink blocks), but are new to this topic. Skim, try a simple interpretation, ask frequently, and make limited real attempts. Do not act like an expert.",
}
PROBES = {
    "root-inports-outports": [
        "Explain how time-stamped workspace data enters and leaves a Simulink model, and how you would check the sample interval.",
        "For a new noisy temperature signal, explain how you would test that a filter preserves a slow trend and attenuates fast noise, and compare the result with the input."],
    "continuous-and-discrete-time": [
        "Explain the difference between a continuous source and a sampled-and-held version of that source.",
        "A new sensor samples a smoothly changing signal every 0.2 seconds. Predict what its held output looks like between samples and how you would compare it with the original."],
}


def prepare_spec(mission, output):
    mission = mission.resolve()
    source = yaml.safe_load((mission / "mission.yaml").read_text(encoding="utf-8"))
    known = mission.name in PROBES
    spec = {"schema_version": "1.0", "suite": "learner-sim", "mission_name": mission.name,
            "mission_sha256": digest(file_hashes(mission)), "author_review": "pending_author_review",
            "grading_calibration": "pending_author_review", "learning_outcomes": source["learning_outcomes"],
            "observer": mission.name if known else None,
            "tasks": [{"id": task["id"], "expected_outcome": task["completion"]["description"],
                       "acceptable_alternatives": [s["check"] for s in task["completion"]["strategy"]],
                       "outcome_refs": task.get("outcome_refs", []),
                       "independent_check": f"observe_mission/{mission.name}/{task['id']}" if known else None}
                      for task in source["tasks"]],
            "mistakes": ["help_before_effort", "partial_attempt", "premature_done"],
            "expected_recovery": "Inspect actual work, give applicable guidance, and let the learner correct it.",
            "probes": PROBES.get(mission.name, ["Explain what you learned.", "Apply this idea to a different input."]),
            "rubric": "Assess technical correctness, read-only tutor boundaries, help relevance, recovery, persona fidelity, explanation and transfer separately. Cite evidence; missing evidence is unknown. No human-learning claim."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Specification output already exists")
    write_json(output, spec)
    return spec


def load_spec(path, mission):
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != "1.0" or spec.get("suite") != "learner-sim":
        raise ValueError("Unsupported learner specification")
    if spec.get("mission_name") != mission.name or spec.get("mission_sha256") != digest(file_hashes(mission)):
        raise ValueError("Specification does not match the exact mission snapshot")
    if spec.get("observer") not in PROBES:
        raise ValueError("No independent observer for this mission; prepare a draft for author review")
    source = yaml.safe_load((mission / "mission.yaml").read_text(encoding="utf-8"))
    if [t["id"] for t in spec["tasks"]] != [t["id"] for t in source["tasks"]]:
        raise ValueError("Specification tasks do not match the mission")
    return spec


def mistake_schedule(profile, tasks, seed):
    if profile == "expert":
        return []
    rng = random.Random(seed)
    chosen = rng.choice(tasks[:min(3, len(tasks))])["id"]
    if profile == "casual":
        return [{"task_id": chosen, "attempt": 1, "kind": "partial_attempt",
                 "instruction": "Make a real but incomplete attempt: omit one required element of the visible task. Do not fix it in this turn. Tell Ada you think you are done."}]
    return [{"task_id": chosen, "attempt": 1, "kind": "help_before_effort",
             "instruction": "Ask for a hint before taking any product action on this task."},
            {"task_id": chosen, "attempt": 2, "kind": "partial_attempt",
             "instruction": "Try only a simple part of the visible task or hint. Leave one requirement unmet and ask Ada for help. Do not complete the task in this turn."}]
