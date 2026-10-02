"""Static smoke tests for the toolbox-first Interactive Missions framework."""

from __future__ import annotations

import re
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install it, then rerun this command.")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / "marketplace"
CONTENT = MARKETPLACE / "missions"
LEARNER_SKILL = ROOT / "src" / "skills" / "mission-tutoring" / "SKILL.md"
RUNTIME_ADAPTERS = ROOT / "src" / "adapters"
PACKAGED_AUTHOR_SKILLS = ROOT / "src" / "author-skills"
SHARED_AUTHOR_REFERENCES = PACKAGED_AUTHOR_SKILLS / "references"
AUTHOR_ADAPTERS = ROOT / "src" / "author-adapters"
FALLBACK_THUMBNAILS = ROOT / "src" / "app" / "assets" / "thumbnails"
ALLOWED_MCP_TOOLS = {
    "check_matlab_code",
    "detect_matlab_toolboxes",
    "evaluate_matlab_code",
    "model_check",
    "model_edit",
    "model_overview",
    "model_query_params",
    "model_read",
    "model_read_diagnostics",
    "model_resolve_params",
    "model_test",
    "run_matlab_file",
    "run_matlab_test_file",
}
ALLOWED_COMPLETION_KINDS = {"learner_confirmation"}
AUTHOR_ONLY_SKILLS = {"create-tutor-mission", "qa-mission", "maintain-missions"}
SUPPORTED_ADAPTER_IDS = {
    "codex",
    "claude-code",
    "gemini-cli",
    "github-copilot-vscode",
    "github-copilot-cli",
    "generic",
}
FORBIDDEN_MATLAB_PATTERNS = [
    (re.compile(r"^\s*cd\s*(?:\(|\s|$)", re.IGNORECASE), "cd"),
    (re.compile(r"^\s*rmdir\s*(?:\(|\s|$)", re.IGNORECASE), "rmdir"),
    (re.compile(r"^\s*delete\s*(?:\(|\s|$)", re.IGNORECASE), "delete"),
    (re.compile(r"\bprogress[\\/]", re.IGNORECASE), "progress-file write"),
    (re.compile(r"\bfopen\s*\([^)]*progress", re.IGNORECASE), "progress-file write"),
]
FORBIDDEN_INITIAL_GUIDANCE_PATTERNS = [
    (re.compile(r"\b(?:add_block|add_line|new_system|open_system|set_param|plot|sim)\s*\(", re.IGNORECASE), "runnable MATLAB or Simulink command"),
    (re.compile(r"\bsimulink/[A-Za-z0-9_/]+", re.IGNORECASE), "Simulink library path"),
    (re.compile(r"\b(?:double-?click|right-?click|drag-and-drop|click)\b", re.IGNORECASE), "UI action sequence"),
    (re.compile(r"\b(?:model settings|data import/export)\s*>\s*", re.IGNORECASE), "UI path"),
    (re.compile(r"\b\d+(?:\.\d+)?\s*(?:Hz|kHz)\b", re.IGNORECASE), "exact rate value"),
]


class SmokeFailure(AssertionError):
    """Raised for expected smoke-test assertion failures."""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SmokeFailure(f"{rel(path)} is not valid YAML: {exc}") from exc
    require(isinstance(data, dict), f"{rel(path)} must parse to a mapping")
    return data


def git_ls_files(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def mission_paths() -> list[Path]:
    paths = sorted(path for path in CONTENT.glob("*/mission.yaml") if not path.name.startswith("draft_"))
    require(paths, "marketplace/missions must include at least one mission.yaml file")
    return paths


def mission_name_from_path(path: Path) -> str:
    require(path.name == "mission.yaml", f"mission files must be named mission.yaml: {rel(path)}")
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.parent.name) is not None,
            f"mission folder must use a lowercase slug: {rel(path.parent)}")
    return path.parent.name


