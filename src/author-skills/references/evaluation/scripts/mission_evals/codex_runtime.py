"""Codex SDK session and event-capture feasibility proof."""

from __future__ import annotations

import importlib.metadata
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import psutil

from openai_codex import AsyncCodex, CodexConfig, Sandbox
from openai_codex.generated.v2_all import ConfigWriteResponse, SkillsListResponse

from .events import EventLog
from .processes import OwnedProcessTree
from .workspace import prepare_codex_home


class ApprovalReviewUnavailable(RuntimeError):
    """Tool execution was blocked because automatic review could not run."""


async def isolate_skill_catalog(client, cwd, log, config_path):
    """Disable discovered host skills in the disposable client configuration.

    CODEX_HOME isolation alone does not hide the user's .agents/skills roots.
    Use the documented app-server API and verify the effective catalog before
    creating a tutor, learner, or grader thread.
    """
    params = {"cwds": [str(cwd)], "forceReload": True}
    catalog = await client._client.request("skills/list", params, response_model=SkillsListResponse)
    outside = sorted({skill.path.root for entry in catalog.data for skill in entry.skills
                      if skill.enabled and not Path(skill.path.root).resolve().is_relative_to(cwd.resolve())})
    if outside:
        # One atomic update avoids repeated config-file replacement races on Windows.
        result = await client._client.request("config/batchWrite", {
            "filePath": str(config_path.resolve()), "reloadUserConfig": True,
            "edits": [{"keyPath": "skills.config", "mergeStrategy": "replace",
                       "value": [{"path": path, "enabled": False} for path in outside]}]},
            response_model=ConfigWriteResponse)
        if Path(result.file_path.root).resolve() != config_path.resolve():
            raise RuntimeError("Skill isolation wrote outside the disposable configuration")
    verified = await client._client.request("skills/list", params, response_model=SkillsListResponse)
    enabled = [{"name": skill.name, "path": skill.path.root} for entry in verified.data for skill in entry.skills if skill.enabled]
    if any(not Path(skill["path"]).resolve().is_relative_to(cwd.resolve()) for skill in enabled):
        raise RuntimeError("Host skills remain enabled in the isolated runtime")
    log.emit("catalog.isolated", "harness", {"cwd": str(cwd), "enabled": enabled, "disabled_count": len(outside)})


async def capture_turn(thread, prompt: str, actor: str, log: EventLog, *,
                       inputs=None, allow_tools: bool = False, output_schema=None,
                       on_start=None, include_commentary: bool = False) -> str:
    log.emit("agent.input", actor, {"thread_id": thread.id, "text": prompt})
    handle = await thread.turn(inputs if inputs is not None else prompt, output_schema=output_schema)
    if on_start is not None:
        on_start(handle.id)
    final_text = None
    visible_messages = []
    completed = False
    try:
        async for event in handle.stream():
            payload = event.payload.model_dump(mode="json", by_alias=True)
            log.emit("agent.event", actor, {"method": event.method, "params": payload},
                     turn_id=handle.id)
            if event.method == "item/completed":
                item = payload["item"]
                if item.get("type") == "mcpToolCall" and item.get("error"):
                    message = item["error"].get("message", "")
                    if "Automatic approval review failed" in message:
                        raise ApprovalReviewUnavailable(message)
                if item.get("type") == "agentMessage":
                    final_text = item["text"]
                    visible_messages.append(item["text"])
                if not allow_tools and item.get("type") in {"commandExecution", "mcpToolCall", "fileChange",
                                        "dynamicToolCall", "webSearch"}:
                    raise RuntimeError("Unexpected tool use in the Codex context smoke")
            if event.method == "turn/completed":
                completed = payload["turn"]["status"] == "completed"
                if not completed:
                    raise RuntimeError(f"Codex turn did not complete: {payload['turn']}")
    except BaseException:
        # Interrupt the owned turn before SDK shutdown, including on timeout.
        try:
            await handle.interrupt()
        except Exception:
            pass
        raise
    if not completed or final_text is None:
        raise RuntimeError("Codex stream ended without a completed response")
    return ("\n\n".join(visible_messages) if include_commentary else final_text).strip()


