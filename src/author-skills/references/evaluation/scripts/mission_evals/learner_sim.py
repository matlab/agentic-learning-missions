"""Standalone learner/tutor orchestration over the shared evaluation runtime."""

import asyncio
import importlib.metadata
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from openai_codex import Sandbox, SkillInput, TextInput

from .codex_runtime import agent_client, capture_turn
from .events import EventLog, read_events, write_json
from .learner_grading import acceptance_grade, recommendations, rubric_grade, schedule_grade
from .learner_spec import PROFILES, load_spec, mistake_schedule
from .matlab_runtime import owned_matlab, result_text
from .mission_backend import LEARNER_TOOLS, MissionBackend, MissionBridge, validate_learner_call
from .skill_assets import digest, file_hashes, matlab_string, prepare_live_workspace, protected_hashes, snapshot
from .skill_bridge import serve_bridge
from .skill_grading import grade_status
from .smoke import error_details
from .workspace import trial_workspace

SCRIPTS = Path(__file__).resolve().parent.parent
ACTION_SCHEMA = {"type": "object", "properties": {
    "intention": {"type": "string"}, "message": {"type": "string"},
    "asked_for_help": {"type": "boolean"},
    "actions": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "arguments_json": {"type": "string"}},
        "required": ["name", "arguments_json"], "additionalProperties": False}}},
    "required": ["intention", "message", "asked_for_help", "actions"], "additionalProperties": False}
PROBE_SCHEMA = {"type": "object", "properties": {"explanation": {"type": "string"}, "transfer": {"type": "string"}},
                "required": ["explanation", "transfer"], "additionalProperties": False}


def runtime_details(details, thread):
    return {"thread_id": thread.id, "model": details.model, "model_provider": details.model_provider,
            "reasoning_effort": details.reasoning_effort, "cli_version": details.cli_version}


def presented_task(text, tasks):
    for task in tasks:
        number = int(task["id"][1:])
        if re.search(rf"\btask\s*{number}\b", text, re.I):
            return task["id"]
    return None


async def probe(thread, spec, phase, log):
    prompt = ("Outside Ada's conversation, answer these two unhinted questions from your current understanding. "
              "Keep your learner profile. Do not use tools or take product actions. Do not ask Ada about these probes.\n" +
              json.dumps(spec["probes"]))
    text = await capture_turn(thread, prompt, "learner", log, output_schema=PROBE_SCHEMA)
    log.emit("probe.response", "learner", {"phase": phase, "answers": json.loads(text)})


async def learner_turn(thread, message, assignment, installed, backend, log, *, startup=False):
    prompt = ("Ada's visible message:\n" + message + "\nAssigned behavior for this turn: " +
              (assignment["instruction"] if assignment else ("Respond to Ada's organizer question; no product work yet." if startup else "Follow your profile and execute the currently presented task using product actions.")) +
              "\nReturn your intention and up to four exact MCP actions. arguments_json is a JSON object string. "
              "If you need observations, request inspection actions first. The executor returns their actual results; it will not repair your code. "
              "When finished or asking Ada for help, return no actions and put your learner-facing response in message. "
              "If the task asks you to do product work, actually submit actions; do not merely promise to act.")
    actions, ids = [], []
    # Bounded product planning within one dialogue turn; retries are explicit agent decisions.
    for cycle in range(5):
        text = await capture_turn(thread, prompt, "learner", log, output_schema=ACTION_SCHEMA)
        plan = json.loads(text)
        intention = log.emit("learner.intention", "learner", plan)
        ids.append(intention)
        if not plan["actions"]:
            response = log.emit("learner.response", "learner", {"text": plan["message"], "asked_for_help": plan["asked_for_help"]})
            return plan["message"], plan["asked_for_help"], actions, [*ids, response]
        results = []
        for proposed in plan["actions"]:
            action = {"name": proposed["name"], "arguments": json.loads(proposed["arguments_json"]), "intention_event": intention}
            event_id = log.emit("learner.action", "learner", action)
            try:
                validate_learner_call(action["name"], action["arguments"], installed)
                reply = await backend.call(action["name"], action["arguments"], "learner")
                result = reply.model_dump(mode="json", by_alias=True)
                action["executed"] = True
                action["is_error"] = reply.is_error
            except Exception as error:
                result = {"isError": True, "error": str(error)}
                action["executed"] = False
                action["is_error"] = True
            result_id = log.emit("learner.result", "learner", {"call_event_id": event_id, "result": result})
            action.update(event_id=event_id, result_event_id=result_id)
            actions.append(action)
            ids.extend([event_id, result_id])
            results.append(result)
        prompt = ("Actual results of your requested actions:\n" + json.dumps(results) +
                  "\nKeep the assigned behavior: " + (assignment["instruction"] if assignment else "Follow your profile.") +
                  ("\nNow return no actions and respond to Ada." if cycle >= 3 else "\nContinue only if needed, or return no actions and respond to Ada."))
    raise RuntimeError("Learner exceeded the bounded action-planning turns")