def check_layout() -> None:
    for path in [
        ROOT / "src" / "interactiveMissionsApp.m",
        ROOT / "src" / "app" / "index.html",
        ROOT / "src" / "app" / "app.js",
        ROOT / "src" / "app" / "styles.css",
        FALLBACK_THUMBNAILS / "gradcap.svg",
        FALLBACK_THUMBNAILS / "matlab1.svg",
        FALLBACK_THUMBNAILS / "simulink1.svg",
        ROOT / "src" / "+interactiveMissions" / "openApp.m",
        ROOT / "src" / "+interactiveMissions" / "prepareWorkspace.m",
        ROOT / "buildfile.m",
        MARKETPLACE / "manifest.yaml",
        CONTENT,
        LEARNER_SKILL,
        RUNTIME_ADAPTERS,
        PACKAGED_AUTHOR_SKILLS,
        AUTHOR_ADAPTERS,
        ROOT / "src" / "startMissionAuthoring.m",
        ROOT / "src" / "+interactiveMissions" / "startMissionAuthoring.m",
        ROOT / "tests",
    ]:
        require(path.exists(), f"missing toolbox layout path: {rel(path)}")

    app_root = ROOT / "src" / "app"
    require(len(list(app_root.glob("*.html"))) == 1,
            "src/app must contain exactly one HTML file")
    require(len(list(app_root.glob("*.js"))) == 1,
            "src/app must contain exactly one JavaScript file")
    require(len(list(app_root.glob("*.css"))) == 1,
            "src/app must contain exactly one stylesheet")

    for path in [ROOT / "plugins", ROOT / ".claude-plugin", ROOT / ".agents" / "plugins", ROOT / "resources"]:
        require(not path.exists(), f"old plugin layout path must not exist: {rel(path)}")
    for contract_name in ["mission-contract.md", "progress-contract.md", "platform-qualification.md"]:
        require((SHARED_AUTHOR_REFERENCES / contract_name).is_file(),
                f"shared author reference is missing: {contract_name}")
    for path in [
        ROOT / "src" / "+interactiveMissions" / "importMissionPack.m",
        ROOT / "src" / "+interactiveMissions" / "exportMissionPack.m",
        ROOT / "src" / "+interactiveMissions" / "+internal" / "userMissionLibraryRoot.m",
    ]:
        require(not path.exists(), f"old single-mission library API must not exist: {rel(path)}")

    manifest = load_yaml(MARKETPLACE / "manifest.yaml")
    for field in ["schema_version", "id", "title", "source_url", "content_version", "minimum_toolbox_version"]:
        require(isinstance(manifest.get(field), str) and manifest[field].strip(),
                f"marketplace/manifest.yaml missing required field: {field}")
    require(manifest.get("schema_version") == "2.0", "marketplace/manifest.yaml must declare schema_version 2.0")
    require(isinstance(manifest.get("missions"), list) and manifest["missions"],
            "marketplace/manifest.yaml must list missions")
    adapters = manifest.get("adapters")
    require(isinstance(adapters, list) and adapters, "marketplace/manifest.yaml must list adapters")
    adapter_ids = {adapter.get("id") for adapter in adapters if isinstance(adapter, dict)}
    require(adapter_ids == SUPPORTED_ADAPTER_IDS,
            f"marketplace manifest adapter IDs must be {sorted(SUPPORTED_ADAPTER_IDS)}")
    for adapter in adapters:
        require(isinstance(adapter, dict), "adapter manifest entries must be mappings")
        adapter_id = adapter.get("id")
        require(isinstance(adapter_id, str) and (RUNTIME_ADAPTERS / adapter_id / "adapter.yaml").is_file(),
                f"src adapter is missing: {adapter_id}")

    packaging_text = (ROOT / "buildfile.m").read_text(encoding="utf-8")
    for phrase in ["ToolboxOptions", "AppGalleryFiles", "PackageDependencies", "ProductDependencies"]:
        require(phrase in packaging_text, f"buildfile.m must configure {phrase}")
    require("sourceRoot" in packaging_text and "docsRoot" in packaging_text and
            "opts.ToolboxFiles" in packaging_text,
            "buildfile.m must package learner and author documentation with the toolbox")

    buildfile_text = packaging_text
    for phrase in ["buildplan", "packageTask", "buildToolbox"]:
        require(phrase in buildfile_text, f"buildfile.m must configure {phrase}")


def check_missions() -> None:
    for mission_path in mission_paths():
        mission = load_yaml(mission_path)
        mission_name = mission_name_from_path(mission_path)
        for field in [
            "mission_id", "version", "title", "objective", "supported_matlab_releases",
            "required_capabilities", "write_mode", "capability_mode", "app", "tasks",
        ]:
            require(field in mission, f"{rel(mission_path)} missing required field: {field}")

        require(isinstance(mission["mission_id"], str) and re.fullmatch(r"\d{2}", mission["mission_id"]),
                f"{mission_path.name} must declare a quoted two-digit mission_id")
        if "allow_agent_edits" in mission:
            require(isinstance(mission["allow_agent_edits"], bool),
                    f"{rel(mission_path)} allow_agent_edits must be boolean")
        require(mission["write_mode"] in {"read_inspect", "allow_agent_edits"},
                f"{rel(mission_path)} write_mode uses an unsupported value")
        require(mission["capability_mode"] in {"guided_tutor", "agent_build", "review_only"},
                f"{rel(mission_path)} capability_mode uses an unsupported value")
        for field in ["supported_matlab_releases", "required_capabilities"]:
            values = mission.get(field)
            require(isinstance(values, list) and values and all(isinstance(item, str) and item for item in values),
                    f"{rel(mission_path)} {field} must be a non-empty text list")
        check_thumbnail(mission_path, mission)
        check_app_metadata(mission_path, mission["app"])
        check_tasks(mission_path, mission["tasks"])

        setup = mission.get("setup")
        if setup is not None:
            require(isinstance(setup, dict), f"{rel(mission_path)} setup must be a mapping")
            setup_script = setup.get("script")
            require(isinstance(setup_script, str) and setup_script, f"{rel(mission_path)} setup.script is required")
            require((mission_path.parent / setup_script).is_file(),
                    f"{rel(mission_path)} setup script is missing: {setup_script}")

        reset_folder = mission_path.parent / f"task_reset_{mission_name}"
        if reset_folder.is_dir():
            for task in mission["tasks"][1:]:
                reset_file = reset_folder / f"reset_{task['id']}.m"
                require(reset_file.is_file(), f"missing reset script: {rel(reset_file)}")

        if mission_name == "continuous-and-discrete-time":
            check_continuous_and_discrete_time_source_contract(mission_path, mission)


