"""Run the learner grader on frozen evidence; no tutor/learner or MATLAB execution."""

import argparse
import asyncio
import json
from pathlib import Path

from mission_evals.calibration import publish, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--review-evidence", type=Path, help="Explicit author-reviewed evidence JSON, independent of checkout history")
    parser.add_argument("--additional-review", type=Path, action="append", default=[], help="Additional author-labeled task criteria")
    parser.add_argument("--unlabeled-trace", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-run", type=Path, help="Rebuild report summaries offline without regrading")
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--model")
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    parser.add_argument("--trial-timeout-seconds", type=float, default=300)
    args = parser.parse_args()
    if args.report_run:
        report = json.loads((args.report_run / "report.json").read_text(encoding="utf-8"))
        if report.get("suite") != "grader-calibration":
            parser.error("Expected a saved grader-calibration report")
        publish(args.report_run, report)
        print("Report:", args.report_run.resolve() / "report.md")
        return 0
    if not args.output:
        parser.error("--output is required unless rebuilding a saved report")
    if args.review_evidence is None:
        parser.error("--review-evidence is required for regrading; restore original source layout under --source-root")
    if args.trials < 1 or min(args.timeout_seconds, args.trial_timeout_seconds) <= 0:
        parser.error("Trials and time budgets must be positive")
    report = asyncio.run(run(args))
    print("Report:", args.output.resolve() / "report.md")
    if report["summary"]["trial_errors"] or report["summary"]["not_run"]:
        return 2
    return 0 if report["summary"]["reviewed_example_agreements"] == report["summary"]["expected_reviewed_example_comparisons"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
