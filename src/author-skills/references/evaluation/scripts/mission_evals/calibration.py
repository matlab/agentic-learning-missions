"""Regrade saved learner traces without rerunning learners, tutors, or MATLAB."""

import asyncio
import hashlib
import importlib.metadata
import itertools
import json
from pathlib import Path
import shutil
import time
import uuid

from .events import EventLog, read_events, write_json
from .learner_grading import CATEGORIES, TASK_CRITERIA, criterion_grade, rubric_evidence, rubric_grade
from .skill_assets import digest, snapshot
from .smoke import error_details
from .workspace import trial_workspace


def source_record(path, source_root, expected_hash=None):
    source_root = source_root.resolve()
    path = path.resolve()
    if not path.is_relative_to(source_root.resolve()):
        raise ValueError("Trace must remain within the supplied source root")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_hash and actual_hash != expected_hash:
        raise ValueError("Trace fingerprint does not match author-reviewed evidence")
    events = read_events(path)
    if not events or events[0]["suite"] != "learner-sim":
        raise ValueError("Expected a nonempty learner-simulation trace")
    first = events[0]
    if (path.parents[3].name != "trials" or first["mission_name"] != path.parents[2].name
            or first["learner_type"] != path.parents[1].name):
        raise ValueError("Trace metadata does not match the mission/profile directory layout")
    if any(e["trial_id"] != first["trial_id"] for e in events):
        raise ValueError("Mixed trial identities in source trace")
    manifest_path = path.parents[4] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest["specifications"][first["mission_name"]]
    return {"id": first["mission_name"] + "--" + first["learner_type"] + "--" + actual_hash[:8],
            "source": path.relative_to(source_root).as_posix(), "sha256": actual_hash,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "mission_name": first["mission_name"], "profile": first["learner_type"],
            "specification": spec, "targets": [], "cohort": "author_reviewed_examples"}


def prepare_sources(review, source_root, unlabeled):
    sources, excluded = {}, []
    for case in review["cases"]:
        category = case.get("author_criterion", case["category"])
        task_id = case.get("author_task_id", case.get("task_id"))
        unresolved = case.get("follow_up") and case["follow_up"].get("status") != "resolved"
        supported = category in TASK_CRITERIA if task_id else category in CATEGORIES
        if unresolved or not supported or case.get("author_status") not in ("pass", "fail", "unknown"):
            excluded.append({"id": case["id"], "author_status": case.get("author_status"),
                             "reason": "Unresolved review or no matching qualitative category; excluded from agreement"})
            continue
        path = (source_root / case["source_trace"]).resolve()
        if str(path) not in sources:
            sources[str(path)] = source_record(path, source_root, case["source_sha256"])
        record = sources[str(path)]
        if record["sha256"] != case["source_sha256"]:
            raise ValueError("Conflicting fingerprints for a reviewed source")
        target = {"id": case["id"], "category": category, "author_status": case["author_status"]}
        if task_id:
            if task_id not in {t["id"] for t in record["specification"]["tasks"]}:
                raise ValueError("Reviewed task does not exist in the source specification")
            target.update(task_id=task_id, attribution_context=case.get("attribution_context", {}))
        record["targets"].append(target)
    for path in unlabeled:
        resolved = (source_root / path).resolve()
        if str(resolved) in sources:
            raise ValueError("A trace cannot have multiple cohorts or be repeated")
        record = source_record(resolved, source_root)
        record["cohort"] = "unlabeled_holdout"
        sources[str(resolved)] = record
    if not sources:
        raise ValueError("No eligible calibration sources")
    return list(sources.values()), excluded


def compare_labels(targets, grades):
    by_id = {(grade["id"], grade.get("task_id")): grade for grade in grades}
    results = []
    for target in targets:
        grade = by_id.get((target["category"], target.get("task_id")), {})
        results.append({**target, "grader_status": grade.get("status", "missing"),
                        "agreement": bool(grade.get("status") == target["author_status"] and grade.get("evidence_ids")),
                        "evidence_ids": grade.get("evidence_ids", [])})
    return results