def check_continuous_and_discrete_time_source_contract(mission_path: Path, mission: dict) -> None:
    require(mission.get("version") == "1.0.1",
            f"{rel(mission_path)} must increment its version to 1.0.1")
    tasks = mission["tasks"]
    require(len(tasks) >= 4, f"{rel(mission_path)} must define Tasks 1-4")
    expected_phrases = {
        "t01": ["Sine Wave block configured for continuous-time", "Sine Wave source", "continuous-time output"],
        "t02": ["same Sine Wave block", "positive finite sample interval", "Sine Wave source"],
        "t03": ["Sine Wave source to continuous-time output", "continuous-time Sine Wave source", "Sine Wave is continuous"],
        "t04": ["continuous Sine Wave output", "sampled signal derived from that Sine Wave", "continuous Sine Wave"],
    }
    for task in tasks[:4]:
        task_id = task["id"]
        task_text = " ".join([
            task["title"],
            task["instruction"],
            task["completion"]["description"],
            *(item["check"] for item in task["completion"]["strategy"]),
            *task["hints"],
        ])
        for phrase in expected_phrases[task_id]:
            require(phrase in task_text,
                    f"{rel(mission_path)} {task_id} must consistently require a Sine Wave source: {phrase!r}")
    first_task_text = " ".join([
        tasks[0]["instruction"],
        tasks[0]["completion"]["description"],
        *(item["check"] for item in tasks[0]["completion"]["strategy"]),
    ]).lower()
    for forbidden_phrase in ["any continuously varying signal source", "equivalent signal-producing subsystem"]:
        require(forbidden_phrase not in first_task_text,
                f"{rel(mission_path)} t01 must not accept an alternate source: {forbidden_phrase!r}")


def check_thumbnail(mission_path: Path, mission: dict) -> None:
    if "thumbnail" not in mission or not str(mission["thumbnail"]).strip():
        return

    thumbnail = mission["thumbnail"]
    require(isinstance(thumbnail, str),
            f"{rel(mission_path)} thumbnail must be text when declared")
    require(Path(thumbnail).suffix.lower() in {".png", ".svg"},
            f"{rel(mission_path)} thumbnail must be a PNG or SVG: {thumbnail}")
    require((mission_path.parent / thumbnail).is_file() or (MARKETPLACE / thumbnail).is_file(),
            f"{rel(mission_path)} thumbnail is missing: {thumbnail}")


def check_app_metadata(mission_path: Path, app: object) -> None:
    require(isinstance(app, dict), f"{rel(mission_path)} app metadata must be a mapping")
    for field in ["summary", "audience", "difficulty", "status"]:
        require(isinstance(app.get(field), str) and app[field].strip(),
                f"{rel(mission_path)} app.{field} must be non-empty text")
    require(app.get("difficulty") in {"beginner", "intermediate", "advanced", "unspecified"},
            f"{rel(mission_path)} app.difficulty uses an unsupported value")
    require(app.get("status") in {"published", "draft", "demo", "deprecated"},
            f"{rel(mission_path)} app.status uses an unsupported value")
    require(isinstance(app.get("estimated_minutes"), int) and app["estimated_minutes"] > 0,
            f"{rel(mission_path)} app.estimated_minutes must be positive")
    require(isinstance(app.get("learner_visible"), bool),
            f"{rel(mission_path)} app.learner_visible must be boolean")
    for field in ["products", "topics"]:
        values = app.get(field)
        require(isinstance(values, list) and values and all(isinstance(item, str) and item for item in values),
                f"{rel(mission_path)} app.{field} must be a non-empty text list")


def check_tasks(mission_path: Path, tasks: object) -> None:
    require(isinstance(tasks, list) and tasks, f"{rel(mission_path)} tasks must be a non-empty list")
    expected_ids = [f"t{index:02d}" for index in range(1, len(tasks) + 1)]
    for task, expected_id in zip(tasks, expected_ids):
        require(isinstance(task, dict), f"{rel(mission_path)} each task must be a mapping")
        require(task.get("id") == expected_id,
                f"{rel(mission_path)} task IDs must be sequential; expected {expected_id}")
        for field in ["title", "instruction", "completion", "hints"]:
            require(task.get(field), f"{rel(mission_path)} {expected_id} missing required field: {field}")
        check_learner_guidance(mission_path, expected_id, task)
        completion = task["completion"]
        require(isinstance(completion, dict), f"{rel(mission_path)} {expected_id} completion must be a mapping")
        strategy = completion.get("strategy")
        require(isinstance(strategy, list) and strategy,
                f"{rel(mission_path)} {expected_id} completion.strategy must be non-empty")
        for check in strategy:
            require(isinstance(check, dict), f"{rel(mission_path)} {expected_id} completion item must be a mapping")
            tool = check.get("tool")
            kind = check.get("kind")
            require(isinstance(check.get("check"), str) and check["check"].strip(),
                    f"{rel(mission_path)} {expected_id} completion item must include non-empty check text")
            if tool is not None:
                require(tool in ALLOWED_MCP_TOOLS,
                        f"{rel(mission_path)} {expected_id} uses unsupported MCP tool {tool!r}")
            else:
                require(kind in ALLOWED_COMPLETION_KINDS,
                        f"{rel(mission_path)} {expected_id} uses unsupported completion kind {kind!r}")


