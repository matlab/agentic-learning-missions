"""Owned MATLAB MCP session and serialized, role-attributed tool calls."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from mcp import ClientSession, StdioServerParameters, stdio_client

from .events import EventLog
from .processes import OwnedProcessTree


def result_text(result) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")


class MatlabBroker:
    """One session for all roles; this is routing, not a MATLAB code sandbox."""

    def __init__(self, session, log: EventLog, *, timeout: float = 120):
        self.session = session
        self.log = log
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def call(self, actor: str, name: str, arguments: dict):
        async with self._lock:
            action_id = str(uuid.uuid4())
            self.log.emit("tool.call", actor, {"name": name, "arguments": arguments},
                          action_id=action_id)
            try:
                result = await self.session.call_tool(name, arguments,
                                                       read_timeout_seconds=self.timeout)
                self.log.emit("tool.result", actor,
                              result.model_dump(mode="json", by_alias=True), action_id=action_id)
            except BaseException as error:
                self.log.emit("tool.error", actor,
                              {"error_type": type(error).__name__, "message": str(error)},
                              action_id=action_id)
                raise
            if result.is_error:
                raise RuntimeError(f"MATLAB MCP {name} failed: {result_text(result)}")
            return result


@asynccontextmanager
async def owned_matlab(root: Path, log: EventLog, *, server: Path, matlab_root: Path, extensions=()):
    workspace = root / "matlab-workspace"
    preferences = root / "matlab-preferences"
    # Keep socket paths short and generated TLS credentials in the disposable
    # workspace. Retain only text diagnostics after the owned process exits.
    server_logs = root / "mcp"
    for folder in (workspace, preferences, server_logs):
        folder.mkdir()
    params = StdioServerParameters(
        command=str(server.resolve()),
        args=["--matlab-session-mode=new", "--matlab-display-mode=nodesktop",
              "--initial-working-folder", str(workspace), "--matlab-root", str(matlab_root),
              "--log-folder", str(server_logs),
              *[arg for path in extensions for arg in ("--extension-file", str(path))]],
        env={"MATLAB_PREFDIR": str(preferences)}, cwd=workspace)
    tree = None
    try:
        with (log.path.parent / "matlab-server.stderr.log").open("x", encoding="utf-8") as errors:
            async with stdio_client(params, errlog=errors) as streams:
                tree = OwnedProcessTree.discover(server, str(workspace))
                log.emit("process.owned", "harness", {"component": "matlab", "runtime_root": str(root),
                    "processes": [{"pid": p.pid, "created": p.create_time()} for p in tree.members.values()]})
                try:
                    async with ClientSession(*streams, read_timeout_seconds=120) as session:
                        info = await session.initialize()
                        log.emit("mcp.initialized", "harness", info.model_dump(mode="json", by_alias=True))
                        tools = await session.list_tools()
                        log.emit("mcp.tools", "harness", tools.model_dump(mode="json", by_alias=True))
                        if "evaluate_matlab_code" not in {tool.name for tool in tools.tools}:
                            raise RuntimeError("MATLAB MCP does not expose evaluate_matlab_code")
                        broker = MatlabBroker(session, log)
                        broker.tools = tools.tools
                        code = 'disp("IM_EVAL_HANDSHAKE " + jsonencode(struct("pid", matlabProcessID, "prefdir", prefdir, "cwd", pwd, "release", version("-release"), "matlabroot", matlabroot)))'
                        reply = await broker.call("harness", "evaluate_matlab_code", {"code": code})
                        lines = result_text(reply).splitlines()
                        marker = "IM_EVAL_HANDSHAKE "
                        matching = [line[len(marker):] for line in lines if line.startswith(marker)]
                        if len(matching) != 1:
                            raise RuntimeError("MATLAB ownership handshake was not returned")
                        state = json.loads(matching[0])
                        tree.capture()
                        if state["pid"] not in tree.members or state["pid"] == tree.root.pid:
                            raise RuntimeError("MATLAB process is not owned by this trial")
                        if not Path(state["prefdir"]).resolve().is_relative_to(preferences.resolve()):
                            raise RuntimeError("MATLAB did not use the isolated preference directory")
                        if Path(state["cwd"]).resolve() != workspace.resolve():
                            raise RuntimeError("MATLAB did not start in the trial workspace")
                        if Path(state["matlabroot"]).resolve() != matlab_root.resolve():
                            raise RuntimeError("MATLAB started from a different installation")
                        log.emit("matlab.ownership", "harness", state)
                        yield broker, state
                finally:
                    tree.capture()
    finally:
        try:
            if tree:
                log.emit("process.cleanup", "harness", dict(component="matlab", **await tree.finish()))
        finally:
            for source in server_logs.rglob("*.log"):
                if source.is_file() and not source.is_symlink():
                    destination = log.path.parent / "matlab-server-logs" / source.relative_to(server_logs)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)


async def prove_matlab(root: Path, log: EventLog, *, server: Path, matlab_root: Path) -> dict:
    before = {(p.pid, p.create_time()) for p in psutil.process_iter()
              if p.name().lower() == "matlab.exe"}
    async with owned_matlab(root, log, server=server, matlab_root=matlab_root) as (broker, state):
        if (state["pid"], psutil.Process(state["pid"]).create_time()) in before:
            raise RuntimeError("Trial reused an existing MATLAB process")
        # The harness drives both roles in Milestone 1. Native tutor and learner
        # tool adapters are added with their respective evaluation suites.
        await broker.call("learner", "evaluate_matlab_code", {"code": "imEvalValue = 42;"})
        reply = await broker.call("tutor", "evaluate_matlab_code", {
            "code": 'assert(imEvalValue == 42); disp("IM_EVAL_SHARED_STATE_OK")'})
        if "IM_EVAL_SHARED_STATE_OK" not in result_text(reply):
            raise RuntimeError("Roles did not observe the same MATLAB state")
        result = {"pid": state["pid"], "release": state["release"],
                  "new_process_passed": True, "isolated_preferences_passed": True,
                  "shared_state_passed": True, "role_driver": "harness"}
        log.emit("matlab.assertions", "harness", result)
    return result
