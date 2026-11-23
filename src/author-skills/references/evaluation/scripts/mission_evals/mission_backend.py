"""Full installed MCP forwarding, without the scalar fixture assumptions."""

import json
import re
import uuid

from mcp.types import Tool, ToolAnnotations

from .matlab_runtime import result_text
from .skill_assets import matlab_string
from .skill_bridge import TutorBridge, text_result

READ_TOOLS = {"evaluate_matlab_code", "detect_matlab_toolboxes", "model_read", "model_overview",
              "model_query_params", "model_resolve_params"}
LEARNER_TOOLS = READ_TOOLS | {"model_edit"}


class MissionBackend:
    def __init__(self, broker, workspace, observer):
        self.live = broker
        self.workspace = workspace
        self.observer = observer
        self.simulation_baselines = {}

    async def call(self, name, arguments, actor="tutor"):
        if name == "run_matlab_file":
            path = (self.workspace / arguments["script_path"]).resolve()
            content = self.workspace / ".interactive-missions/content"
            if not path.is_relative_to(content) or path.suffix != ".m":
                raise ValueError("Only mission-owned setup scripts may be run by the tutor")
            # Execute in base workspace, without run_matlab_file's directory change.
            name, arguments = "evaluate_matlab_code", {"code": path.read_text(encoding="utf-8")}
        if name != "evaluate_matlab_code":
            return await self.live.call(actor, name, arguments)
        marker = "IM_EVAL_OK_" + uuid.uuid4().hex
        code = arguments["code"]
        # Core Server's Live Editor transport otherwise creates transient inline
        # figures and deletes them on the next call. Restore normal MATLAB
        # defaults before executing exact user code; explicit figure choices and
        # omitted plotting actions remain untouched.
        wrapped = ('try; set(groot,"DefaultFigureVisible","on"); '
                   f'eval(jsondecode({matlab_string(json.dumps(code))})); disp("{marker}"); '
                   'catch mcpTmp_bridgeError; disp("MATLAB evaluation failed: " + string(mcpTmp_bridgeError.message)); '
                   'clear mcpTmp_bridgeError; end;')
        reply = await self.live.call(actor, name, {"code": wrapped})
        rows = result_text(reply).splitlines()
        return text_result("\n".join(r for r in rows if r != marker), error=marker not in rows)

    async def observe(self, mission, task):
        # Function workspace keeps grader locals out of the learner's base workspace.
        code = (f'addpath({matlab_string(self.observer.parent)}); '
                f'disp("IM_OBSERVATION " + jsonencode(observe_mission({matlab_string(mission)}, {matlab_string(task or "")}))); '
                f'rmpath({matlab_string(self.observer.parent)});')
        reply = await self.call("evaluate_matlab_code", {"code": code}, "checker")
        matches = [line[len("IM_OBSERVATION "):] for line in result_text(reply).splitlines()
                   if line.startswith("IM_OBSERVATION ")]
        if reply.is_error or len(matches) != 1:
            raise RuntimeError("Independent observation failed: " + result_text(reply))
        observation = json.loads(matches[0])
        # These tasks explicitly change the preceding task's source timing and
        # require another run. An older SimulationOutput cannot prove that run.
        if mission == "continuous-and-discrete-time" and task in ("t02", "t03"):
            stamp = observation["facts"].get("latest_simulation_start", 0)
            baseline = self.simulation_baselines.setdefault(task, stamp)
            observation["facts"]["task_simulation_baseline"] = baseline
            if observation["status"] == "pass" and stamp <= baseline:
                observation["status"] = "fail"
                observation["reason"] = "No new current-model SimulationOutput after the required timing change"
        return observation


class MissionBridge(TutorBridge):
    def __init__(self, workspace, backend, log):
        super().__init__(workspace, backend, log)
        installed = {t.name: t for t in backend.live.tools}
        required = {"evaluate_matlab_code", "model_read", "model_query_params", "model_edit"}
        if required - installed.keys():
            raise RuntimeError(f"Installed MCP capabilities missing: {sorted(required - installed.keys())}")
        reader = self.tools[0]
        self.tools = [reader] + [installed[name] for name in sorted(READ_TOOLS | {"run_matlab_file"}) if name in installed]
        # Executable code and setup retain their real potentially destructive annotations.
        self.schemas = {t.name: t.input_schema for t in self.tools}


def validate_learner_call(name, arguments, installed):
    """Prevent accidental hidden-input access; not a sandbox for hostile MATLAB."""
    import jsonschema
    if name not in LEARNER_TOOLS or name not in installed:
        raise ValueError("Tool is not exposed to the learner")
    jsonschema.validate(arguments, installed[name].input_schema)
    text = json.dumps(arguments)
    if re.search(r"mission\.yaml|\.interactive-missions|\.codex|observe_mission|evals[/\\]|SKILL\.md", text, re.I):
        raise ValueError("Learner actions cannot read hidden mission or grading inputs")
    if name == "evaluate_matlab_code" and re.search(
            r"\b(fileread|fopen|readlines|readstruct|readtable|load|run|system|unix|dos|webread|cd|addpath|rmpath|delete|rmdir)\s*\(", arguments["code"], re.I):
        raise ValueError("File/system access is outside learner product actions")
    if "project_path" in arguments:
        raise ValueError("Learner cannot change the product working directory")
