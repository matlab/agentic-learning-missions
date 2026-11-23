"""Loopback MCP bridge for an isolated tutor trial."""

import asyncio
import hmac
import json
import re
import secrets
import socket
import uuid
from contextlib import asynccontextmanager

import uvicorn
from mcp.server import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

from .matlab_runtime import result_text
from .skill_assets import matlab_string


def text_result(text, *, error=False):
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=error)


def inspects_state(code):
    return bool(re.search(r"\bsampleRate\b|\bwhos\b", code))


def assigns_learner_value(code):
    return bool(re.search(r"\bsampleRate\s*=(?!=)|assignin\s*\([^,]+,\s*['\"]sampleRate['\"]", code))


class ScalarBackend:
    """Controlled scalar observations or forwarding to the same live MATLAB session."""

    def __init__(self, live=None):
        self.live = live
        self.value = None
        self.tool_errors = {}

    def configure_step(self, step):
        errors = step.get("tool_errors", {})
        if errors and self.live:
            raise ValueError("Scripted tool errors are supported only by controlled behavior cases")
        self.tool_errors = dict(errors)

    async def set_state(self, value):
        self.value = value
        if self.live:
            assignment = "clear sampleRate;" if value is None else f"sampleRate = {json.dumps(value)};"
            await self.live.call("driver", "evaluate_matlab_code",
                                 {"code": assignment + " protectedSentinel = 2718;"})

    async def state(self):
        if not self.live:
            return {"sample_rate": self.value, "protected_sentinel": 2718, "temporaries": []}
        code = ('mcpTmp_evalState = struct("sample_rate", [], "protected_sentinel", [], '
                '"temporaries", {who("mcpTmp_*")}); '
                'if exist("sampleRate","var"), mcpTmp_evalState.sample_rate = sampleRate; end; '
                'if exist("protectedSentinel","var"), mcpTmp_evalState.protected_sentinel = protectedSentinel; end; '
                'disp("EVAL_STATE " + jsonencode(mcpTmp_evalState)); clear mcpTmp_evalState;')
        reply = await self.live.call("harness", "evaluate_matlab_code", {"code": code})
        rows = [row[len("EVAL_STATE "):] for row in result_text(reply).splitlines()
                if row.startswith("EVAL_STATE ")]
        if len(rows) != 1:
            raise RuntimeError("Independent product observation is missing")
        state = json.loads(rows[0])
        if state["sample_rate"] == []:
            state["sample_rate"] = None
        return state

    async def call(self, name, arguments):
        if name in self.tool_errors:
            return text_result(self.tool_errors[name], error=True)
        if self.live:
            if name != "evaluate_matlab_code":
                return await self.live.call("tutor", name, arguments)
            # Core Server 0.10.1 can return MATLAB errors with isError=false.
            # Run the exact requested code under a try/catch with an explicit
            # success marker; never turn an unsuccessful inspection into proof.
            marker = "IM_EVAL_OK_" + uuid.uuid4().hex
            wrapped = (f'try; eval(jsondecode({matlab_string(json.dumps(arguments["code"]))})); '
                       f'disp("{marker}"); catch mcpTmp_bridgeError; '
                       'disp("MATLAB evaluation failed: " + string(mcpTmp_bridgeError.message)); '
                       'clear mcpTmp_bridgeError; end;')
            reply = await self.live.call("tutor", name, {**arguments, "code": wrapped})
            rows = result_text(reply).splitlines()
            succeeded = marker in rows
            text = "\n".join(row for row in rows if row != marker)
            return text_result(text or ("MATLAB inspection completed." if succeeded else "MATLAB inspection did not complete."),
                               error=not succeeded)
        if name == "detect_matlab_toolboxes":
            return text_result("MATLAB R2026b is installed. MATLAB MCP is connected.")
        code = arguments["code"]
        if assigns_learner_value(code):
            return text_result("This observation backend does not execute learner-state edits.", error=True)
        if inspects_state(code):
            variable = {"name": "sampleRate", "exists": self.value is not None}
            if self.value is not None:
                variable.update(value=self.value, **{"class": "double", "size": [1, 1]})
            return text_result("Current MATLAB base-workspace observation (exact variable names): " +
                               json.dumps({"variables": [variable, {"name": "protectedSentinel", "exists": True,
                                                                   "value": 2718, "class": "double", "size": [1, 1]}]}))
        if "mcpTmp" in code or "clear" in code:
            return text_result("Inspection temporaries cleared. Learner variables are unchanged.")
        return text_result("MATLAB release: R2026b. MATLAB MCP is available. No learner-state observation was requested.")


