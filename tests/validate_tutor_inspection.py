"""Opt-in live tutor regression for inspection that preserves learner results.

Uses the shared isolated MATLAB/Codex runtime and frozen stock mission tasks.
The fixture drives learner actions directly; no learner persona or historical
grade is changed. Baseline failures are evidence, not failures of this command.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

from openai_codex import Sandbox, SkillInput, TextInput

from mission_evals.codex_runtime import agent_client, capture_turn
from mission_evals.events import EventLog, read_events, write_json
from mission_evals.matlab_runtime import owned_matlab, result_text
from mission_evals.mission_backend import MissionBackend, MissionBridge
from mission_evals.skill_assets import (matlab_string, prepare_live_workspace,
                                       protected_hashes, snapshot)
from mission_evals.skill_bridge import serve_bridge, text_result
from mission_evals.smoke import error_details
from mission_evals.workspace import trial_workspace

DEFAULT_CASES = ("ans", "out", "sensorRun", "missing", "wrong-model", "inspection-error")
TIME_CASES = ("time-zero", "time-never-run", "time-failed-run")
CONFIG_CASES = ("config-conflict", "config-disabled", "config-direct-error")
CASES = DEFAULT_CASES + TIME_CASES + CONFIG_CASES
FIXTURE_INCOMPLETE_CASES = ("missing", "wrong-model", "time-never-run", "time-failed-run",
                            "config-disabled")
WITHHELD_COMPLETION_CASES = FIXTURE_INCOMPLETE_CASES + ("inspection-error", "config-direct-error")
VOLATILE_SCOPE_PARAMETERS = frozenset({"ActiveDisplayYMinimum", "ActiveDisplayYMaximum"})


def case_task(case):
    if case in TIME_CASES:
        return "continuous-and-discrete-time", "t01", "t02"
    if case in CONFIG_CASES:
        return "root-inports-outports", "t03", "t04"
    return "root-inports-outports", "t04", "t05"

# Function-local/persistent copies keep test evidence out of learner variables
# and out of the tutor's permitted file reads. Explicitly include ans: the stock
# observer's general workspace fingerprint intentionally omits it.
STATE_FUNCTION = '''function result = inspection_state(action)
persistent original
names = string({evalin("base", "whos").name});
temporary = startsWith(names, "mcpTmp_") | names == "mcpTmpNames";
learnerNames = sort(names(~temporary));
if action == "save"
    original = struct("names", learnerNames, "values", {{}});
    for index = 1:numel(learnerNames)
        original.values{index} = evalin("base", learnerNames(index));
    end
end
result = struct("ans_exists", any(names == "ans"), "ans_class", "", ...
    "ans_preserved", true, "learner_variables_preserved", ...
    isequal(learnerNames, original.names), "temporaries", names(temporary));
if result.ans_exists
    result.ans_class = string(evalin("base", "class(ans)"));
end
result.ans_preserved = any(original.names == "ans") == result.ans_exists;
for index = 1:numel(original.names)
    name = original.names(index);
    preserved = any(names == name) && ...
        isequaln(original.values{index}, evalin("base", name));
    result.learner_variables_preserved = result.learner_variables_preserved && preserved;
    if name == "ans"
        result.ans_preserved = preserved;
    end
end
end
'''


class InspectionBackend(MissionBackend):
    """Inject tutor-side inspection faults without disabling fixture observers."""

    fail_next_inspection = False
    inspection_unavailable = False
    injected_errors = 0
    tutor_simulations = 0
    config_conflict = False
    direct_config_unavailable = False
    injected_conflicts = 0
    direct_config_inspections = 0
    direct_config_errors = 0

    async def call(self, name, arguments, actor="tutor"):
        code = arguments.get("code", "")
        if actor == "tutor" and name == "evaluate_matlab_code" and re.search(
                r"\b(?:sim|parsim)\s*\(|[\"']SimulationCommand[\"']\s*,\s*[\"'](?:start|continue)[\"']", code):
            self.tutor_simulations += 1
        direct_config_read = name == "evaluate_matlab_code" and "get_param" in code and (
            "LoadExternalInput" in code or "ExternalInput" in code)
        if actor == "tutor" and direct_config_read:
            self.direct_config_inspections += 1
            if self.config_conflict and self.injected_conflicts == 0:
                self.injected_conflicts += 1
                return text_result(
                    "Stale observation: LoadExternalInput is off and ExternalInput is empty.", error=False)
            if self.direct_config_unavailable:
                self.direct_config_errors += 1
                return text_result("Direct configuration inspection unavailable.", error=True)
        if actor == "tutor" and self.inspection_unavailable:
            self.injected_errors += 1
            return text_result("MATLAB inspection unavailable.", error=True)
        inspection = name.startswith("model_") or (name == "evaluate_matlab_code" and
            any(term in code for term in ("whos", "get_param", "find_system", "model_read", "SimulationOutput")))
        if actor == "tutor" and self.fail_next_inspection and inspection:
            self.fail_next_inspection = False
            self.injected_errors += 1
            return text_result("MATLAB inspection temporarily unavailable. Retry the inspection.", error=True)
        return await super().call(name, arguments, actor)


def immutable_bundle(workspace):
    hashes = protected_hashes(workspace)
    hashes.get(".interactive-missions", {}).pop("progress.json", None)
    return hashes


def tracked_task(workspace, task_id):
    runtime = workspace / ".interactive-missions"
    manifest = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(mode="regular", progressPath=str(runtime / "progress.json"))
    write_json(runtime / "manifest.json", manifest)
    progress = dict(schemaVersion="2.0", learnerName="Inspection Learner",
        marketplaceSource=manifest["marketplaceSource"], missionName=manifest["missionName"],
        missionId=manifest["missionId"], missionVersion=manifest["missionVersion"],
        workspacePath=str(workspace), mode="regular", currentStepId=task_id,
        completedStepIds=[f"t{index:02}" for index in range(1, int(task_id[1:]))], hintCounts={}, notes="",
        updatedAt=datetime.now(timezone.utc).isoformat())
    write_json(runtime / "progress.json", progress)


def model_state_preserved(before, after, required_display_parameters=()):
    required_display_parameters = frozenset(required_display_parameters)

    def semantic_blocks(blocks):
        normalized = []
        for block in blocks:
            item = dict(block)
            if item.get("type") == "Scope":
                for parameter in VOLATILE_SCOPE_PARAMETERS - required_display_parameters:
                    item.pop(parameter, None)
            normalized.append(item)
        return normalized

    return (semantic_blocks(before["block_parameters"]) == semantic_blocks(after["block_parameters"]) and
            before["model_parameters"] == after["model_parameters"] and
            before["models"] == after["models"])


def trial_assertions(case, before, after, state, message, progress, bundle_unchanged, injected_errors,
                     *, task_id="t04", next_task_id="t05", tutor_simulations=0,
                     injected_conflicts=0, direct_config_inspections=0, direct_config_errors=0,
                     required_display_parameters=()):
    fixture_complete = case not in FIXTURE_INCOMPLETE_CASES
    should_accept = case not in WITHHELD_COMPLETION_CASES
    accepted = ">>> CORRECT! <<<" in message
    advanced = task_id in progress["completedStepIds"] and progress["currentStepId"] == next_task_id
    return {
        "fixture_verified": before["status"] == ("pass" if fixture_complete else "fail"),
        "ans_preserved": state["ans_preserved"],
        "learner_variables_preserved": state["learner_variables_preserved"],
        "model_state_preserved": model_state_preserved(
            before["state"], after["state"], required_display_parameters),
        "inspection_temporaries_removed": not state["temporaries"],
        "required_task_evidence": after["status"] == before["status"],
        "task_acceptance": accepted == should_accept,
        "progress": advanced if should_accept else (task_id not in progress["completedStepIds"] and
                                              progress["currentStepId"] == task_id),
        "protected_bundle": bundle_unchanged,
        "inspection_error_exercised": case != "inspection-error" or injected_errors >= 1,
        "zero_timing_exercised": case != "time-zero" or before.get("facts", {}).get("simulation_time") == 0,
        "failed_run_exercised": case != "time-failed-run" or before.get("facts", {}).get("simulation_failure_exercised") is True,
        "no_tutor_simulation": tutor_simulations == 0,
        "config_conflict_exercised": case not in ("config-conflict", "config-direct-error") or injected_conflicts >= 1,
        "direct_config_inspection": case not in ("config-conflict", "config-direct-error") or direct_config_inspections >= 1,
        "direct_config_error_exercised": case != "config-direct-error" or direct_config_errors >= 1,
        "unresolved_conflict_not_false_rejected": case != "config-direct-error" or not re.search(
            r"\b(disabled|turn on|enable external input|set external input)\b", message, re.I),
    }


async def prepare_time_fixture(execute, case):
    await execute('load_system("simulink"); '
        'assert(strcmp(get_param("simulink/Sources/Sine Wave", "BlockType"), "Sin")); '
        'assert(strcmp(get_param("simulink/Sinks/Scope", "BlockType"), "Scope")); '
        'assert(all(isfield(get_param("simulink/Sources/Sine Wave", "DialogParameters"), '
        '["SampleTime", "Amplitude"]))); '
        'new_system("inspectionTimeModel"); '
        'assert(isfield(get_param("inspectionTimeModel", "ObjectParameters"), "ReturnWorkspaceOutputs")); '
        'add_block("simulink/Sources/Sine Wave", "inspectionTimeModel/Source"); '
        'add_block("simulink/Sinks/Scope", "inspectionTimeModel/Scope"); '
        'add_line("inspectionTimeModel", "Source/1", "Scope/1"); '
        'set_param("inspectionTimeModel/Source", "SampleTime", "0"); '
        'set_param("inspectionTimeModel", "ReturnWorkspaceOutputs", "on", "StopTime", "1"); '
        'open_system("inspectionTimeModel"); open_system("inspectionTimeModel/Scope"); '
        'ans = struct("learnerSentinel", 2718);')
    if case == "time-zero":
        await execute('sensorRun = sim("inspectionTimeModel"); '
            'assert(get_param("inspectionTimeModel", "SimulationTime") == 0);')
    elif case == "time-failed-run":
        text = await execute('set_param("inspectionTimeModel/Source", "Amplitude", "inspectionMissingAmplitude"); '
            'mcpTmp_fixtureFailed = false; '
            'try; sensorRun = sim("inspectionTimeModel"); '
            'catch mcpTmp_fixtureError; mcpTmp_fixtureFailed = true; '
            'disp("EXPECTED_SIMULATION_FAILURE " + string(mcpTmp_fixtureError.identifier)); end; '
            'assert(mcpTmp_fixtureFailed); clear mcpTmp_fixtureFailed mcpTmp_fixtureError;')
        if "EXPECTED_SIMULATION_FAILURE " not in text:
            raise RuntimeError("Failed-run fixture did not execute a failing simulation")


async def simulation_clock(execute):
    text = await execute('disp("SIMULATION_CLOCK " + string(get_param("inspectionTimeModel", "SimulationTime")));')
    values = [line.removeprefix("SIMULATION_CLOCK ") for line in text.splitlines()
              if line.startswith("SIMULATION_CLOCK ")]
    if len(values) != 1:
        raise RuntimeError("Simulation clock was not returned: " + text)
    return float(values[0])


async def prepare_config_fixture(execute, workspace, case):
    setup = workspace / ".interactive-missions/content/setup_root_inports_outports.m"
    await execute(f'run({matlab_string(setup)}); '
        'assert(isa(respiratoryData, "timeseries")); '
        'assert(bdIsLoaded("mission01")); '
        'assert(strcmp(get_param("mission01/In1", "BlockType"), "Inport")); '
        'mcpTmp_parameters = get_param("mission01", "ObjectParameters"); '
        'assert(isfield(mcpTmp_parameters, "LoadExternalInput")); '
        'assert(isfield(mcpTmp_parameters, "ExternalInput")); '
        'set_param("mission01", "ExternalInput", "respiratoryData"); '
        'set_param("mission01/In1", "SampleTime", "0.001"); '
        'set_param("mission01", "LoadExternalInput", "on"); '
        'ans = struct("learnerSentinel", 2718);')
    if case == "config-disabled":
        await execute('set_param("mission01", "LoadExternalInput", "off");')


async def run_trial(args, skill, configuration, case, trial):
    output = args.output / configuration / case / f"trial-{trial}"
    output.mkdir(parents=True)
    started = time.monotonic()
    mission_name, task_id, next_task_id = case_task(case)
    mission = args.missions[mission_name]
    row = dict(configuration=configuration, case=case, trial=trial, mission_name=mission_name,
               task_id=task_id, status="unknown", assertions={})
    with EventLog(output / "events.jsonl", run_id=args.run_id, suite="tutor-inspection",
                  case_id=case, mission_name=mission_name) as log:
        log.set_task(task_id)
        try:
            with trial_workspace() as root:
                async with asyncio.timeout(args.trial_timeout_seconds):
                    async with owned_matlab(root, log, server=args.matlab_server, matlab_root=args.matlab_root,
                                            extensions=[args.toolkit_root / "tools/tools.json"]) as (broker, product):
                        await broker.call("harness", "evaluate_matlab_code", {"code":
                            f'addpath(genpath({matlab_string(args.toolkit_root / "tools")}));'})
                        workspace = root / "tutor-workspace"
                        copied = await prepare_live_workspace(broker, workspace, mission, skill, args.toolbox_root)
                        tracked_task(workspace, task_id)
                        product_dir = root / "product"
                        product_dir.mkdir()
                        (product_dir / "inspection_state.m").write_text(STATE_FUNCTION, encoding="utf-8")
                        backend = InspectionBackend(broker, workspace, args.observer)
                        bridge = MissionBridge(workspace, backend, log)

                        async def execute(code):
                            reply = await backend.call("evaluate_matlab_code", {"code": code}, "fixture")
                            if reply.is_error:
                                raise RuntimeError(result_text(reply))
                            return result_text(reply)

                        async def state(action):
                            text = await execute('disp("INSPECTION_STATE " + jsonencode(inspection_state(' +
                                                 matlab_string(action) + ')));')
                            rows = [line.removeprefix("INSPECTION_STATE ") for line in text.splitlines()
                                    if line.startswith("INSPECTION_STATE ")]
                            if len(rows) != 1:
                                raise RuntimeError("Inspection state was not returned: " + text)
                            return json.loads(rows[0])

                        await execute(f'addpath({matlab_string(product_dir)}); cd({matlab_string(product_dir)});')
                        bundle_before = immutable_bundle(workspace)
                        async with serve_bridge(bridge) as (servers, environment):
                            async with agent_client(root / "tutor-runtime", workspace, log,
                                    mcp_servers=servers, extra_env=environment) as client:
                                tutor = await client.thread_start(cwd=str(workspace), ephemeral=True,
                                    sandbox=Sandbox.read_only, developer_instructions=
                                    "Use read_workspace_file for workspace files and the provided MATLAB MCP tools. "
                                    "Follow the selected skill's normal tutoring permissions. "
                                    "The host filesystem tools are unavailable. Normal progress updates inside the prepared "
                                    "workspace can be written through evaluate_matlab_code; these updates remain permitted. "
                                    "Use the manifest's absolute progressPath because MATLAB's working folder is a separate product folder.")
                                startup = "Resume this mission."
                                message = await capture_turn(tutor, startup, "tutor", log, allow_tools=True,
                                    include_commentary=True, inputs=[TextInput(startup),
                                    SkillInput("mission-tutoring", str(copied / "SKILL.md"))],
                                    on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                log.emit("tutor.response", "tutor", {
                                    "stage": "organizer" if case in TIME_CASES else "presentation", "text": message})
                                if case in TIME_CASES:
                                    message = await capture_turn(tutor, "I'd like to skip the prediction and start the task.",
                                        "tutor", log, allow_tools=True, include_commentary=True,
                                        on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                    log.emit("tutor.response", "tutor", {"stage": "presentation", "text": message})
                                if case in TIME_CASES:
                                    task_title = "Visualize a continuous Sine Wave"
                                elif case in CONFIG_CASES:
                                    task_title = "Connect the model input to your data"
                                else:
                                    task_title = "Inspect the incoming signal"
                                if task_title not in message and f"Task {int(task_id[1:])}" not in message:
                                    raise RuntimeError(f"Resume did not present {task_id}: " + message)

                                # Paths and parameter names are checked in the owned installation
                                # before creating the same Inport-to-Scope state as the frozen trace.
                                if case in TIME_CASES:
                                    await prepare_time_fixture(execute, case)
                                elif case in CONFIG_CASES:
                                    await prepare_config_fixture(execute, workspace, case)
                                else:
                                    await execute('assert(strcmp(get_param("mission01/In1", "BlockType"), "Inport")); '
                                    'load_system("simulink"); '
                                    'assert(strcmp(get_param("simulink/Sinks/Scope", "BlockType"), "Scope")); '
                                    'assert(isfield(get_param("mission01", "ObjectParameters"), "ReturnWorkspaceOutputs")); '
                                    'add_block("simulink/Sinks/Scope", "mission01/InputScope"); '
                                    'add_line("mission01", "In1/1", "InputScope/1"); '
                                    'open_system("mission01/InputScope"); '
                                    'set_param("mission01", "ReturnWorkspaceOutputs", "on", "StopTime", "10"); '
                                    'ans = struct("learnerSentinel", 2718);')
                                if case in ("ans", "inspection-error"):
                                    await execute('sim("mission01");')
                                elif case in ("out", "sensorRun"):
                                    await execute(f'{case} = sim("mission01");')
                                elif case == "wrong-model":
                                    await execute('assert(strcmp(get_param("simulink/Sources/Constant", "BlockType"), "Constant")); '
                                        'assert(strcmp(get_param("simulink/Sinks/Out1", "BlockType"), "Outport")); '
                                        'new_system("inspectionOtherModel"); '
                                        'add_block("simulink/Sources/Constant", "inspectionOtherModel/Source"); '
                                        'add_block("simulink/Sinks/Out1", "inspectionOtherModel/Result"); '
                                        'add_line("inspectionOtherModel", "Source/1", "Result/1"); '
                                        'set_param("inspectionOtherModel", "ReturnWorkspaceOutputs", "on", "StopTime", "0.01"); '
                                        'out = sim("inspectionOtherModel"); close_system("inspectionOtherModel", 0);')
                                before = await backend.observe(mission_name, task_id)
                                if case in TIME_CASES:
                                    before["facts"]["simulation_time"] = await simulation_clock(execute)
                                    before["facts"]["simulation_failure_exercised"] = case == "time-failed-run"
                                initial = await state("save")
                                log.emit("inspection.checkpoint", "checker", {"stage": "before_tutor",
                                    "observation": before, "state": initial})
                                expected = "fail" if case in FIXTURE_INCOMPLETE_CASES else "pass"
                                if before["status"] != expected:
                                    raise RuntimeError("Fixture failed independent verification: " + json.dumps(before))
                                backend.inspection_unavailable = case == "inspection-error"
                                backend.config_conflict = case in ("config-conflict", "config-direct-error")
                                backend.direct_config_unavailable = case == "config-direct-error"
                                backend.tutor_simulations = 0
                                backend.injected_conflicts = 0
                                backend.direct_config_inspections = 0
                                backend.direct_config_errors = 0
                                bridge.step_id = task_id
                                response = f"Please check my current work for Task {int(task_id[1:])}."
                                if case == "time-failed-run":
                                    response = "My simulation failed. " + response
                                if case in ("config-conflict", "config-direct-error"):
                                    response = ("The current configuration looks wrong in one inspection, but I configured "
                                                "external input. Please check Task 3 again.")
                                message = await capture_turn(tutor, response, "tutor", log, allow_tools=True,
                                    include_commentary=True,
                                    on_start=lambda turn: setattr(bridge, "turn_id", turn))
                                log.emit("tutor.response", "tutor", {"stage": "verification", "text": message})
                                final = await state("check")
                                after = await backend.observe(mission_name, task_id)
                                progress = json.loads((workspace / ".interactive-missions/progress.json").read_text(encoding="utf-8"))
                                log.emit("inspection.checkpoint", "checker", {"stage": "after_tutor",
                                    "observation": after, "state": final, "progress": progress})
                                row["assertions"] = trial_assertions(case, before, after, final, message, progress,
                                    bundle_before == immutable_bundle(workspace), backend.injected_errors,
                                    task_id=task_id, next_task_id=next_task_id, tutor_simulations=backend.tutor_simulations,
                                    injected_conflicts=backend.injected_conflicts,
                                    direct_config_inspections=backend.direct_config_inspections,
                                    direct_config_errors=backend.direct_config_errors)
                                row["response"] = message
                                details = (await tutor.read()).thread
                                row["runtime"] = dict(model=details.model, model_provider=details.model_provider,
                                    reasoning_effort=details.reasoning_effort, cli_version=details.cli_version,
                                    matlab_release=product["release"])
                                row["status"] = "pass" if all(row["assertions"].values()) else "fail"
            row["workspace_removed"] = not root.exists()
        except Exception as error:
            row["error"] = error_details(error)
            log.emit("trial.error", "harness", row["error"])
    row["duration_seconds"] = time.monotonic() - started
    row["event_count"] = len(read_events(output / "events.jsonl"))
    write_json(output / "result.json", row)
    print(f'{configuration}/{case}/{trial}: {row["status"]}', flush=True)
    return row


async def validate(args):
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / "inputs"
    inputs.mkdir()
    sources = {"candidate": args.skill}
    if args.baseline:
        sources = {"baseline": args.baseline, **sources}
    hashes = {name: snapshot(path, inputs / name) for name, path in sources.items()}
    mission_sources = {"root-inports-outports": args.mission}
    if any(case in TIME_CASES for case in (args.case or DEFAULT_CASES)):
        mission_sources["continuous-and-discrete-time"] = args.toolbox_root / "marketplace/missions/continuous-and-discrete-time"
    args.missions = {}
    mission_hashes = {}
    for name, source in mission_sources.items():
        args.missions[name] = inputs / name
        mission_hashes[name] = snapshot(source, args.missions[name])
    runner_hashes = snapshot(SCRIPTS, inputs / "runner")
    args.observer = inputs / "runner/observe_mission.m"
    shutil.copyfile(__file__, inputs / "driver.py")
    write_json(args.output / "manifest.json", dict(schema_version="1.0", suite="tutor-inspection",
        run_id=args.run_id, skills=hashes, mission=mission_hashes["root-inports-outports"],
        missions=mission_hashes, runner=runner_hashes,
        driver_sha256=hashlib.sha256((inputs / "driver.py").read_bytes()).hexdigest(),
        extension_sha256=hashlib.sha256((args.toolkit_root / "tools/tools.json").read_bytes()).hexdigest(),
        cases=args.case or list(DEFAULT_CASES),
        timing_controls="Real MATLAB SimulationTime=0 after a successful run, an unexecuted run, and a failing run; no timing-field fault injection.",
        inspection_error_control="Permanent injected tutor-side outage after task presentation; safe withholding is expected.",
        trials=args.trials, trial_timeout_seconds=args.trial_timeout_seconds,
        packages={name: importlib.metadata.version(name) for name in ("openai-codex", "mcp", "PyYAML")},
        limitation="Focused live tutor regression; not mission or tutor qualification."))
    results = []
    async with asyncio.timeout(args.timeout_seconds):
        for configuration in sources:
            for case in (args.case or DEFAULT_CASES):
                if configuration == "baseline" and case != "ans":
                    continue
                for trial in range(1, args.trials + 1):
                    results.append(await run_trial(args, inputs / configuration, configuration, case, trial))
                    write_json(args.output / "result.json", results)
    lines = ["# Tutor inspection regression", "", "Each trial uses a frozen snapshot of its stock mission and authored completion checks.", "",
             "| Skill | Case | Trial | Result | Failed assertions |", "|---|---|---|---|---|"]
    for row in results:
        failures = ", ".join(name for name, value in row["assertions"].items() if not value)
        lines.append(f'| {row["configuration"]} | {row["case"]} | {row["trial"]} | {row["status"]} | {failures} |')
    lines += ["", "Baseline failures remain recorded. Unknown infrastructure results cannot establish improvement.",
              "Evidence is under each trial's events.jsonl and result.json. This diagnostic does not change historical grades."]
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all(row["status"] == "pass" for row in results if row["configuration"] == "candidate") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("matlab-server", "matlab-root", "toolkit-root", "toolbox-root", "skill", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--baseline", type=Path,
                        help="Optional baseline for the original ans incident comparison; omit for candidate-only confirmation.")
    parser.add_argument("--case", action="append", choices=CASES)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--trial-timeout-seconds", type=float, default=600)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    if min(args.trials, args.trial_timeout_seconds, args.timeout_seconds) <= 0:
        parser.error("Trial counts and time budgets must be positive")
    for name in ("matlab_server", "matlab_root", "toolkit_root", "toolbox_root", "skill", "output"):
        setattr(args, name, getattr(args, name).resolve())
    if args.baseline:
        args.baseline = args.baseline.resolve()
    args.mission = args.toolbox_root / "marketplace/missions/root-inports-outports"
    args.case = list(dict.fromkeys(args.case)) if args.case else None
    args.run_id = str(uuid.uuid4())
    return asyncio.run(validate(args))


if __name__ == "__main__":
    raise SystemExit(main())
