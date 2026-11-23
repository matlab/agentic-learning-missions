"""Independent commands for infrastructure and tutor-skill evaluation."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .events import write_json
from .skill_suite import DEFAULT_CASES, comparison, render_report, run_suite, summarize
from .smoke import main as smoke_main


def finish_report(report):
    report["summaries"] = {
        version: summarize([r for r in report["results"] if r["configuration"] == version],
                           len(report["selected_cases"]) * report["trials_per_case"], report["grading_calibration"])
        for version in report["configurations"]}
    if report["trials_per_case"] < 2:
        for summary in report["summaries"].values():
            if summary["readiness"] == "meets_pilot_bar":
                summary["readiness"] = "insufficient_evidence"
    report["comparison"] = comparison(report)
    return report


def merge_runs(baseline, candidate):
    for key in ("schema_version", "suite", "case_spec_sha256", "fixture_hashes", "runner_sha256",
                "selected_cases", "trials_per_case", "packages", "grading_calibration"):
        if baseline.get(key) != candidate.get(key):
            raise ValueError(f"Cannot compare runs with different {key}")
    result = dict(candidate)
    result["configurations"] = {"baseline": baseline["configurations"]["candidate"],
                                "candidate": candidate["configurations"]["candidate"]}
    result["results"] = [dict(row, configuration=label)
                         for source, label in ((baseline, "baseline"), (candidate, "candidate"))
                         for row in source["results"] if row["configuration"] == "candidate"]
    return finish_report(result)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "smoke":
        return smoke_main(argv)
    if argv and argv[0] == "learner-sim":
        from .learner_cli import main as learner_main
        return learner_main(argv[1:])
    if argv and argv[0] == "combined":
        from .combined import main as combined_main
        return combined_main(argv[1:])
    parser = argparse.ArgumentParser(description="Independent tutor-skill evaluation harness")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("combined", help="Run both evaluators or compose saved runs (combined --help)")
    run = commands.add_parser("skill-eval")
    run.add_argument("--skill", required=True, type=Path)
    run.add_argument("--baseline", type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--cases-file", type=Path, default=DEFAULT_CASES)
    run.add_argument("--layer", choices=("all", "behavior", "live"), default="all")
    run.add_argument("--case", action="append", default=[])
    run.add_argument("--trials", type=int, default=2)
    run.add_argument("--model")
    run.add_argument("--timeout-seconds", type=float, default=3600)
    run.add_argument("--trial-timeout-seconds", type=float, default=600)
    run.add_argument("--matlab-server", type=Path)
    run.add_argument("--matlab-root", type=Path)
    run.add_argument("--toolbox-root", type=Path)
    rebuild = commands.add_parser("report")
    rebuild.add_argument("--run", required=True, type=Path)
    compare = commands.add_parser("compare")
    compare.add_argument("--baseline-run", required=True, type=Path)
    compare.add_argument("--candidate-run", required=True, type=Path)
    compare.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "skill-eval":
            if args.trials < 1 or min(args.timeout_seconds, args.trial_timeout_seconds) <= 0:
                parser.error("Trials and time budgets must be positive")
            for name in ("skill", "baseline", "matlab_server", "matlab_root", "toolbox_root", "cases_file"):
                value = getattr(args, name)
                if value is not None:
                    setattr(args, name, value.resolve())
            report = asyncio.run(run_suite(args))
            output = args.output
        elif args.command == "report":
            output = args.run.resolve()
            saved = output / "benchmark.json"
            if not saved.exists():
                saved = output / "manifest.json"
            report = json.loads(saved.read_text(encoding="utf-8"))
            if report.get("suite") == "combined":
                from .combined import rebuild, exit_code
                report = rebuild(output)
                print(f"Report: {output / 'report.md'}")
                return exit_code(report)
            if report.get("suite") == "learner-sim":
                from .learner_sim import rebuild
                report = rebuild(output)
                print(f"Report: {output / 'report.md'}")
                return 1 if report["summary"]["counts"]["fail"] else 2 if report["summary"]["counts"]["unknown"] or report["summary"]["counts"]["not_run"] else 0
            report = finish_report(report)
            render_report(output, report)
            write_json(output / "benchmark.json", report)
            write_json(output / "comparison.json", report["comparison"])
        else:
            baseline = json.loads((args.baseline_run / "benchmark.json").read_text(encoding="utf-8"))
            candidate = json.loads((args.candidate_run / "benchmark.json").read_text(encoding="utf-8"))
            if "combined" in (baseline.get("suite"), candidate.get("suite")):
                raise ValueError("Compare the corresponding component runs independently, not combined reports")
            if baseline.get("suite") == "learner-sim" or candidate.get("suite") == "learner-sim":
                from .learner_reports import compare as compare_learners
                compare_learners(args.baseline_run, args.candidate_run, args.output.resolve())
                print(f"Report: {args.output.resolve() / 'report.md'}")
                return 0
            report = merge_runs(baseline, candidate)
            output = args.output.resolve()
            sources = {"baseline": args.baseline_run.resolve(), "candidate": args.candidate_run.resolve()}
            report["source_runs"] = {key: str(path) for key, path in sources.items()}
            for row in report["results"]:
                trace = sources[row["configuration"]] / "candidate" / row["case_id"] / f"trial-{row['trial_number']}" / "events.jsonl"
                try:
                    row["evidence_path"] = Path(os.path.relpath(trace, output)).as_posix()
                except ValueError:
                    row["evidence_path"] = trace.as_posix()
            output.mkdir(parents=True, exist_ok=False)
            write_json(output / "benchmark.json", report)
            write_json(output / "comparison.json", report["comparison"])
            render_report(output, report)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"Report: {output.resolve() / 'report.md'}")
    return 1 if any(r["status"] == "fail" for r in report["results"]) else (
        2 if any(s["counts"]["unknown"] or s["counts"]["not_run"] for s in report["summaries"].values()) else 0)
