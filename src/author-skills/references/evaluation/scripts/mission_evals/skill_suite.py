"""Independent tutor-skill evaluation; no learner-simulator dependency."""

import asyncio
import importlib.metadata
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from openai_codex import Sandbox, SkillInput, TextInput

from .codex_runtime import agent_client, capture_turn
from .events import EventLog, read_events, write_json
from .matlab_runtime import owned_matlab
from .skill_assets import (digest, file_hashes, prepare_behavior_workspace, prepare_live_workspace,
                           protected_hashes, skill_metadata, snapshot)
from .skill_bridge import ScalarBackend, TutorBridge, serve_bridge
from .skill_grading import KINDS, deterministic_grades, grade_status, qualitative_grade
from .smoke import error_details
from .workspace import trial_workspace

DEFAULT_CASES = Path(__file__).resolve().parents[2] / "evals/evals.json"


def verify_fixture_state(state, expected):
    if state["sample_rate"] != expected or state["protected_sentinel"] != 2718:
        raise RuntimeError("Scripted fixture state was not established; the tutor cannot be graded against it")


def load_cases(path, layer, selected):
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0" or document.get("skill_name") != "mission-tutoring":
        raise ValueError("Unsupported skill-eval case specification")
    ids = set()
    for case in document["evals"]:
        if case["id"] in ids or not case["id"].replace("-", "").isalnum():
            raise ValueError("Case IDs must be unique and contain letters, digits, or hyphens")
        ids.add(case["id"])
        if case["backend"] not in ("behavior", "live") or case["invocation"] not in ("explicit", "implicit"):
            raise ValueError("Unsupported backend or invocation mode")
        if not case["steps"] or case["prompt"] != case["steps"][0]["message"]:
            raise ValueError("The first scripted step must match the case prompt")
        step_ids = [step["id"] for step in case["steps"]]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("Step IDs must be unique within a case")
        for step in case["steps"]:
            if step["sample_rate"] is not None and type(step["sample_rate"]) not in (int, float):
                raise ValueError("Scalar fixture states must be numbers or null")
            errors = step.get("tool_errors", {})
            if (not isinstance(errors, dict) or set(errors) - {"evaluate_matlab_code", "detect_matlab_toolboxes"}
                    or any(not isinstance(message, str) or not message.strip() for message in errors.values())
                    or (errors and case["backend"] != "behavior")):
                raise ValueError("Scripted tool errors require named behavior tools and nonempty messages")
        for assertion in case["assertions"]:
            if assertion["kind"] not in KINDS or ("step" in assertion and assertion["step"] not in step_ids):
                raise ValueError("Unknown assertion kind or step")
        fixture = (path.parent / case["fixture"]).resolve()
        if not fixture.is_relative_to(path.parent.resolve()) or not (fixture / "mission.yaml").is_file():
            raise ValueError("Fixture must be inside the case-specification directory")
    if set(selected) - ids:
        raise ValueError(f"Unknown selected cases: {sorted(set(selected) - ids)}")
    cases = [case for case in document["evals"] if (layer == "all" or case["backend"] == layer)
             and (not selected or case["id"] in selected)]
    if not cases:
        raise ValueError("No cases selected")
    return document, cases


@asynccontextmanager
async def case_environment(root, case, fixture, skill, log, server, matlab_root, toolbox_root):
    if case["backend"] == "live":
        async with owned_matlab(root, log, server=server, matlab_root=matlab_root) as (broker, state):
            workspace = root / "learner-workspace"
            copied = await prepare_live_workspace(broker, workspace, fixture, skill, toolbox_root)
            yield workspace, copied, ScalarBackend(broker), {"release": state["release"]}
    else:
        workspace = root / "workspace"
        copied = prepare_behavior_workspace(workspace, fixture, skill)
        yield workspace, copied, ScalarBackend(), {"release": "controlled-R2026b"}