def emit_checkpoint(log, task, stage, observation):
    return log.emit("checkpoint", "checker", {"task_id": task, "stage": stage, "observation": observation})


def action_summary(events, path):
    rows = []
    tutor = ""
    actions = []
    for event in events:
        if event["event_type"] == "tutor.response":
            tutor = event["payload"]["text"]
        elif event["event_type"] == "learner.action":
            actions.append(dict(event["payload"], event_id=event["event_id"]))
        elif event["event_type"] == "learner.result":
            for action in actions:
                if action["event_id"] == event["payload"]["call_event_id"]:
                    action["observed_result"] = event["payload"]["result"]
                    action["result_event_id"] = event["event_id"]
        elif event["event_type"] == "learner.response":
            rows.append({"timestamp": event["timestamp"], "learner_type": event["learner_type"],
                         "mission_name": event["mission_name"], "mission_task_id": event["task_id"],
                         "action": "learner_turn", "agent_message": tutor,
                         "learner_response": event["payload"]["text"], "product_actions": actions,
                         "evidence_id": event["event_id"]})
            actions = []
    if actions:
        rows.append({"timestamp": events[-1]["timestamp"], "learner_type": events[-1]["learner_type"],
                     "mission_name": events[-1]["mission_name"], "mission_task_id": events[-1]["task_id"],
                     "action": "interrupted_turn", "agent_message": tutor, "learner_response": None,
                     "product_actions": actions, "evidence_id": events[-1]["event_id"]})
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


