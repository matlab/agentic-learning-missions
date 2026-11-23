"""Immutable inputs and prepared workspaces for skill evaluation cases."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .events import write_json
from .matlab_runtime import result_text


def file_hashes(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Snapshot inputs must not contain symlinks: {path}")
        if path.is_file() and not {"__pycache__", ".git"}.intersection(path.relative_to(root).parts):
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def snapshot(source: Path, destination: Path) -> dict:
    source = source.resolve()
    if destination.resolve().is_relative_to(source):
        raise ValueError("Snapshot output must be outside its input directory")
    hashes = file_hashes(source)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    if file_hashes(destination) != hashes:
        raise RuntimeError("Input changed while its snapshot was being copied")
    return {"sha256": digest(hashes), "files": hashes}


def skill_metadata(skill: Path) -> dict:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("Skill must contain YAML frontmatter")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    if metadata.get("name") != "mission-tutoring" or not metadata.get("description"):
        raise ValueError("Expected the mission-tutoring skill and its description")
    return metadata


def protected_hashes(workspace: Path) -> dict:
    result = {}
    for directory in (".interactive-missions", ".codex"):
        if (workspace / directory).exists():
            result[directory] = file_hashes(workspace / directory)
    if (workspace / "AGENTS.md").exists():
        result["AGENTS.md"] = hashlib.sha256((workspace / "AGENTS.md").read_bytes()).hexdigest()
    return result


def prepare_behavior_workspace(workspace: Path, fixture: Path, skill: Path) -> Path:
    """Fixture-only counterpart to the live prepareWorkspace API; never uses MATLAB."""
    workspace.mkdir()
    runtime = workspace / ".interactive-missions"
    runtime.mkdir()
    shutil.copytree(fixture, runtime / "content")
    shutil.copytree(skill, runtime / "skills/mission-tutoring")
    copied_skill = workspace / ".codex/skills/mission-tutoring"
    shutil.copytree(skill, copied_skill)
    mission = yaml.safe_load((fixture / "mission.yaml").read_text(encoding="utf-8"))
    write_json(runtime / "manifest.json", {
        "schemaVersion": "1.0", "progressSchemaVersion": "2.0", "toolboxVersion": "0.0.1",
        "workspaceRoot": str(workspace), "runtimeRoot": str(runtime),
        "contentRoot": str(runtime / "content"), "skillRoot": str(runtime / "skills/mission-tutoring"),
        "marketplaceSource": "evaluation-fixture", "missionName": fixture.name,
        "missionId": mission["mission_id"], "missionVersion": mission["version"],
        "missionTitle": mission["title"], "mode": "practice", "agentClient": "codex",
        "progressPath": "", "resumableProgressPath": str(runtime / "progress.json"),
        "taskIds": [task["id"] for task in mission["tasks"]], "allowAgentEdits": False,
        "createdAt": datetime.now(timezone.utc).isoformat(), "files": []})
    (workspace / "AGENTS.md").write_text(
        "# Prepared learner workspace\n\nWhen the learner asks to start or resume this mission, "
        "use mission-tutoring. Read .interactive-missions/manifest.json before setup.\n",
        encoding="utf-8")
    return copied_skill


def matlab_string(value) -> str:
    return '"' + str(value).replace('"', '""') + '"'


async def prepare_live_workspace(broker, workspace: Path, fixture: Path,
                                 skill: Path, toolbox_root: Path) -> Path:
    code = (f"addpath({matlab_string(toolbox_root / 'src')}); "
            "mcpTmp_preparedWorkspace = interactiveMissions.prepareWorkspace("
            f"WorkspaceRoot={matlab_string(workspace)}, MissionName={matlab_string(fixture.name)}, "
            f"ContentRoot={matlab_string(fixture)}, TutorSkillRoot={matlab_string(skill)}, "
            'RegisterWorkspace=false, Mode="practice", RequireEmpty=true); clear mcpTmp_preparedWorkspace; '
            f'cd({matlab_string(workspace)}); disp("IM_EVAL_PREPARED");')
    reply = await broker.call("harness", "evaluate_matlab_code", {"code": code})
    if "IM_EVAL_PREPARED" not in result_text(reply).splitlines():
        raise RuntimeError("Workspace provisioning did not complete: " + result_text(reply))
    return workspace / ".codex/skills/mission-tutoring"