async def run_trial(output, case, fixture, skill, *, server, matlab_root, toolbox_root, model, timeout):
    output.mkdir(parents=True)
    trial_id = str(uuid.uuid4())
    started = time.monotonic()
    report = {"trial_id": trial_id, "case_id": case["id"], "backend": case["backend"],
              "status": "unknown", "grades": []}
    if case.get("review_context"):
        report["review_context"] = case["review_context"]
    with EventLog(output / "events.jsonl", run_id=trial_id, suite="tutor-skill",
                  case_id=case["id"], mission_name=fixture.name) as log:
        log.emit("trial.started", "harness", {"case_id": case["id"], "backend": case["backend"]})
        try:
            with trial_workspace() as root:
                async with asyncio.timeout(timeout):
                    async with case_environment(root, case, fixture, skill, log, server, matlab_root, toolbox_root) as (workspace, copied, backend, product):
                        before_bundle = protected_hashes(workspace)
                        bridge = TutorBridge(workspace, backend, log)
                        responses, states = [], []
                        explicit_event = None
                        metadata = skill_metadata(copied)
                        instructions = ("Use read_workspace_file for files in this workspace. Its paths may be relative "
                                        "to the workspace root. Available skill (metadata only; read it when applicable):\n"
                                        f"{metadata['name']}: {metadata['description']}\nPath: {copied / 'SKILL.md'}")
                        async with serve_bridge(bridge) as (servers, environment):
                            async with agent_client(root / "tutor-runtime", workspace, log, model=model,
                                                    mcp_servers=servers, extra_env=environment) as client:
                                thread = await client.thread_start(cwd=str(workspace), ephemeral=True,
                                                                   sandbox=Sandbox.read_only,
                                                                   developer_instructions=instructions)
                                for index, step in enumerate(case["steps"]):
                                    bridge.step_id = step["id"]
                                    log.set_task("t01" if index > 0 else None)
                                    backend.configure_step(step)
                                    await backend.set_state(step["sample_rate"])
                                    before = await backend.state()
                                    verify_fixture_state(before, step["sample_rate"])
                                    log.emit("driver.step", "driver", step)
                                    inputs = None
                                    if index == 0 and case["invocation"] == "explicit":
                                        inputs = [TextInput(step["message"]), SkillInput("mission-tutoring", str(copied / "SKILL.md"))]
                                        explicit_event = log.emit("skill.invoked", "harness", {
                                            "mechanism": "Codex SkillInput", "path": str(copied / "SKILL.md")})
                                    text = await capture_turn(thread, step["message"], "tutor", log,
                                                              inputs=inputs, allow_tools=True,
                                                              include_commentary=True,
                                                              on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                    event_id = log.emit("tutor.response", "tutor", {"step_id": step["id"], "text": text},
                                                        turn_id=bridge.turn_id)
                                    responses.append({"step_id": step["id"], "text": text, "event_id": event_id})
                                    after = await backend.state()
                                    observation = {"step_id": step["id"], "before": before, "after": after}
                                    observation["event_id"] = log.emit("state.observed", "harness", observation,
                                                                        turn_id=bridge.turn_id)
                                    states.append(observation)
                                details = (await thread.read()).thread
                                report["runtime"] = {"model": details.model, "model_provider": details.model_provider,
                                                     "reasoning_effort": details.reasoning_effort,
                                                     "cli_version": details.cli_version, **product}
                        bundle_ok = before_bundle == protected_hashes(workspace)
                        bundle_event = log.emit("bundle.checked", "harness", {"unchanged": bundle_ok})
                        report["grades"] = deterministic_grades(case, responses, bridge.calls, states,
                            explicit_event=explicit_event, bundle_event=bundle_event, bundle_unchanged=bundle_ok)
                    mission = yaml.safe_load((fixture / "mission.yaml").read_text(encoding="utf-8"))
                    report["grades"].append(await qualitative_grade(root, case, log, model=model, mission=mission))
                    report["status"] = grade_status(report["grades"])
            report["workspace_removed"] = not root.exists()
            log.emit("trial.completed", "harness", report)
        except Exception as error:
            report["error"] = error_details(error)
            # Deterministic failures already observed remain failures even when
            # a later grader or infrastructure step cannot complete.
            report["status"] = "fail" if grade_status(report["grades"]) == "fail" else "unknown"
            log.emit("trial.error", "harness", report["error"])
    report["duration_seconds"] = time.monotonic() - started
    report["event_count"] = len(read_events(output / "events.jsonl"))
    write_json(output / "grading.json", report)
    return report


def summarize(results, planned, calibration):
    counts = {status: sum(row["status"] == status for row in results) for status in ("pass", "fail", "unknown")}
    counts["not_run"] = planned - len(results)
    readiness = "does_not_meet_pilot_bar" if counts["fail"] else "insufficient_evidence"
    if not counts["fail"] and not counts["unknown"] and not counts["not_run"] and calibration == "reviewed":
        readiness = "meets_pilot_bar"
    return {"counts": counts, "readiness": readiness, "grading_calibration": calibration}


def comparison(report):
    if "baseline" not in report["configurations"]:
        return {"status": "no_baseline"}
    rows = report["results"]
    grouped = {version: {(r["case_id"], r["trial_number"]): r for r in rows if r["configuration"] == version}
               for version in ("baseline", "candidate")}
    entries = []
    for key in sorted(grouped["baseline"].keys() | grouped["candidate"].keys()):
        old, new = grouped["baseline"].get(key), grouped["candidate"].get(key)
        compatible = bool(old and new and old.get("runtime") and old.get("runtime") == new.get("runtime")
                          and "error" not in old and "error" not in new)
        old_grades = {g["id"]: g["status"] for g in old.get("grades", [])} if old else {}
        new_grades = {g["id"]: g["status"] for g in new.get("grades", [])} if new else {}
        changes = [{"assertion": name, "baseline": old_grades.get(name, "unknown"),
                    "candidate": new_grades.get(name, "unknown")}
                   for name in sorted(old_grades.keys() | new_grades.keys())
                   if old_grades.get(name) != new_grades.get(name)] if compatible else []
        entries.append({"case_id": key[0], "trial_number": key[1], "comparable": compatible,
                        "baseline": old["status"] if old else "not_run",
                        "candidate": new["status"] if new else "not_run", "assertion_changes": changes})
    return {"status": "compared", "identical_skill_inputs":
            report["configurations"]["baseline"]["sha256"] == report["configurations"]["candidate"]["sha256"],
            "trials": entries}


def render_report(output, report):
    lines = ["# Tutor-Skill Evaluation", "", f"Grading calibration: {report['grading_calibration']}.",
             "", "| Configuration | Case | Trial | Backend | Result | Evidence |", "|---|---|---|---|---|---|"]
    for row in report["results"]:
        trace = row.get("evidence_path", f"{row['configuration']}/{row['case_id']}/trial-{row['trial_number']}/events.jsonl")
        lines.append(f"| {row['configuration']} | {row['case_id']} | {row['trial_number']} | {row['backend']} | {row['status']} | [trace](<{trace}>) |")
    for version, summary in report["summaries"].items():
        lines.extend(["", f"{version}: **{summary['readiness']}**. Counts: `{json.dumps(summary['counts'])}`."])
    contexts = {row["case_id"]: row["review_context"] for row in report["results"] if row.get("review_context")}
    if contexts:
        lines.extend(["", "## Scenario context", ""])
        for case_id, context in contexts.items():
            lines.append(f"- {case_id}: {context['purpose']} Fixture condition: {context['fixture_condition']} Author review: {context['author_review']}.")
    lines.extend(["", "## Findings", ""])
    for row in report["results"]:
        for grade in row["grades"]:
            if grade["status"] != "pass":
                lines.append(f"- {row['configuration']}/{row['case_id']}/{row['trial_number']}: {grade['id']} = {grade['status']}. Evidence: {', '.join(grade['evidence_ids']) or 'missing'}. {grade.get('reason', '')}")
        if "error" in row:
            lines.append(f"- {row['configuration']}/{row['case_id']}/{row['trial_number']}: execution/grading incomplete; see grading.json for the recorded error.")
    lines.extend(["", "No learner simulator was run. Controlled observations and live product evidence are reported separately.",
                  "Rubric judgments remain provisional until author calibration. Missing or timed-out trials are not passes.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def run_suite(args):
    document, cases = load_cases(args.cases_file.resolve(), args.layer, args.case)
    if any(case["backend"] == "live" for case in cases) and (not args.matlab_server or not args.matlab_root or not args.toolbox_root):
        raise ValueError("Live cases require --matlab-server, --matlab-root, and --toolbox-root")
    skill_metadata(args.skill)
    if args.baseline:
        skill_metadata(args.baseline)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    configurations = {"candidate": snapshot(args.skill, inputs / "candidate")}
    if args.baseline:
        configurations["baseline"] = snapshot(args.baseline, inputs / "baseline")
    fixture_hashes = {}
    for case in cases:
        if case["fixture"] not in fixture_hashes:
            fixture_hashes[case["fixture"]] = snapshot(args.cases_file.parent / case["fixture"], inputs / case["fixture"])
    write_json(inputs / "evals.json", document)
    report = {"schema_version": "1.0", "suite": "tutor-skill", "configurations": configurations,
              "case_spec_sha256": digest(document), "fixture_hashes": fixture_hashes,
              "runner_sha256": digest(file_hashes(Path(__file__).parent)),
              "grading_calibration": document["grading_calibration"], "trials_per_case": args.trials,
              "selected_cases": [case["id"] for case in cases], "results": [],
              "packages": {name: importlib.metadata.version(name) for name in ("openai-codex", "mcp", "PyYAML")}}
    write_json(output / "manifest.json", report)
    deadline = min(time.monotonic() + args.timeout_seconds, getattr(args, "invocation_deadline", float("inf")))
    versions = [version for version in ("baseline", "candidate") if version in configurations]
    for case in cases:
        for number in range(1, args.trials + 1):
            for version in versions:
                remaining = deadline - time.monotonic()
                if (remaining <= 0 or asyncio.current_task().cancelling()
                        or (getattr(args, "stop_file", None) is not None and args.stop_file.exists())):
                    break
                print(f"Running {version}/{case['id']}/trial-{number} ({case['backend']})...", flush=True)
                trial_output = output / version / case["id"] / f"trial-{number}"
                row = await run_trial(trial_output, case, inputs / case["fixture"], inputs / version,
                                      server=args.matlab_server, matlab_root=args.matlab_root,
                                      toolbox_root=args.toolbox_root, model=args.model,
                                      timeout=min(remaining, args.trial_timeout_seconds))
                row.update(configuration=version, trial_number=number)
                report["results"].append(row)
                print(f"  {row['status']} ({row['duration_seconds']:.1f}s)", flush=True)
                write_json(output / "benchmark.json", report)
    report["summaries"] = {version: summarize([r for r in report["results"] if r["configuration"] == version],
                                              len(cases) * args.trials, document["grading_calibration"])
                           for version in versions}
    if args.trials < 2:
        for summary in report["summaries"].values():
            if summary["readiness"] == "meets_pilot_bar":
                summary["readiness"] = "insufficient_evidence"
    report["comparison"] = comparison(report)
    write_json(output / "benchmark.json", report)
    write_json(output / "comparison.json", report["comparison"])
    render_report(output, report)
    return report