def summary(report):
    comparisons = [comparison for row in report["results"] if "error" not in row for comparison in row.get("comparisons", [])]
    planned = len(report["sources"]) * report["trials_per_source"]
    errors = sum("error" in row for row in report["results"])
    pairs, stable, differences = 0, 0, []
    holdouts = {}
    for row in report["results"]:
        if row["cohort"] == "unlabeled_holdout" and "error" not in row:
            holdouts.setdefault(row.get("source_id"), []).append(row)
    for source, rows in holdouts.items():
        for first, second in itertools.combinations(rows, 2):
            old = {g["id"]: g for g in first.get("grades", [])}
            new = {g["id"]: g for g in second.get("grades", [])}
            for category in CATEGORIES:
                if not old.get(category, {}).get("evidence_ids") or not new.get(category, {}).get("evidence_ids"):
                    continue
                pairs += 1
                equal = old[category]["status"] == new[category]["status"]
                stable += equal
                if not equal:
                    differences.append({"source_id": source, "category": category,
                                        "trials": [first["trial_number"], second["trial_number"]],
                                        "statuses": [old[category]["status"], new[category]["status"]],
                                        "evidence_ids": [old[category]["evidence_ids"], new[category]["evidence_ids"]]})
    return {"reviewed_example_agreements": sum(c["agreement"] for c in comparisons),
            "reviewed_example_comparisons": len(comparisons),
            "expected_reviewed_example_comparisons": sum(len(s["targets"]) for s in report["sources"]) * report["trials_per_source"],
            "unlabeled_holdout_trials": sum(row["cohort"] == "unlabeled_holdout" and "error" not in row for row in report["results"]),
            "trial_errors": errors, "not_run": planned - len(report["results"]),
            "unlabeled_category_agreements": stable, "unlabeled_category_pairs": pairs,
            "unlabeled_disagreements": differences,
            "qualification": "provisional",
            "limitation": "Reviewed examples informed the rubric. Their agreement is not held-out accuracy; unlabeled traces cannot establish accuracy. No automatic author approval or regrading of source results."}


