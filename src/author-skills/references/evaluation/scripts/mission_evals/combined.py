"""Optional orchestration and read-only composition of independent evaluations."""

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from .events import read_events, write_json
from .skill_suite import DEFAULT_CASES, load_cases, run_suite

SUITES = {"skill-eval": "tutor-skill", "learner-sim": "learner-sim"}
LIMITS = [
    "Component results and readiness are independent; no aggregate quality score is calculated.",
    "Composition does not establish baseline/candidate compatibility or causal effects of coupled changes.",
    "Reviewed-label agreement is calibration evidence, not accuracy on unseen traces. Preserve provisional qualification.",
    "Reviewed boundary unknowns are completed author decisions. SDI verification pass does not replace the historical independent outcome unknown.",
    "Simulated learning proxies do not establish human learning or desktop usability. No automatic mission or tutor edits.",
]


def link(path, output):
    try:
        return Path(os.path.relpath(path, output)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(path, label, output):
    """Read source evidence without rebuilding or changing historical reports."""
    saved = path / "benchmark.json"
    if not saved.is_file():
        saved = path / "manifest.json"
    report = json.loads(saved.read_text(encoding="utf-8"))
    if report.get("schema_version") != "1.0" or report.get("suite") != SUITES[label]:
        raise ValueError(f"Expected a {SUITES[label]} run at {path}")
    report = copy.deepcopy(report)
    known = {row["trial_id"] for row in report["results"]}
    # Recover published grades omitted by an interrupted benchmark write. Never grade anew.
    pattern = "*/*/trial-*/events.jsonl" if label == "skill-eval" else "trials/*/*/*/events.jsonl"
    recovered = False
    for trace in sorted(path.glob(pattern)):
        events = read_events(trace)
        if not events:
            raise ValueError(f"Empty trial evidence: {trace}")
        if events[0]["trial_id"] in known:
            continue
        grading = trace.parent / "grading.json"
        if grading.is_file():
            row = json.loads(grading.read_text(encoding="utf-8"))
        else:
            row = {"trial_id": events[0]["trial_id"], "status": "unknown", "grades": [],
                   "error": "Interrupted before grading was published", "runtime": {}}
        if row["trial_id"] != events[0]["trial_id"]:
            raise ValueError(f"Trial evidence does not match grading: {trace}")
        if label == "skill-eval":
            row.update(configuration=trace.parts[-4], case_id=trace.parts[-3],
                       trial_number=int(trace.parent.name.removeprefix("trial-")))
        else:
            row.update(mission_name=trace.parts[-4], profile=trace.parts[-3],
                       seed=int(trace.parent.name.removeprefix("seed-")))
        row["evidence_path"] = trace.relative_to(path).as_posix()
        report["results"].append(row)
        known.add(row["trial_id"])
        recovered = True
    evidence = []
    for row in report["results"]:
        relative = row.get("evidence_path")
        if relative is None and label == "skill-eval":
            relative = f"{row['configuration']}/{row['case_id']}/trial-{row['trial_number']}/events.jsonl"
        if not relative:
            raise ValueError("Result has no evidence path")
        trace = (path / relative).resolve()
        events = read_events(trace)
        if not events or events[0]["trial_id"] != row["trial_id"]:
            raise ValueError(f"Trial evidence does not match result: {trace}")
        evidence.append({"trial_id": row["trial_id"], "trace": link(trace, output),
                         "sha256": fingerprint(trace), "event_count": len(events)})
    if label == "skill-eval":
        if recovered or "summaries" not in report:
            from .cli import finish_report
            finish_report(report)
        summaries = report["summaries"]
    else:
        if recovered or "summary" not in report:
            from .learner_sim import readiness
            report["summary"] = readiness(report)
        summaries = {"candidate": report["summary"]}
    code = 1 if any(r["status"] == "fail" for r in report["results"]) else (
        2 if any(s["counts"]["unknown"] or s["counts"]["not_run"] for s in summaries.values()) else 0)
    return {"state": "available", "exit_code": code, "source": link(path, output),
            "source_file": link(saved, output), "source_sha256": fingerprint(saved),
            "report_link": link(path / "report.md", output) if (path / "report.md").is_file() else None,
            "recovered_partial_evidence": recovered, "summaries": summaries,
            "evidence": evidence, "source_report": report}


def exit_code(report):
    codes = [part["exit_code"] for part in report["components"].values()]
    return 1 if 1 in codes else 2 if 2 in codes else 0


def render(output, report):
    lines = ["# Combined Evaluation", "", f"Mode: {report['mode']}. Execution exit code: {exit_code(report)}.",
             "", *[f"- {limit}" for limit in LIMITS], ""]
    for label, part in report["components"].items():
        lines.extend([f"## {label}", "", f"Evidence state: {part['state']}. Execution exit code: {part['exit_code']}.", ""])
        if part.get("error"):
            lines.extend([f"Execution/evidence limitation: {part['error']}", ""])
        if part.get("report_link"):
            lines.extend([f"[Original component report](<{part['report_link']}>)", ""])
        for name, summary in part.get("summaries", {}).items():
            lines.append(f"- {name}: **{summary['readiness']}**; `{json.dumps(summary)}`")
        source = part.get("source_report", {})
        provenance = {key: source[key] for key in ("configurations", "skill", "runner_sha256", "packages",
                      "mission_hashes", "grading_calibration", "specifications") if key in source}
        if provenance:
            # Keep full specification/grade details in JSON; the Markdown links the exact preserved source.
            lines.extend(["", f"[Source data](<{part['source_file']}>) SHA-256: `{part['source_sha256']}`.",
                          "", "Snapshot and runtime identifiers (different suites use different runner hash scopes):", "",
                          "```json", json.dumps({k: v for k, v in provenance.items() if k not in ("specifications", "mission_hashes")}, indent=2), "```", ""])
        for row in source.get("results", []):
            trace = next(item["trace"] for item in part["evidence"] if item["trial_id"] == row["trial_id"])
            lines.append(f"- {row['trial_id']}: **{row['status']}**; [trace](<{trace}>); runtime `{json.dumps(row.get('runtime', {}))}`.")
        lines.append("")
    lines.extend(["Full component results, grades, limitations, specifications, and provenance are preserved in `benchmark.json`.", ""])
    write_json(output / "benchmark.json", report)
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def rebuild(output):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("suite") != "combined" or manifest.get("schema_version") != "1.0":
        raise ValueError("Expected a combined manifest")
    previous_path = output / "benchmark.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.is_file() else {}
    report = dict(manifest, components={})
    for label, source in manifest["sources"].items():
        try:
            part = component((output / source).resolve(), label, output)
        except (OSError, ValueError, KeyError) as error:
            part = copy.deepcopy(previous.get("components", {}).get(label, {}))
            part.update(state="unavailable", exit_code=1 if part.get("exit_code") == 1 else 2,
                        source=source, error=str(error))
        if label in manifest.get("errors", {}):
            part["error"] = manifest["errors"][label]
            if part["exit_code"] != 1:
                part["exit_code"] = 2
        report["components"][label] = part
    render(output, report)
    return report


def compose(skill_run, learner_run, output):
    # Validate before creating output. Original files are never changed.
    if any(output.resolve().is_relative_to(path.resolve()) for path in (skill_run, learner_run)):
        raise ValueError("Combined output must be outside source run folders")
    parts = {label: component(path.resolve(), label, output) for label, path in
             (("skill-eval", skill_run), ("learner-sim", learner_run))}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": "1.0", "suite": "combined", "run_id": str(uuid.uuid4()),
                "mode": "saved", "sources": {label: part["source"] for label, part in parts.items()},
                "limitations": LIMITS}
    write_json(output / "manifest.json", manifest)
    report = dict(manifest, components=parts)
    render(output, report)
    return report