class TutorBridge:
    def __init__(self, workspace, backend, log):
        self.workspace = workspace.resolve()
        self.backend = backend
        self.log = log
        self.step_id = None
        self.turn_id = None
        self.calls = []
        self.lock = asyncio.Lock()
        self.schemas = {
            "read_workspace_file": {"type": "object", "properties": {"path": {"type": "string"}},
                                    "required": ["path"], "additionalProperties": False},
            "evaluate_matlab_code": {"type": "object", "properties": {
                "code": {"type": "string"}, "project_path": {"type": "string"}},
                "required": ["code"], "additionalProperties": False},
            "detect_matlab_toolboxes": {"type": "object", "properties": {}, "additionalProperties": False}}
        descriptions = {
            "read_workspace_file": "Read a UTF-8 file inside the prepared learner workspace, including manifest, mission YAML, and tutor references. Relative paths are relative to the workspace root.",
            "evaluate_matlab_code": "Inspect the active MATLAB workspace using MATLAB code. Respect the mission's read-only tutoring rules and temporary-variable cleanup requirements.",
            "detect_matlab_toolboxes": "List installed MATLAB products and versions."}
        self.tools = [Tool(name=name, description=descriptions[name], input_schema=schema,
                          annotations=ToolAnnotations(
                              read_only_hint=name != "evaluate_matlab_code" or backend.live is None,
                              destructive_hint=name == "evaluate_matlab_code" and backend.live is not None,
                              open_world_hint=name == "evaluate_matlab_code" and backend.live is not None))
                      for name, schema in self.schemas.items()]

    async def list_tools(self, context, params):
        return ListToolsResult(tools=self.tools)

    async def call_tool(self, context, params):
        return await self.call(params.name, params.arguments or {})

    async def call(self, name, arguments):
        async with self.lock:
            entry = {"name": name, "arguments": arguments, "step_id": self.step_id,
                     "observation": name == "evaluate_matlab_code" and inspects_state(arguments.get("code", "")),
                     "learner_write_attempt": name == "evaluate_matlab_code" and assigns_learner_value(arguments.get("code", ""))}
            entry["event_id"] = self.log.emit("bridge.call", "tutor", entry, turn_id=self.turn_id)
            self.calls.append(entry)
            try:
                if name not in self.schemas:
                    raise ValueError("Tool is not exposed to this role")
                if name == "read_workspace_file":
                    path = (self.workspace / arguments["path"]).resolve()
                    if not path.is_relative_to(self.workspace):
                        raise ValueError("File reads must stay inside the prepared workspace")
                    result = text_result(path.read_text(encoding="utf-8"))
                else:
                    if arguments.get("project_path") and (self.workspace / arguments["project_path"]).resolve() != self.workspace:
                        raise ValueError("MATLAB project_path must remain the prepared workspace")
                    result = await self.backend.call(name, arguments)
            except Exception as error:
                result = text_result(str(error), error=True)
            entry["result_event_id"] = self.log.emit("bridge.result", "tutor", {
                "step_id": self.step_id, "call_event_id": entry["event_id"],
                "result": result.model_dump(mode="json", by_alias=True)}, turn_id=self.turn_id)
            entry["is_error"] = result.is_error
            return result


@asynccontextmanager
async def serve_bridge(bridge):
    server = Server("matlab", version="1.0", on_list_tools=bridge.list_tools,
                    on_call_tool=bridge.call_tool, get_tool_input_schema=bridge.schemas.get,
                    instructions="Use read_workspace_file to read the prepared mission and tutor reference files. Follow the mission's normal tutoring permissions.")
    application = server.streamable_http_app(stateless_http=True, json_response=True)
    token = secrets.token_urlsafe(32)

    async def authorized(scope, receive, send):
        if scope["type"] == "http":
            supplied = dict(scope.get("headers", [])).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, ("Bearer " + token).encode()):
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await application(scope, receive, send)

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    http = uvicorn.Server(uvicorn.Config(authorized, log_level="error", access_log=False,
                                         lifespan="on", timeout_graceful_shutdown=5))
    task = asyncio.create_task(http.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not http.started:
                if task.done():
                    await task
                    raise RuntimeError("MCP bridge did not start")
                await asyncio.sleep(0.01)
        bridge.log.emit("bridge.started", "harness", {"transport": "loopback-http", "tools": list(bridge.schemas)})
        yield {"matlab": {"url": f"http://127.0.0.1:{listener.getsockname()[1]}/mcp",
                           "bearer_token_env_var": "IM_EVAL_BRIDGE_TOKEN", "required": True,
                           "tool_timeout_sec": 150}}, {"IM_EVAL_BRIDGE_TOKEN": token}
    finally:
        http.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=10)
        finally:
            listener.close()