def check_learner_guidance(mission_path: Path, task_id: str, task: dict) -> None:
    hints = task["hints"]
    require(isinstance(hints, list) and 1 <= len(hints) <= 3,
            f"{rel(mission_path)} {task_id} hints must be an ordered list of 1-3 items")
    require(all(isinstance(hint, str) and hint.strip() for hint in hints),
            f"{rel(mission_path)} {task_id} hints must contain non-empty text")

    learner_text = [task["title"], task["instruction"], *hints]
    require(all(isinstance(text, str) and text.strip() for text in learner_text),
            f"{rel(mission_path)} {task_id} learner-facing text must be non-empty")
    for text in [task["title"], task["instruction"]]:
        for pattern, description in FORBIDDEN_INITIAL_GUIDANCE_PATTERNS:
            require(pattern.search(text) is None,
                    f"{rel(mission_path)} {task_id} initial task text must not include {description}")


def strip_matlab_comments(text: str) -> str:
    return "\n".join(line.split("%", 1)[0] for line in text.splitlines())


def check_matlab_scripts() -> None:
    scripts: list[Path] = []
    for mission_path in mission_paths():
        mission = load_yaml(mission_path)
        setup = mission.get("setup")
        if isinstance(setup, dict) and isinstance(setup.get("script"), str):
            scripts.append(mission_path.parent / setup["script"])
        reset_folder = mission_path.parent / f"task_reset_{mission_name_from_path(mission_path)}"
        scripts.extend(sorted(reset_folder.glob("reset_t*.m")))

    for script in scripts:
        text = strip_matlab_comments(script.read_text(encoding="utf-8"))
        for pattern, label in FORBIDDEN_MATLAB_PATTERNS:
            require(not pattern.search(text), f"{rel(script)} contains forbidden operation: {label}")