def publish(output, report):
    report["summary"] = summary(report)
    write_json(output / "report.json", report)
    s = report["summary"]
    lines = ["# Saved-trace grader calibration", "",
             f"Reviewed-example agreement: {s['reviewed_example_agreements']}/{s['reviewed_example_comparisons']} comparisons ({s['expected_reviewed_example_comparisons']} planned).",
             f"Unlabeled holdout trials: {s['unlabeled_holdout_trials']}. Errors: {s['trial_errors']}. Not run: {s['not_run']}.",
             f"Unlabeled-category repeatability: {s['unlabeled_category_agreements']}/{s['unlabeled_category_pairs']} cited verdict pairs (repeatability, not accuracy).",
             "", s["limitation"], "",
             "| Source | Trial | Cohort | Result | Audit |", "|---|---|---|---|---|"]
    for row in report["results"]:
        value = "infrastructure error" if "error" in row else ("; ".join(f"{c['id']}: {c['grader_status']} / author {c['author_status']}" for c in row["comparisons"]) or "Graded; no author reference label")
        lines.append(f"| {row['source_id']} | {row['trial_number']} | {row['cohort']} | {value} | [trace](<{row['audit_path']}>) |")
    lines.extend(["", "## Excluded review targets", ""])
    lines.extend(f"- {item['id']}: {item['reason']}. Author label retained: {item['author_status']}." for item in report["excluded"])
    if s["unlabeled_disagreements"]:
        lines.extend(["", "## Unlabeled disagreements for author calibration", ""])
        lines.extend(f"- {item['source_id']}: {item['category']} differed across trials {item['trials']}: {item['statuses']}. See the per-trial grades and source evidence before selecting a reference label."
                     for item in s["unlabeled_disagreements"])
    lines.extend(["", "Frozen source JSONL and grader inputs are under inputs/. New grader calls use fresh, tool-free contexts and disposable workspaces. Original source events and grades are unchanged.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def run(args):
    source_root = args.source_root.resolve()
    review = json.loads(args.review_evidence.read_text(encoding="utf-8"))
    for path in getattr(args, "additional_review", []):
        additional = json.loads(path.read_text(encoding="utf-8"))
        review["cases"].extend(additional["cases"])
        review.setdefault("additional_review_records", []).append(additional)
    if len({case["id"] for case in review["cases"]}) != len(review["cases"]):
        raise ValueError("Review target IDs must be unique")
    sources, excluded = prepare_sources(review, source_root, args.unlabeled_trace)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    write_json(inputs / "review-targets.json", review)
    runner = snapshot(Path(__file__).parent, inputs / "grader")
    for source in sources:
        destination = inputs / (source["id"] + ".jsonl")
        shutil.copyfile(source_root / source["source"], destination)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != source["sha256"]:
            raise RuntimeError("Source changed while freezing calibration inputs")
        write_json(inputs / (source["id"] + "-grader-evidence.json"), rubric_evidence(read_events(destination)))
    report = {"schema_version": "1.0", "suite": "grader-calibration", "run_id": str(uuid.uuid4()),
              "sources": sources, "excluded": excluded, "trials_per_source": args.trials,
              "runner": runner, "review_sha256": digest(review), "requested_model": args.model,
              "packages": {name: importlib.metadata.version(name) for name in ("openai-codex", "mcp", "PyYAML")},
              "budget_seconds": args.timeout_seconds, "trial_budget_seconds": args.trial_timeout_seconds, "results": []}
    write_json(output / "manifest.json", report)
    publish(output, report)
    deadline = time.monotonic() + args.timeout_seconds
    for source in sources:
        for number in range(1, args.trials + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            trial = output / source["id"] / f"trial-{number}"
            trial.mkdir(parents=True)
            row = {"source_id": source["id"], "trial_number": number, "cohort": source["cohort"],
                   "comparisons": [], "audit_path": (trial / "events.jsonl").relative_to(output).as_posix()}
            started = time.monotonic()
            print(f"Grading {source['id']}/trial-{number} ({source['cohort']})...", flush=True)
            with EventLog(trial / "events.jsonl", run_id=report["run_id"], suite="grader-calibration",
                          case_id=source["id"], trial_id=str(uuid.uuid4()), mission_name=source["mission_name"]) as log:
                log.emit("calibration.started", "harness", {"source": source["source"], "sha256": source["sha256"]})
                try:
                    with trial_workspace() as root:
                        async with asyncio.timeout(min(remaining, args.trial_timeout_seconds)):
                            events = read_events(inputs / (source["id"] + ".jsonl"))
                            grades, proxies, runtime = await rubric_grade(root, log, source["specification"], source["profile"], args.model,
                                source_events=events)
                            criterion_runtimes = []
                            for index, target in enumerate(source["targets"]):
                                if not target.get("task_id"):
                                    continue
                                log.set_task(target["task_id"])
                                grade, details = await criterion_grade(root / f"criterion-{index}", log, source["specification"],
                                    source["profile"], args.model, events, target["category"], target["task_id"], target["attribution_context"])
                                grades.append(grade)
                                criterion_runtimes.append({"criterion": target["category"], "task_id": target["task_id"], **details})
                            row.update(grades=grades, learning_proxies=proxies, runtime=runtime,
                                       criterion_runtimes=criterion_runtimes,
                                       comparisons=compare_labels(source["targets"], grades))
                    row["workspace_removed"] = not root.exists()
                    log.emit("calibration.completed", "harness", row)
                except Exception as error:
                    row["error"] = error_details(error)
                    log.emit("calibration.error", "harness", row["error"])
            row["duration_seconds"] = time.monotonic() - started
            row["event_count"] = len(read_events(log.path))
            write_json(trial / "grading.json", row)
            report["results"].append(row)
            publish(output, report)
            print(f"  {'error' if 'error' in row else 'graded'} ({row['duration_seconds']:.1f}s)", flush=True)
    return report
