"""Milestone 1 infrastructure proof; no mission-quality claims are made here."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import platform
import time
import uuid
from pathlib import Path

from .codex_runtime import prove_codex
from .events import EventLog, read_events, write_json
from .matlab_runtime import prove_matlab
from .workspace import trial_workspace


def error_details(error: BaseException) -> dict:
    result = {"type": type(error).__name__, "message": str(error)}
    if isinstance(error, BaseExceptionGroup):
        result["errors"] = [error_details(child) for child in error.exceptions]
    return result


async def run_smoke(output: Path, *, component: str, server: Path | None,
                    matlab_root: Path | None, model: str | None, timeout: float) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    run_id = str(uuid.uuid4())
    packages = {name: importlib.metadata.version(name)
                for name in ("openai-codex", "openai-codex-cli-bin", "mcp", "psutil")}
    manifest = {"schema_version": "1.0", "run_id": run_id, "suite": "infrastructure",
                "component": component, "python": platform.python_version(),
                "platform": platform.platform(), "packages": packages,
                "timeout_seconds": timeout, "requested_model": model}
    write_json(output / "manifest.json", manifest)
    started = time.monotonic()
    report = {"run_id": run_id, "status": "infrastructure_failed", "checks": {}}
    with EventLog(output / "events.jsonl", run_id=run_id,
                  suite="infrastructure", case_id="runtime-smoke") as log:
        log.emit("run.started", "harness", manifest)
        try:
            with trial_workspace() as root:
                log.emit("workspace.created", "harness", {"path": str(root)})
                try:
                    async with asyncio.timeout(timeout):
                        if component in ("all", "codex"):
                            print("Checking fresh Codex contexts and continuation...", flush=True)
                            report["checks"]["codex"] = await prove_codex(root, log, model=model)
                        if component in ("all", "matlab"):
                            if server is None or matlab_root is None:
                                raise ValueError("MATLAB checks require --matlab-server and --matlab-root")
                            print("Checking disposable MATLAB ownership and shared state...", flush=True)
                            report["checks"]["matlab"] = await prove_matlab(
                                root, log, server=server, matlab_root=matlab_root)
                except BaseException as error:
                    log.emit("run.error", "harness", error_details(error))
                    raise
            if root.exists():
                raise RuntimeError("Trial workspace was not removed")
            log.emit("workspace.removed", "harness", {"path": str(root)})
            report["workspace_removed"] = True
            report["status"] = "passed"
            log.emit("run.completed", "harness", report)
        except BaseException as error:
            report["error"] = error_details(error)
            log.emit("run.failed", "harness", report)
            if not isinstance(error, Exception):
                write_json(output / "report.json", report)
                raise
    report["duration_seconds"] = time.monotonic() - started
    report["event_count"] = len(read_events(output / "events.jsonl"))
    write_json(output / "report.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    smoke = subcommands.add_parser("smoke", help="Run the infrastructure proof")
    smoke.add_argument("--output", required=True, type=Path, help="New output directory")
    smoke.add_argument("--component", choices=("all", "codex", "matlab"), default="all")
    smoke.add_argument("--matlab-server", type=Path)
    smoke.add_argument("--matlab-root", type=Path)
    smoke.add_argument("--model", help="Default: preserve the user's configured model")
    smoke.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    if args.component in ("all", "matlab"):
        if args.matlab_server is None or not args.matlab_server.is_file():
            parser.error("--matlab-server must name the installed MATLAB MCP executable")
        if args.matlab_root is None or not args.matlab_root.is_dir():
            parser.error("--matlab-root must name the MATLAB installation directory")
    report = asyncio.run(run_smoke(args.output, component=args.component,
                                  server=args.matlab_server, matlab_root=args.matlab_root,
                                  model=args.model, timeout=args.timeout_seconds))
    print(f"{report['status']}: {args.output.resolve() / 'report.json'}", flush=True)
    if "error" in report:
        print(f"{report['error']['type']}: {report['error']['message']}", flush=True)
    return 0 if report["status"] == "passed" else 1
