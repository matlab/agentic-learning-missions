"""Offline accumulation and comparison with strict provenance checks."""

import json
import os
from pathlib import Path

from .events import read_events, write_json
from .learner_sim import render_report

COMPATIBILITY = ("schema_version", "suite", "mission_hashes", "specifications", "runner_sha256", "extension_sha256", "toolkit", "packages", "max_tasks")


def compatible(left, right, *, same_skill=True, partial_missions=False):
    for key in (*COMPATIBILITY, *(("skill",) if same_skill else ())):
        if partial_missions and key in ("mission_hashes", "specifications"):
            old, new = left.get(key, {}), right.get(key, {})
            if any(old[name] != new[name] for name in old.keys() & new.keys()):
                raise ValueError(f"Incompatible learner runs: different {key}")
            continue
        if left.get(key) != right.get(key):
            raise ValueError(f"Incompatible learner runs: different {key}")


def runtime_signature(row):
    return {role: {key: value for key, value in details.items() if key != "thread_id"} if isinstance(details, dict) else details
            for role, details in row.get("runtime", {}).items()}


def load_run(path):
    report = json.loads((path / "benchmark.json").read_text(encoding="utf-8"))
    if report.get("suite") != "learner-sim":
        raise ValueError("Expected a learner simulation run")
    for row in report["results"]:
        trace = (path / row["evidence_path"]).resolve()
        events = read_events(trace)
        if not events or events[0]["trial_id"] != row["trial_id"]:
            raise ValueError("Trial evidence does not match result")
    return report


def accumulate(paths, output):
    sources = [(path.resolve(), load_run(path)) for path in paths]
    report = dict(sources[0][1], results=[])
    seen = set()
    runtime = None
    for path, source in sources:
        compatible(report, source, partial_missions=True)
        for key in ("mission_hashes", "specifications"):
            report[key] = {**report.get(key, {}), **source.get(key, {})}
        for row in source["results"]:
            key = (row["mission_name"], row["profile"], row["seed"])
            if key in seen:
                raise ValueError("Duplicate mission/profile/seed; repeated seeds are not confirming trials")
            seen.add(key)
            signature = runtime_signature(row)
            if signature:
                if runtime is not None and runtime != signature:
                    raise ValueError("Cannot accumulate different resolved model/product runtimes")
                runtime = signature
            copied = dict(row)
            copied["evidence_path"] = Path(os.path.relpath(path / row["evidence_path"], output)).as_posix()
            report["results"].append(copied)
    report["profiles"] = sorted({profile for _, source in sources for profile in source["profiles"]})
    report["selected_missions"] = sorted({mission for _, source in sources for mission in source["selected_missions"]})
    report["trials_per_profile"] = max(2, max(sum(r["mission_name"] == m and r["profile"] == p for r in report["results"])
                                            for m in report["selected_missions"] for p in report["profiles"]))
    report["source_runs"] = [str(path) for path, _ in sources]
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", report)
    render_report(output, report)
    return report


def compare(baseline_path, candidate_path, output):
    baseline, candidate = load_run(baseline_path), load_run(candidate_path)
    compatible(baseline, candidate, same_skill=False)
    def indexed(report):
        return {(r["mission_name"], r["profile"], r["seed"]): r for r in report["results"]}
    old, new = indexed(baseline), indexed(candidate)
    rows = []
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)
        paired = bool(left and right and runtime_signature(left) and runtime_signature(left) == runtime_signature(right)
                      and not left.get("error") and not right.get("error"))
        rows.append({"mission": key[0], "profile": key[1], "seed": key[2], "comparable": paired,
                     "baseline": left["status"] if left else "not_run", "candidate": right["status"] if right else "not_run",
                     "baseline_grades": left.get("grades", []) if paired else [], "candidate_grades": right.get("grades", []) if paired else [],
                     "baseline_trace": str((baseline_path / left["evidence_path"]).resolve()) if left else None,
                     "candidate_trace": str((candidate_path / right["evidence_path"]).resolve()) if right else None})
    output.mkdir(parents=True, exist_ok=False)
    result = {"suite": "learner-sim", "identical_skill_inputs": baseline["skill"] == candidate["skill"],
              "baseline_summary": baseline["summary"], "candidate_summary": candidate["summary"], "trials": rows}
    write_json(output / "comparison.json", result)
    (output / "report.md").write_text("# Learner Simulation Comparison\n\n" +
        "\n".join(f"- {r['mission']}/{r['profile']}/{r['seed']}: {r['baseline']} → {r['candidate']}; comparable: {r['comparable']}." for r in rows) + "\n", encoding="utf-8")
    return result