async def run_trial(output, mission, skill, spec, profile, seed, args, timeout):
    output.mkdir(parents=True)
    started = time.monotonic()
    schedule = mistake_schedule(profile, spec["tasks"], seed)
    row = {"trial_id": str(uuid.uuid4()), "mission_name": mission.name, "profile": profile, "seed": seed,
           "status": "unknown", "grades": [], "completed_tasks": [], "attempts": [], "schedule": schedule,
           "stop_reason": "infrastructure_failure", "runtime": {}}
    root = None
    with EventLog(output / "events.jsonl", run_id=args.run_id, trial_id=row["trial_id"], suite="learner-sim", case_id=profile,
                  mission_name=mission.name) as log:
        log.set_learner(profile)
        log.emit("trial.started", "harness", {"profile": profile, "seed": seed, "budget_seconds": timeout})
        log.emit("schedule.assigned", "harness", {"schedule": schedule})
        try:
            with trial_workspace() as root:
                log.emit("workspace.created", "harness", {"path": str(root)})
                async with asyncio.timeout(timeout):
                    async with owned_matlab(root, log, server=args.matlab_server, matlab_root=args.matlab_root,
                                            extensions=args.extension_file) as (broker, product):
                        initialization = await broker.call("harness", "evaluate_matlab_code", {"code":
                            f'addpath({matlab_string(args.toolkit_root)}); addpath(genpath({matlab_string(args.toolkit_root / "tools")})); '
                            'assert(exist("model_read","file") == 6 || exist("model_read","file") == 2); '
                            'assert(exist("model_edit","file") == 6 || exist("model_edit","file") == 2); '
                            'disp("IM_TOOLKIT_READY"); disp(which("model_read")); disp(which("model_edit")); disp(jsonencode(ver));'})
                        if "IM_TOOLKIT_READY" not in result_text(initialization).splitlines():
                            raise RuntimeError("Installed toolkit functions are unavailable in the owned MATLAB session")
                        workspace = root / "tutor-workspace"
                        copied = await prepare_live_workspace(broker, workspace, mission, skill, args.toolbox_root)
                        # Product working directory never contains tutor/mission/grader files.
                        product_dir = root / "product"
                        product_dir.mkdir()
                        await broker.call("harness", "evaluate_matlab_code", {"code": f'cd({matlab_string(product_dir)}); rng({seed});'})
                        before_bundle = protected_hashes(workspace)
                        backend = MissionBackend(broker, workspace, args.observer)
                        bridge = MissionBridge(workspace, backend, log)
                        installed = {t.name: t for t in broker.tools if t.name in LEARNER_TOOLS}
                        learner_dir = root / "learner-context"
                        learner_dir.mkdir()
                        schemas = [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in installed.values()]
                        learner_instructions = ("You are the learner in a synthetic tutoring session. " + PROFILES[profile] +
                            " You have basic MATLAB syntax knowledge. Never read mission YAML, tutor skills, hidden checks or files. "
                            "You cannot use host tools. Submit exact requested product actions as JSON to the executor. "
                            "Inspect installed APIs, block types and parameters before configuring unfamiliar ones. "
                            "Use only information revealed in Ada's conversation and product results. Do not reveal persona schedules to Ada. "
                            "Do not ask to save progress. Use a model name you choose. Available installed MCP tools:\n" + json.dumps(schemas))
                        async with serve_bridge(bridge) as (servers, environment):
                            async with agent_client(root / "tutor-runtime", workspace, log, model=args.model,
                                                    mcp_servers=servers, extra_env=environment) as tutor_client:
                                async with agent_client(root / "learner-runtime", learner_dir, log, model=args.model) as learner_client:
                                    tutor = await tutor_client.thread_start(cwd=str(workspace), ephemeral=True, sandbox=Sandbox.read_only,
                                        developer_instructions="Use read_workspace_file for workspace files and the provided MATLAB MCP tools. Follow the selected skill's normal tutoring permissions.")
                                    learner = await learner_client.thread_start(cwd=str(learner_dir), ephemeral=True, sandbox=Sandbox.read_only,
                                                                               developer_instructions=learner_instructions)
                                    if tutor.id == learner.id:
                                        raise RuntimeError("Tutor and learner contexts are not fresh and separate")
                                    log.emit("contexts.created", "harness", {"tutor": tutor.id, "learner": learner.id, "learner_directory_empty": not any(learner_dir.iterdir())})
                                    await probe(learner, spec, "pre", log)
                                    startup = "Start this mission in practice mode."
                                    message = await capture_turn(tutor, startup, "tutor", log, allow_tools=True, include_commentary=True,
                                        inputs=[TextInput(startup), SkillInput("mission-tutoring", str(copied / "SKILL.md"))],
                                        on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                    log.emit("tutor.response", "tutor", {"text": message}, turn_id=bridge.turn_id)
                                    current, counts, startup_count = None, {}, 0
                                    while True:
                                        if args.stop_file.exists():
                                            row["stop_reason"] = "operator_stop"
                                            break
                                        if current is None:
                                            startup_count += 1
                                            if startup_count > 3:
                                                row["stop_reason"] = "startup_did_not_present_task"
                                                break
                                        else:
                                            counts[current] = counts.get(current, 0) + 1
                                            if counts[current] > args.turns_per_task:
                                                row["stop_reason"] = "task_turn_budget"
                                                break
                                        log.set_task(current)
                                        attempt = counts.get(current, 0)
                                        assignment = next((e for e in schedule if e["task_id"] == current and e["attempt"] == attempt), None)
                                        baseline = await backend.observe(mission.name, current)
                                        baseline_id = emit_checkpoint(log, current, "before_learner", baseline)
                                        response, asked, actions, ids = await learner_turn(learner, message, assignment, installed, backend, log, startup=current is None)
                                        before = await backend.observe(mission.name, current)
                                        before_id = emit_checkpoint(log, current, "before_tutor", before)
                                        if current:
                                            row["attempts"].append({"task_id": current, "attempt": attempt, "asked_for_help": asked,
                                                "product_actions": [a for a in actions if a["executed"] and not a["is_error"]],
                                                "state_changed": baseline["state"] != before["state"],
                                                "observation_status": before["status"], "evidence_ids": [baseline_id, *ids, before_id]})
                                        bridge.step_id = current
                                        message = await capture_turn(tutor, response, "tutor", log, allow_tools=True, include_commentary=True,
                                            on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                        response_id = log.emit("tutor.response", "tutor", {"text": message}, turn_id=bridge.turn_id)
                                        after = await backend.observe(mission.name, current)
                                        after_id = emit_checkpoint(log, current, "after_tutor", after)
                                        if current:
                                            boundary = before["state"] == after["state"]
                                            row["grades"].append({"id": "protected_product_state", "task_id": current,
                                                "status": "pass" if boundary else "unknown", "evidence_ids": [before_id, after_id],
                                                "reason": "Product state unchanged" if boundary else "State changed; independent rubric must distinguish inspection effects from learner edits"})
                                            if ">>> CORRECT! <<<" in message:
                                                row["grades"].append(dict(acceptance_grade(True, before, before_id, response_id), task_id=current))
                                                row["completed_tasks"].append(current)
                                                if len(row["completed_tasks"]) == len(spec["tasks"]) or (args.max_tasks and len(row["completed_tasks"]) >= args.max_tasks):
                                                    row["stop_reason"] = "mission_completed" if len(row["completed_tasks"]) == len(spec["tasks"]) else "task_scope_limit"
                                                    break
                                                current = spec["tasks"][len(row["completed_tasks"])]["id"]
                                        else:
                                            current = presented_task(message, spec["tasks"])
                                    await probe(learner, spec, "post", log)
                                    row["runtime"] = {"tutor": runtime_details((await tutor.read()).thread, tutor),
                                                      "learner": runtime_details((await learner.read()).thread, learner),
                                                      "matlab_release": product["release"]}
                        bundle_ok = before_bundle == protected_hashes(workspace)
                        event_id = log.emit("bundle.checked", "harness", {"unchanged": bundle_ok})
                        row["grades"].append({"id": "bundle_integrity", "status": "pass" if bundle_ok else "fail", "evidence_ids": [event_id]})
                        row["grades"].extend(schedule_grade(schedule, row["attempts"]))
                        # Preserve only learner product files; credentials/settings remain disposable.
                        snapshot(product_dir, output / "product-artifacts")
                    grades, proxies, grader_runtime = await rubric_grade(root, log, spec, profile, args.model)
                    row["grades"].extend(grades)
                    row["learning_proxies"] = proxies
                    row["runtime"]["grader"] = grader_runtime
                    if row["stop_reason"] != "mission_completed":
                        row["grades"].append({"id": "mission_completion", "status": "unknown", "evidence_ids": [], "reason": row["stop_reason"]})
                    row["status"] = grade_status(row["grades"])
            log.emit("trial.completed", "harness", row)
        except (Exception, asyncio.CancelledError) as error:
            row["error"] = error_details(error)
            def timed_out(exception):
                return isinstance(exception, TimeoutError) or (isinstance(exception, BaseExceptionGroup) and any(timed_out(e) for e in exception.exceptions))
            row["stop_reason"] = "budget_exhausted" if timed_out(error) else "infrastructure_failure"
            row["status"] = "fail" if grade_status(row["grades"]) == "fail" else "unknown"
            row["error_evidence"] = [log.emit("trial.error", "harness", {"error": row["error"], "stop_reason": row["stop_reason"]})]
        finally:
            row["workspace_removed"] = root is not None and not root.exists()
            log.emit("workspace.cleanup", "harness", {"removed": row["workspace_removed"]})
    row["duration_seconds"] = time.monotonic() - started
    row["recommendations"] = recommendations(row)
    events = read_events(output / "events.jsonl")
    row["event_count"] = len(events)
    action_summary(events, output / "actions.jsonl")
    write_json(output / "grading.json", row)
    return row


def readiness(report):
    counts = {key: sum(r["status"] == key for r in report["results"]) for key in ("pass", "fail", "unknown")}
    counts["not_run"] = max(0, len(report["selected_missions"])*len(report["profiles"])*report["trials_per_profile"]-len(report["results"]))
    provisional = any(s["author_review"] != "reviewed" or s["grading_calibration"] != "reviewed" for s in report["specifications"].values())
    confirmed = True
    for mission in report["selected_missions"]:
        for profile in report["profiles"]:
            valid = [r for r in report["results"] if r.get("mission_name") == mission and r.get("profile") == profile and r["status"] == "pass"]
            confirmed = confirmed and len({r.get("seed") for r in valid}) >= 2
            if profile != "expert":
                confirmed = confirmed and len({digest(r.get("schedule", [])) for r in valid}) >= 2
    value = "insufficient_evidence"
    if not provisional and counts["fail"]:
        value = "does_not_meet_pilot_bar"
    elif not provisional and not any(counts[k] for k in ("fail", "unknown", "not_run")) and report["trials_per_profile"] >= 2 and set(report["profiles"]) == set(PROFILES) and confirmed:
        value = "meets_pilot_bar"
    return {"readiness": value, "counts": counts, "provisional": provisional, "confirming_variation": confirmed}


def render_report(output, report):
    report["summary"] = readiness(report)
    lines = ["# Learner Simulation", "", f"Readiness: **{report['summary']['readiness']}**. Provisional: {report['summary']['provisional']}.",
             "", "No tutor-skill suite was executed. Probes measure simulated explanation and transfer, not human learning.", "",
             "| Mission | Profile | Seed | Result | Ada accepted | Independently verified | Stop reason | Trace |", "|---|---|---|---|---|---|---|---|"]
    for row in report["results"]:
        verified = sum(g["id"] == "false_acceptance" and g["status"] == "pass" for g in row.get("grades", []))
        lines.append(f"| {row['mission_name']} | {row['profile']} | {row['seed']} | {row['status']} | {len(row['completed_tasks'])} | {verified} | {row['stop_reason']} | [JSONL](<{row['evidence_path']}>) |")
    lines.extend(["", "## Learning proxies and recommendations", ""])
    for row in report["results"]:
        lines.append(f"- {row['mission_name']}/{row['profile']}/{row['seed']}: `{json.dumps(row.get('learning_proxies', {'status': 'unknown'}))}`")
        for finding in row["recommendations"]:
            lines.append(f"- {finding['severity']} / {finding['category']}: {finding['consequence']}. Likely cause: {finding['likely_cause']}. Proposed change: {finding['proposed_change']}. Confirm: {finding['confirming_test']}. Confidence: {finding['confidence']}. Evidence: {', '.join(finding['evidence_ids']) or 'missing'}.")
    lines.extend(["", "Limits: stock pilot observers, Windows/R2026b qualification only; unsupported alternatives are unknown. Desktop usability is not assessed. No automatic mission or tutor edits. See grading.json and checkpoints for individual assertions.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(output / "benchmark.json", report)


def rebuild(output):
    report = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if report.get("source_runs"):
        from .learner_reports import load_run
        for path in report["source_runs"]:
            load_run(Path(path))
        render_report(output, report)
        return report
    report["results"] = []
    for trace in sorted(output.glob("trials/*/*/*/events.jsonl")):
        grading = trace.parent / "grading.json"
        events = read_events(trace)
        if not events:
            raise ValueError("Empty trial evidence")
        if grading.exists():
            row = json.loads(grading.read_text(encoding="utf-8"))
        else:
            first = events[0]
            row = {"trial_id": first["trial_id"], "mission_name": first["mission_name"],
                   "profile": first["learner_type"], "seed": first["payload"].get("seed"),
                   "status": "unknown", "grades": [], "completed_tasks": [], "stop_reason": "interrupted",
                   "error": "Trace ended before grading was published", "error_evidence": [events[-1]["event_id"]],
                   "runtime": {}}
            row["recommendations"] = recommendations(row)
        if not events or events[0]["trial_id"] != row["trial_id"]:
            raise ValueError("Trial evidence does not match grading")
        row["recommendations"] = recommendations(row)
        action_summary(events, trace.parent / "actions.jsonl")
        row["evidence_path"] = trace.relative_to(output).as_posix()
        report["results"].append(row)
    render_report(output, report)
    return report


async def run(args):
    missions = {path.name: path for path in args.mission}
    if len(missions) != len(args.mission):
        raise ValueError("Mission folder names must be unique")
    specs = {name: load_spec(args.spec_dir / f"{name}.json", path) for name, path in missions.items()}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    skill = snapshot(args.skill, inputs / "tutor")
    snapshot(SCRIPTS, inputs / "runner")
    args.observer = inputs / "runner/observe_mission.m"
    mission_hashes = {name: snapshot(path, inputs / "missions" / name) for name, path in missions.items()}
    for name, spec in specs.items():
        write_json(inputs / f"{name}.json", spec)
    extensions = []
    for index, path in enumerate(args.extension_file):
        frozen = inputs / f"extension-{index}.json"
        shutil.copyfile(path, frozen)
        extensions.append(frozen)
    args.extension_file = extensions
    args.run_id = str(uuid.uuid4())
    args.stop_file = getattr(args, "stop_file", output / "STOP")
    report = {"schema_version": "1.0", "suite": "learner-sim", "run_id": args.run_id, "selected_missions": list(missions),
              "profiles": args.profile, "trials_per_profile": args.trials, "seed": args.seed, "skill": skill,
              "mission_hashes": mission_hashes, "specifications": specs, "runner_sha256": digest(file_hashes(SCRIPTS)),
              "extension_sha256": digest([p.read_text(encoding="utf-8") for p in extensions]),
              "toolkit": {"root": str(args.toolkit_root), "sha256": digest(file_hashes(args.toolkit_root / "tools")),
                          "version": (args.toolkit_root / "VERSION").read_text(encoding="utf-8").strip()},
              "packages": {name: importlib.metadata.version(name) for name in ("openai-codex", "mcp", "PyYAML")},
              "budgets": {"invocation_seconds": args.timeout_seconds, "trial_seconds": args.trial_timeout_seconds,
                          "turns_per_task": args.turns_per_task}, "max_tasks": args.max_tasks, "results": []}
    write_json(output / "manifest.json", report)
    render_report(output, report)
    deadline = min(time.monotonic() + args.timeout_seconds, getattr(args, "invocation_deadline", float("inf")))
    for number in range(args.trials):
        for name in missions:
            for profile in args.profile:
                remaining = deadline-time.monotonic()
                if remaining <= 0 or args.stop_file.exists() or asyncio.current_task().cancelling():
                    return report
                seed = args.seed+number
                trial_output = output / "trials" / name / profile / f"seed-{seed}"
                print(f"Running {name}/{profile}/seed-{seed}...", flush=True)
                row = await run_trial(trial_output, inputs / "missions" / name, inputs / "tutor", specs[name], profile,
                                      seed, args, min(remaining, args.trial_timeout_seconds))
                row["evidence_path"] = (trial_output / "events.jsonl").relative_to(output).as_posix()
                report["results"].append(row)
                render_report(output, report)
                print(f"  {row['status']}: {row['stop_reason']}, {len(row['completed_tasks'])} tasks ({row['duration_seconds']:.1f}s)", flush=True)
    return report