async def run(args):
    from .learner_sim import run as learner_run
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + args.timeout_seconds
    manifest = {"schema_version": "1.0", "suite": "combined", "run_id": str(uuid.uuid4()),
                "mode": "fresh", "sources": {label: label for label in SUITES}, "errors": {},
                "timeout_seconds": args.timeout_seconds, "limitations": LIMITS,
                "request": {k: [str(p) for p in v] if isinstance(v, list) else str(v) if isinstance(v, Path) else v
                            for k, v in vars(args).items()}}
    write_json(output / "manifest.json", manifest)
    rebuild(output)
    shared = dict(skill=args.skill, model=args.model, matlab_server=args.matlab_server,
                  matlab_root=args.matlab_root, toolbox_root=args.toolbox_root,
                  invocation_deadline=deadline, stop_file=output / "STOP")
    skill_args = SimpleNamespace(**shared, baseline=args.skill_baseline, cases_file=args.cases_file,
                                 layer=args.layer, case=args.case, trials=args.skill_trials,
                                 trial_timeout_seconds=args.skill_trial_timeout_seconds)
    learner_args = SimpleNamespace(**shared, mission=args.mission, spec_dir=args.spec_dir,
                                   profile=args.profile, trials=args.learner_trials, seed=args.seed,
                                   turns_per_task=args.turns_per_task, max_tasks=args.max_tasks,
                                   extension_file=args.extension_file, toolkit_root=args.toolkit_root,
                                   trial_timeout_seconds=args.learner_trial_timeout_seconds)
    try:
        for label, execute, options in (("skill-eval", run_suite, skill_args), ("learner-sim", learner_run, learner_args)):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or shared["stop_file"].exists() or asyncio.current_task().cancelling():
                manifest["errors"][label] = "Not started: cancellation, STOP request, or invocation budget exhausted"
                continue
            options.output = output / label
            options.timeout_seconds = remaining
            try:
                await execute(options)
            except Exception as error:
                manifest["errors"][label] = f"{type(error).__name__}: {error}"
            write_json(output / "manifest.json", manifest)
            rebuild(output)
    except (asyncio.CancelledError, KeyboardInterrupt):
        manifest["errors"][label] = "Execution cancelled; partial evidence retained"
    finally:
        write_json(output / "manifest.json", manifest)
        report = rebuild(output)
    return report