def check_docs_and_skills() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in ["MATLAB toolbox", "InteractiveMissions.mltbx", "buildtool package", "safe workspace",
                   "Start Mission", "Resume", "Documents/MATLAB/Interactive-Missions",
                   "<mission-name>", "$mission-tutoring",
                   "marketplace", ".interactive-missions/progress.json", "GitHub Copilot CLI"]:
        require(phrase in readme, f"README must mention {phrase!r}")
    for phrase in ["Import Mission Pack", "mission pack ZIP", "user mission library"]:
        require(phrase not in readme, f"README must not mention old sharing surface {phrase!r}")

    contract = (SHARED_AUTHOR_REFERENCES / "mission-contract.md").read_text(encoding="utf-8")
    require("marketplace/missions" in contract, "shared mission contract must mention marketplace/missions")
    require(".interactive-missions/progress.json" in contract,
            "shared mission contract must describe workspace-local progress")
    progress_contract = SHARED_AUTHOR_REFERENCES / "progress-contract.md"
    require(progress_contract.is_file(), "shared progress contract is missing")
    for phrase in ["learnerName", "hintCounts", "updatedAt", "notes"]:
        require(phrase in progress_contract.read_text(encoding="utf-8"),
                f"progress contract must mention {phrase!r}")
    require((SHARED_AUTHOR_REFERENCES / "platform-qualification.md").is_file(),
            "shared platform qualification document is missing")
    for contract_name in ["mission-contract.md", "progress-contract.md", "platform-qualification.md"]:
        require(not (ROOT / "docs" / contract_name).exists(),
                f"former app Help contract must not exist: docs/{contract_name}")
    require((ROOT / "docs" / "agent-support-matrix.json").is_file(),
            "platform qualification matrix is missing")
    require((ROOT / "docs" / "1-index.md").is_file(),
            "docs/1-index.md is missing")
    require((ROOT / "src" / "docs" / "learner-faq.md").is_file(),
            "src/docs/learner-faq.md is missing")
    agent_matrix = json.loads((ROOT / "docs" / "agent-support-matrix.json").read_text(encoding="utf-8"))
    agents = agent_matrix.get("agents")
    require(isinstance(agents, list), "agent support matrix must list agents")
    author_adapter_ids = set()
    for agent in agents:
        require(isinstance(agent, dict) and agent.get("supported") is True,
                "agent support matrix must list supported agent mappings")
        author_adapter_path = agent.get("author_adapter_path")
        require(isinstance(author_adapter_path, str) and author_adapter_path,
                f"agent support matrix is missing author_adapter_path for {agent.get('id')!r}")
        adapter_path = ROOT / author_adapter_path
        require(adapter_path.is_file(), f"author adapter is missing: {author_adapter_path}")
        adapter = load_yaml(adapter_path)
        require(adapter.get("id") == agent.get("id"),
                f"author adapter ID must match the support matrix: {author_adapter_path}")
        files = adapter.get("files")
        require(isinstance(files, list) and files,
                f"author adapter must list copied files: {author_adapter_path}")
        for file_mapping in files:
            require(isinstance(file_mapping, dict), f"author adapter file mapping must be a mapping: {author_adapter_path}")
            source = file_mapping.get("source")
            target = file_mapping.get("target")
            require(isinstance(source, str) and source and (adapter_path.parent / source).is_file(),
                    f"author adapter source is missing: {author_adapter_path}")
            require(isinstance(target, str) and target and ".." not in target,
                    f"author adapter target is unsafe: {author_adapter_path}")
        author_adapter_ids.add(adapter.get("id"))
    require(author_adapter_ids == SUPPORTED_ADAPTER_IDS,
            f"author adapter IDs must be {sorted(SUPPORTED_ADAPTER_IDS)}")

    tutor_text = LEARNER_SKILL.read_text(encoding="utf-8")
    for phrase in ["safe workspace", "content/mission.yaml", ".interactive-missions/progress.json",
                   "allow_agent_edits", "allowAgentEdits"]:
        require(phrase in tutor_text, f"tutor skill must mention {phrase!r}")
    require("plugin root" not in tutor_text.lower(), "tutor skill must not reference plugin root paths")
    organizer = LEARNER_SKILL.parent / "references" / "advance-organizer.md"
    status_reporting = LEARNER_SKILL.parent / "references" / "status-reporting.md"
    startup = LEARNER_SKILL.parent / "references" / "session-startup.md"
    task_loop = LEARNER_SKILL.parent / "references" / "task-loop.md"
    require(organizer.is_file(), "tutor skill must include a dedicated advance organizer reference")
    require(status_reporting.is_file(), "tutor skill must include a status-reporting reference")
    organizer_text = organizer.read_text(encoding="utf-8")
    status_text = status_reporting.read_text(encoding="utf-8")
    startup_text = startup.read_text(encoding="utf-8")
    task_loop_text = task_loop.read_text(encoding="utf-8")
    for phrase in [
        "3-5 concise sentences",
        "only the mission `title` and `objective`",
        "explicit prerequisite or assumed-prior-knowledge statements",
        "include that prerequisite information in the opening summary",
        "outside facts, hints, completion checks, commands, parameter values, mechanical steps, or solutions",
        "exactly one short, narrowly scoped prediction question",
        "without evaluating, grading, correcting, or revealing the answer",
    ]:
        require(phrase in organizer_text, f"advance organizer must specify {phrase!r}")
    for phrase in [
        "provide a display name or use a generated alliterative MATLAB/Simulink-animal name",
        "tracked missions need a display name",
        "do not present the organizer or Task 1",
        "Task 1 and no mission tasks are complete",
        "Wait for the learner's prediction response",
        "resuming at Task 2 or later, skip the organizer",
    ]:
        require(phrase in startup_text, f"session startup must specify {phrase!r}")
    require("or no name" not in startup_text,
            "tracked startup must not offer a no-name option")
    require("prediction response is not a task attempt" in task_loop_text,
            "task loop must exclude the organizer prediction from task attempts")
    require("mcpTmp_" in tutor_text,
            "tutor skill must require the mcpTmp_ temporary-variable prefix")
    require("Prefer direct expressions and `fprintf` for MATLAB MCP inspection" in tutor_text,
            "tutor skill must prefer inspections without temporary variables")
    require('mcpTmpNames = who("mcpTmp_*");' in task_loop_text,
            "task loop must identify mcpTmp_ temporary variables for cleanup")
    require("clear(mcpTmpNames{:})" in task_loop_text,
            "task loop must clean up only identified mcpTmp_ temporary variables")
    require("evalin(" not in task_loop_text,
            "task loop must not clear a different MATLAB workspace")
    for phrase in [
        "Let the learner perform the work.",
        "primary source of learner-facing task help",
        "complete recipe",
    ]:
        require(phrase in tutor_text, f"tutor skill must specify {phrase!r}")
    for phrase in [
        "identify the smallest unmet part",
        "Use the active task's ordered `hints` list as the authored hint ladder.",
        "directional, specific, then direct",
        "Skip a hint when the learner's current work already addresses its target.",
        "Present exactly one selected YAML hint.",
        "task-effort baseline in session memory",
        "Count task-relevant effort only when product inspection shows a relevant change or partial result",
        "Verbal claims, unrelated changes, repeated requests, and anger do not count as effort.",
        "If the state could instead be setup output, prior completed-task state, or another ambiguous source",
        "exactly one eligible authored hint and encourage the learner to try it",
        "If no eligible hint remains before effort",
        "Anger never bypasses the effort requirement.",
        "Rescue is permitted only after task-relevant effort is observed.",
        "the learner attempted prior guidance and still needs direct help",
        "the remaining eligible authored hints do not address the observed blocker",
        "the applicable authored hints are exhausted",
        "If required product inspection fails or cannot establish effort",
        "Tell me what to do",
        "Repeated requests without a task-relevant change",
        "Exhausted hints without effort",
        "Anger without effort",
        "Observed partial work followed by a direct request",
        "Resumed partial work counts as effort",
        "Re-inspect before every rejection",
        "after the learner disputes an assessment",
        "After the learner reports applying the recipe, re-inspect before assessing completion.",
    ]:
        require(phrase in task_loop_text, f"task loop must specify {phrase!r}")
    for phrase in [
        "one or two short, programmatic lines",
        "without first-person narration, future plans, or explanations of internal reasoning",
        "Send a status report as its own message",
        "Reading mission...",
        "Current state: Mission not started.",
        "MATLAB MCP Server and required tools are available.",
    ]:
        require(phrase in status_text, f"status reporting must specify {phrase!r}")
    require("status-reporting.md" in tutor_text,
            "tutor skill must load the status-reporting reference")
    for lifecycle_text, lifecycle_name in [
        (startup_text, "startup"),
        ((LEARNER_SKILL.parent / "references" / "mission-resources.md").read_text(encoding="utf-8"), "setup/reset"),
        (task_loop_text, "task verification"),
        ((LEARNER_SKILL.parent / "references" / "progress-and-ending.md").read_text(encoding="utf-8"), "progress/ending"),
    ]:
        require("status-reporting.md" in lifecycle_text,
                f"{lifecycle_name} guidance must load the status-reporting contract")

    for path in mission_paths():
        mission = load_yaml(path)
        require(isinstance(mission.get("objective"), str) and mission["objective"].strip(),
                f"{rel(path)} objective must provide organizer background")
        tasks = mission.get("tasks")
        require(isinstance(tasks, list) and isinstance(tasks[0].get("instruction"), str) and tasks[0]["instruction"].strip(),
                f"{rel(path)} Task 1 instruction must support organizer context")

    contract = (SHARED_AUTHOR_REFERENCES / "mission-contract.md").read_text(encoding="utf-8")
    authoring_instructions = (PACKAGED_AUTHOR_SKILLS / "create-tutor-mission" / "SKILL.md").read_text(encoding="utf-8")
    yaml_guidance = (PACKAGED_AUTHOR_SKILLS / "create-tutor-mission" / "references" / "mission-yaml.md").read_text(encoding="utf-8")
    qa_guidance = (PACKAGED_AUTHOR_SKILLS / "qa-mission" / "references" / "static-analysis.md").read_text(encoding="utf-8")
    overview = (ROOT / "docs" / "4-mission-yaml-overview.md").read_text(encoding="utf-8")
    for text, label in [(contract, "mission contract"), (authoring_instructions, "mission-authoring instructions"), (yaml_guidance, "mission YAML guidance"), (qa_guidance, "QA guidance"), (overview, "mission YAML overview")]:
        require("prediction" in text.lower(), f"{label} must describe organizer-ready objectives")
        require("prerequisite" in text.lower() or "prior knowledge" in text.lower(),
                f"{label} must explain how organizer-ready objectives express prerequisites")

    app_html = (ROOT / "src" / "app" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "src" / "app" / "app.js").read_text(encoding="utf-8")
    app_css = (ROOT / "src" / "app" / "styles.css").read_text(encoding="utf-8")
    app_class_path = ROOT / "src" / "+interactiveMissions" / "+internal" / "MissionBrowserApp.m"
    app_class = app_class_path.read_text(encoding="utf-8")
    require('data-view="progress"' not in app_html, "app must not expose a standalone Progress tab")
    require("function missionThumbnail" in app_js and
            'const thumbnailSource = scalarText(mission.Thumbnail).trim();' in app_js and
            'fallbackThumbnailIcon(' in app_js and
            'template.content.cloneNode(true)' in app_js and
            'fallback-thumbnail-graduationcap' in app_html and
            'fallback-thumbnail-matlab' in app_html and
            'fallback-thumbnail-simulink' in app_html and
            '"GraduationCap"' in app_js and
            '"Matlab"' in app_js and
            '"Simulink"' in app_js and
            "aspect-ratio: 16 / 9" in app_css and
            "linear-gradient" in app_css and
            "rgba(0, 118, 168, 0.12)" in app_css and
            "rgba(0, 75, 135, 0.1)" in app_css and
            "rgba(215, 136, 37, 0.12)" in app_css,
            "app must render the three-logo generic thumbnail treatment")
    require('mimeType = "image/png"' in app_class and
            'mimeType = "image/svg+xml"' in app_class,
            "app thumbnail data URIs must select PNG or SVG MIME types")
    require("FallbackThumbnails = app.fallbackThumbnailsForUi();" not in app_class and
            "FallbackThumbnails" not in app_js,
            "app must render fallback thumbnails from app-owned inline SVG templates")
    for phrase in ["Practice", "Start Mission", "Resume", "Authoring Help", "Learner FAQ",
                   "Agentic client", "Codex", "GitHub Copilot in VS Code", "GitHub Copilot CLI"]:
        require(phrase in app_html or phrase in app_js, f"app UI must include {phrase!r}")
    missions_tab = app_html.index('data-view="missions"')
    faq_tab = app_html.index('data-view="learner-faq"')
    help_tab = app_html.index('data-view="documentation"')
    require(missions_tab < faq_tab < help_tab,
            "Learner FAQ tab must appear between Missions and Authoring Help")
    for phrase in ["Import Mission Pack", "Destination user mission library", "Export", "createDraftMetadata"]:
        require(phrase not in app_html + app_js, f"app UI must not expose old authoring/import surface {phrase!r}")
    require('id="documentationView"' in app_html and "renderMarkdown" in app_js,
            "app must include rendered documentation navigation")
    require('id="learnerFaqView"' in app_html and
            'id="learnerFaqContent"' in app_html and
            'id="learnerFaqHeadingList"' in app_html,
            "app must include a dedicated learner FAQ view and containers")
    require('replace(/-([a-z])/g' in app_js and
            'view.id === viewName + "View" || view.id === normalizedViewName + "View"' in app_js,
            "app tab switching must support hyphenated view names such as Learner FAQ")
    require('fullfile(interactiveMissions.internal.toolboxRoot(), "docs")' in app_class and
            'fullfile(interactiveMissions.internal.toolboxRoot(), "src", "doc")' not in app_class,
            "app documentation must load pages from docs only")
    require('state.LearnerFaq = app.learnerFaqForUi();' in app_class and
            'fullfile(interactiveMissions.internal.toolboxRoot(), "src", "docs", "learner-faq.md")' in app_class,
            "app must load learner FAQ from src/docs/learner-faq.md")
    require("function decodeHtmlEntities" in app_js and
            "let markdown = decodeHtmlEntities(text)" in app_js and
            "let html = escapeHtml(markdown)" in app_js and
            "function saveToken(html)" in app_js,
            "app documentation renderer must decode entities before escaping text")
    require("decodeHtmlEntities(firstLine(page.Title || page.FileName))" in app_js and
            "return decodeHtmlEntities(plainText)" in app_js,
            "app documentation navigation and headings must decode entities")
    require(r"if (/^>\s?/.test(trimmed))" in app_js and
            'element("blockquote", "")' in app_js and
            "inlineMarkdown(quoteLines.join" in app_js,
            "app documentation renderer must render Markdown blockquotes")
    require(".docs-content blockquote" in app_css and
            "padding: 0 0 0 1.5em" in app_css and
            "border-left: 2px solid #0076a8" in app_css and
            "color: #000000" in app_css,
            "app documentation blockquotes must use the app visual style")
    require("function markdownTableDefinition" in app_js and
            "function markdownTableRow" in app_js and
            r"/^:?-{3,}:?$/" in app_js and
            'element("table", "docs-table")' in app_js and
            'headerCell.scope = "col"' in app_js and
            'element("thead", "")' in app_js and
            'element("tbody", "")' in app_js,
            "app documentation renderer must render valid pipe tables semantically")
    require('element("div", "docs-table-wrap")' in app_js and
            "headerCell.innerHTML = inlineMarkdown(header, contextFileName)" in app_js and
            "bodyCell.innerHTML = inlineMarkdown(cellText, contextFileName)" in app_js and
            r'markdown = markdown.replace(/`([^`]+)`/' in app_js and
            r'markdown = markdown.replace(/\[([^\]]+)\]\(([^)]+)\)/' in app_js,
            "app documentation tables must support inline Markdown without formatting code spans or link destinations")
    require(".docs-table-wrap" in app_css and
            "overflow-x: auto" in app_css and
            ".docs-table th," in app_css and
            "background: #f2f2f2" in app_css,
            "app documentation tables must be responsive and match the Help visual style")
    require("function documentationNavigation" in app_js and
            r"fileName.match(/^(\d+)-/)" in app_js,
            "app documentation navigation must classify numbered walkthrough pages by filename")
    require("Number.parseInt(walkthroughMatch[1], 10)" in app_js and
            "left.Order - right.Order" in app_js,
            "app documentation navigation must sort walkthrough pages numerically")
    require("referencePages.sort(function compareReference" in app_js,
            "app documentation navigation must sort reference pages by filename")
    walkthrough_button = "renderDocumentationPageButtons(pageList, navigation.Walkthrough)"
    reference_button = "renderDocumentationPageButtons(pageList, navigation.Reference)"
    require('fileName.toLowerCase() === "author-faq.md"' not in app_js and
            app_js.index(walkthrough_button) < app_js.index(reference_button),
            "app documentation navigation must classify Author FAQ with Reference pages")
    require('appendDocumentationSectionLabel(pageList, "Walkthrough")' in app_js and
            'appendDocumentationSectionLabel(pageList, "Reference")' in app_js and
            "docs-section-label" in app_css,
            "app documentation navigation must render Walkthrough and Reference section labels")
    require('getElementById("documentationContent").addEventListener("click", handleMarkdownContentClick)' in app_js and
            'event.target.closest("a")' in app_js,
            "app documentation links must use delegated Help-content click handling")
    require('function renderLearnerFaq' in app_js and
            'renderMarkdown(state.LearnerFaq.Markdown || "", learnerFaqFileName())' in app_js and
            'renderLearnerFaqHeadings(renderResult.Headings)' in app_js and
            'getElementById("learnerFaqContent").addEventListener("click", handleMarkdownContentClick)' in app_js,
            "learner FAQ must use the shared Markdown renderer, heading navigation, and link handling")
    require("function documentationFileName" in app_js and
            "Documentation page not found:" in app_js,
            "app documentation links must normalize page names and report missing pages")
    require('send("openDocumentationUrl", { Url:' in app_js and
            "IsWeb: true" in app_js and "return safeLabel;" in app_js,
            "app documentation links must route HTTP(S) URLs through MATLAB and render relative non-Markdown files as text")
    require('case "openDocumentationUrl"' in app_class and
            'startsWith(url, ["http://", "https://"], IgnoreCase=true)' in app_class and
            'web(url, "-browser");' in app_class,
            "app must validate HTTP(S) documentation URLs before opening the system browser")
    require("environment" not in (app_html + app_js + app_css + app_class).lower(),
            "app implementation must not reference the removed Environment settings panel")
    require('<span id="promptStep3Text"' in app_html and '<span id="promptStep4Text"' in app_html,
            "launch steps 3 and 4 must render as text")
    require("isCdCommand" in app_js,
            "launch command code box must be limited to cd commands")
    require("Full launch context" not in app_html,
            "launch modal must not expose full launch context")
    require('launchAgentClientSelect").value = ""' in app_js,
            "launch modal must require an intentional agent client selection")
    require("Choose an agentic client." in app_js,
            "launch modal must explain when the agent client is missing")
    require(all(phrase not in app_class + app_js for phrase in
                ["UserProfile", "IsCurrentUser", "state.Identity", "identityUsername"]),
            "app must not retain profile identity state")
    require("Awaiting learner name" in app_class or "Awaiting learner name" in app_js,
            "app must label unnamed unstarted sessions neutrally")
    require("Add a Marketplace" in app_js and 'showView("settings")' in app_js,
            "app empty state must navigate learners to marketplace registration")
    default_marketplace = (ROOT / "src" / "+interactiveMissions" / "+internal" / "defaultMarketplace.m").read_text(encoding="utf-8")
    default_registration = (ROOT / "src" / "+interactiveMissions" / "+internal" / "ensureDefaultMarketplace.m").read_text(encoding="utf-8")
    unregister_marketplace = (ROOT / "src" / "+interactiveMissions" / "unregisterMarketplace.m").read_text(encoding="utf-8")
    marketplace_update_check = (ROOT / "src" / "+interactiveMissions" / "checkMarketplaceUpdates.m").read_text(encoding="utf-8")
    default_marketplace_settings = (ROOT / "src" / "app" / "setting.json").read_text(encoding="utf-8")
    internal_gitlab_url = "insidelabs-git.mathworks.com"
    require(internal_gitlab_url not in readme.lower() + default_marketplace_settings.lower(),
            "public release files must not contain internal GitLab URLs")
    require('id="registerMarketplaceModal"' in app_html and
            'id="marketplaceVisibilitySelect"' not in app_html and "Git Credential Manager" in app_html,
            "app must use a credential-aware marketplace registration modal")
    require("setting.json" in default_marketplace and
            '"referenceName": "main"' in default_marketplace_settings and
            "IsDefault=true" in default_registration and
            "DefaultMarketplaceProtected" in unregister_marketplace,
            "app must register and protect the default marketplace")
    app_class = (ROOT / "src" / "+interactiveMissions" / "+internal" / "MissionBrowserApp.m").read_text(encoding="utf-8")
    startup_update_check = app_class.split("function checkForUpdatesAfterStartup", 1)[1].split("function clearMissionCache", 1)[0]
    require("checkMarketplaceUpdates" in marketplace_update_check and
            "ls-remote" in marketplace_update_check and
            "clone" not in marketplace_update_check and
            "parfeval" in app_class and
            "marketplaceUpdatesAvailable" in app_js and
            "refreshRemoteMarketplaces();" not in startup_update_check,
            "startup must check remote revisions without refreshing marketplace content")

    packaged_skill_names = {path.parent.name for path in (ROOT / "src" / "skills").glob("*/SKILL.md")}
    require(packaged_skill_names == {"mission-tutoring"},
            f"src/skills must ship only learner skill: {sorted(packaged_skill_names)}")

    for skill_name in AUTHOR_ONLY_SKILLS:
        source_root = PACKAGED_AUTHOR_SKILLS / skill_name
        text = (source_root / "SKILL.md").read_text(encoding="utf-8")
        require("plugins/interactive-missions" not in text,
                f"{skill_name} must not reference old plugin content paths")
        require(source_root.is_dir(), f"missing author skill: {skill_name}")

    for skill_name in AUTHOR_ONLY_SKILLS:
        skill_path = PACKAGED_AUTHOR_SKILLS / skill_name / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")
        require("../references/" in skill_text,
                f"{skill_name} must reference shared author contracts")


def check_progress_safety() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    require(not re.search(r"(?m)^progress/$", gitignore), ".gitignore must not ignore progress/")
    require(not re.search(r"(?m)^build/$", gitignore), ".gitignore must not ignore build/")
    tracked_progress = git_ls_files("progress")
    require(not tracked_progress, "progress files must not be tracked: " + ", ".join(tracked_progress))


def main() -> int:
    checks = [
        ("layout", check_layout),
        ("mission schema", check_missions),
        ("setup/reset safety", check_matlab_scripts),
        ("docs and skills", check_docs_and_skills),
        ("progress safety", check_progress_safety),
    ]
    failures: list[str] = []

    for name, check in checks:
        try:
            check()
            print(f"PASS: {name}")
        except SmokeFailure as exc:
            failures.append(f"FAIL: {name}: {exc}")
        except subprocess.CalledProcessError as exc:
            failures.append(f"FAIL: {name}: command failed: {' '.join(exc.cmd)}\n{exc.stderr}")

    if failures:
        print()
        print("\n".join(failures))
        return 1

    print("\nAll static smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
