"""CLI for independently preparing and running learner simulations."""

import argparse
import asyncio
from pathlib import Path

from .learner_sim import run
from .learner_spec import PROFILES, prepare_spec


def main(argv):
    parser = argparse.ArgumentParser(description="Standalone mission learner simulator")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--mission", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    merge = commands.add_parser("accumulate")
    merge.add_argument("--run", type=Path, action="append", required=True)
    merge.add_argument("--output", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--mission", type=Path, action="append", required=True)
    execute.add_argument("--spec-dir", type=Path, required=True)
    execute.add_argument("--skill", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--profile", action="append", choices=tuple(PROFILES))
    execute.add_argument("--trials", type=int, default=2)
    execute.add_argument("--seed", type=int, default=73)
    execute.add_argument("--turns-per-task", type=int, default=12)
    execute.add_argument("--max-tasks", type=int, default=0)
    execute.add_argument("--timeout-seconds", type=float, default=3600)
    execute.add_argument("--trial-timeout-seconds", type=float, default=1200)
    execute.add_argument("--model")
    execute.add_argument("--matlab-server", type=Path, required=True)
    execute.add_argument("--matlab-root", type=Path, required=True)
    execute.add_argument("--toolbox-root", type=Path, required=True)
    execute.add_argument("--extension-file", type=Path, action="append", required=True)
    execute.add_argument("--toolkit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "accumulate":
            from .learner_reports import accumulate
            accumulate(args.run, args.output.resolve())
            print(f"Report: {args.output.resolve() / 'report.md'}")
            return 0
        if args.command == "prepare":
            prepare_spec(args.mission, args.output)
            print(f"Provisional specification: {args.output.resolve()}")
            return 0
        if min(args.trials, args.turns_per_task, args.timeout_seconds, args.trial_timeout_seconds) <= 0 or args.max_tasks < 0 or args.seed < 0:
            parser.error("Trials, turns and time budgets must be positive; seed/task limit must be nonnegative")
        args.profile = list(dict.fromkeys(args.profile or PROFILES))
        for name in ("mission", "extension_file"):
            setattr(args, name, [path.resolve() for path in getattr(args, name)])
        for name in ("spec_dir", "skill", "output", "matlab_server", "matlab_root", "toolbox_root", "toolkit_root"):
            setattr(args, name, getattr(args, name).resolve())
        report = asyncio.run(run(args))
        print(f"Report: {args.output / 'report.md'}")
        return 1 if report["summary"]["counts"]["fail"] else 2 if report["summary"]["counts"]["unknown"] or report["summary"]["counts"]["not_run"] else 0
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