@asynccontextmanager
async def agent_client(root: Path, cwd: Path, log: EventLog, *, model=None,
                       mcp_servers=None, extra_env=None):
    """A fresh SDK host with only the explicitly supplied MCP configuration."""
    root.mkdir()
    runtime_home = prepare_codex_home(root, model=model, mcp_servers=mcp_servers)
    config = CodexConfig(cwd=str(cwd), env={"CODEX_HOME": str(runtime_home), **(extra_env or {})},
                         client_name="interactive_missions_eval",
                         client_title="Interactive Missions Evaluation")
    client = AsyncCodex(config)
    tree = None
    existing = {(p.pid, p.create_time()) for p in psutil.Process().children(recursive=True)}
    try:
        async with client:
            distribution = importlib.metadata.distribution("openai-codex-cli-bin")
            binary_name = "codex.exe" if os.name == "nt" else "codex"
            binaries = [Path(distribution.locate_file(f)) for f in distribution.files
                        if f.name == binary_name and "bin" in f.parts]
            if len(binaries) != 1:
                raise RuntimeError("Cannot identify the pinned Codex executable")
            tree = OwnedProcessTree.discover(binaries[0], "app-server", exclude=existing)
            log.emit("process.owned", "harness", {"component": "codex", "runtime_root": str(root),
                "processes": [{"pid": p.pid, "created": p.create_time()} for p in tree.members.values()]})
            try:
                await isolate_skill_catalog(client, cwd, log, runtime_home / "config.toml")
                yield client
            finally:
                tree.capture()
    finally:
        try:
            await client.close()
        finally:
            if tree:
                log.emit("process.cleanup", "harness", dict(component="codex", **await tree.finish()))


async def prove_codex(root: Path, log: EventLog, *, model: str | None = None) -> dict:
    runtime_home = prepare_codex_home(root, model=model)
    actor_a = root / "context-a"
    actor_b = root / "context-b"
    actor_a.mkdir()
    actor_b.mkdir()
    # Configure only the child's intended Codex home; never change parent env.
    config = CodexConfig(cwd=str(actor_a), env={"CODEX_HOME": str(runtime_home)},
                         client_name="interactive_missions_eval",
                         client_title="Interactive Missions Evaluation")
    tree = None
    client = AsyncCodex(config)
    try:
        async with client:
            # Resolve the SDK-owned binary from installed distribution metadata,
            # not the unrelated (possibly broken) codex command on PATH.
            distribution = importlib.metadata.distribution("openai-codex-cli-bin")
            binary_name = "codex.exe" if os.name == "nt" else "codex"
            binaries = [Path(distribution.locate_file(f)) for f in distribution.files
                        if f.name == binary_name and "bin" in f.parts]
            if len(binaries) != 1:
                raise RuntimeError("Cannot identify the pinned Codex executable")
            tree = OwnedProcessTree.discover(binaries[0], "app-server")
            instructions = "This is a transport smoke check. Follow the requested reply format exactly. Do not use tools."
            first = await client.thread_start(cwd=str(actor_a), model=model,
                                              ephemeral=True, sandbox=Sandbox.read_only,
                                              developer_instructions=instructions)
            second = await client.thread_start(cwd=str(actor_b), model=model,
                                               ephemeral=True, sandbox=Sandbox.read_only,
                                               developer_instructions=instructions)
            if first.id == second.id:
                raise RuntimeError("Fresh Codex contexts reused a thread ID")
            marker = uuid.uuid4().hex
            ready = await capture_turn(first, f"Remember the marker {marker}. Reply only READY.", "context-a", log)
            isolated = await capture_turn(second, "If I previously gave you a marker in this conversation, reply with it. Otherwise reply only NONE.", "context-b", log)
            continued = await capture_turn(first, "Reply only with the marker I gave you earlier.", "context-a", log)
            if (ready, isolated, continued) != ("READY", "NONE", marker):
                raise RuntimeError("Codex context continuation/isolation assertions failed")
            details = (await first.read()).thread
            result = {"thread_ids": [first.id, second.id], "continuation_passed": True,
                      "fresh_context_passed": True, "model": details.model,
                      "model_provider": details.model_provider,
                      "reasoning_effort": details.reasoning_effort,
                      "cli_version": details.cli_version}
            log.emit("codex.assertions", "harness", result)
            tree.capture()
    finally:
        # An exception in __aenter__ does not invoke __aexit__. Close explicitly
        # as well so failed SDK initialization cannot leave its process running.
        try:
            await client.close()
        finally:
            if tree:
                log.emit("process.cleanup", "harness", dict(component="codex", **await tree.finish()))
    return result