def parser():
    result = argparse.ArgumentParser(description="Run both independent evaluators or compose saved evidence")
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--skill-run", type=Path)
    result.add_argument("--learner-run", type=Path)
    # Suppress fresh defaults until mode validation, so even explicit default-valued arguments cannot mix modes.
    fresh = result.add_argument_group("fresh execution", argument_default=argparse.SUPPRESS)
    for name in ("skill", "skill-baseline", "cases-file", "spec-dir", "matlab-server", "matlab-root", "toolbox-root", "toolkit-root"):
        fresh.add_argument("--" + name, type=Path)
    for name in ("mission", "extension-file"):
        fresh.add_argument("--" + name, type=Path, action="append")
    fresh.add_argument("--case", action="append")
    fresh.add_argument("--profile", action="append", choices=("expert", "casual", "naive"))
    fresh.add_argument("--layer", choices=("all", "behavior", "live"))
    fresh.add_argument("--model")
    for name in ("skill-trials", "learner-trials", "seed", "turns-per-task", "max-tasks"):
        fresh.add_argument("--" + name, type=int)
    for name in ("timeout-seconds", "skill-trial-timeout-seconds", "learner-trial-timeout-seconds"):
        fresh.add_argument("--" + name, type=float)
    return result


def main(argv):
    command = parser()
    args = command.parse_args(argv)
    args.output = args.output.resolve()
    try:
        if args.skill_run or args.learner_run:
            if not (args.skill_run and args.learner_run) or set(vars(args)) - {"output", "skill_run", "learner_run"}:
                raise ValueError("Saved composition requires both --skill-run and --learner-run and no fresh execution options")
            report = compose(args.skill_run, args.learner_run, args.output)
        else:
            required = ("skill", "mission", "spec_dir", "matlab_server", "matlab_root", "toolbox_root", "extension_file", "toolkit_root")
            if any(not getattr(args, key, None) for key in required):
                raise ValueError("Fresh execution requires " + ", ".join("--" + key.replace("_", "-") for key in required))
            defaults = dict(skill_baseline=None, cases_file=DEFAULT_CASES, layer="all", case=[],
                            profile=["expert", "casual", "naive"], skill_trials=2, learner_trials=2,
                            seed=73, turns_per_task=12, max_tasks=0, model=None, timeout_seconds=3600,
                            skill_trial_timeout_seconds=600, learner_trial_timeout_seconds=1200)
            for key, value in defaults.items():
                if not hasattr(args, key):
                    setattr(args, key, value)
            budgets = (args.timeout_seconds, args.skill_trial_timeout_seconds, args.learner_trial_timeout_seconds)
            if not all(math.isfinite(v) for v in budgets) or min(args.skill_trials, args.learner_trials, args.turns_per_task, args.timeout_seconds,
                   args.skill_trial_timeout_seconds, args.learner_trial_timeout_seconds) <= 0 or min(args.seed, args.max_tasks) < 0:
                raise ValueError("Trials, turns and budgets must be positive; seed and task limit must be nonnegative")
            from .learner_spec import load_spec
            from .skill_assets import skill_metadata
            for key, value in vars(args).items():
                if isinstance(value, Path):
                    setattr(args, key, value.resolve())
            args.profile = list(dict.fromkeys(args.profile))
            args.mission = [path.resolve() for path in args.mission]
            args.extension_file = [path.resolve() for path in args.extension_file]
            if len({p.name for p in args.mission}) != len(args.mission):
                raise ValueError("Mission folder names must be unique")
            for path in args.mission:
                load_spec(args.spec_dir / f"{path.name}.json", path)
            load_cases(args.cases_file, args.layer, args.case)
            skill_metadata(args.skill)
            if args.skill_baseline:
                skill_metadata(args.skill_baseline)
            for path in [args.matlab_server, args.matlab_root, args.toolbox_root, args.toolkit_root, *args.extension_file]:
                if not path.exists():
                    raise ValueError(f"Required runtime path is unavailable: {path}")
            report = asyncio.run(run(args))
    except (ValueError, OSError, KeyError) as error:
        command.error(str(error))
    print(f"Report: {args.output / 'report.md'}")
    return exit_code(report)
