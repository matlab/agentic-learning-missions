"""Disposable trial directories and child-only Codex configuration."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def trial_workspace():
    """Use an OS temporary folder, outside repository instruction discovery."""
    parent = Path(tempfile.gettempdir()).resolve()
    root = Path(tempfile.mkdtemp(prefix="im-eval-", dir=parent))
    try:
        yield root
    except BaseException as primary:
        try:
            remove_trial_workspace(root, parent)
        except Exception as cleanup:
            raise BaseExceptionGroup("Trial and cleanup both failed", [primary, cleanup]) from None
        raise
    else:
        remove_trial_workspace(root, parent)


def remove_trial_workspace(root: Path, parent: Path) -> None:
    # Verify the actual target before recursive removal, including on Windows.
    if root.is_symlink() or root.resolve().parent != parent.resolve():
        raise RuntimeError(f"Refusing cleanup outside the trial parent: {root}")
    if not root.name.startswith(("im-eval-", "interactive-missions-eval-")):
        raise RuntimeError(f"Refusing cleanup of a non-trial directory: {root}")
    resolved_root = root.resolve()
    # Codex's plugin cache can contain paths longer than MAX_PATH. Use Windows'
    # extended path form only after validating the ordinary absolute target.
    native_root = resolved_root
    if os.name == "nt":
        absolute = str(resolved_root)
        native_root = Path("\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\")
                           else "\\\\?\\" + absolute)

    def retry_readonly(operation, path, error):
        target = Path(path)
        if not isinstance(error, PermissionError) or not target.resolve().is_relative_to(native_root):
            raise error
        # Git pack files can be read-only on Windows. Only change permissions
        # inside the verified, disposable trial directory.
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
        operation(path)

    shutil.rmtree(native_root, onexc=retry_readonly)


def toml_value(value):
    """Encode the scalar/list/table values used by provider configuration."""
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(k)} = {toml_value(v)}"
                                for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, (str, bool, int, float)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    raise TypeError(f"Unsupported configuration value: {type(value).__name__}")


def prepare_codex_home(root: Path, *, model: str | None = None,
                       mcp_servers: dict | None = None) -> Path:
    """Reuse authentication/provider settings, not host skills or conversation state.

    This directory can contain credentials. It must stay inside the disposable
    trial, must not be archived in reports, and must be removed during cleanup.
    The parent process's environment and user configuration are never changed.
    """
    source = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    source_config = source / "config.toml"
    settings = (tomllib.loads(source_config.read_text(encoding="utf-8"))
                if source_config.is_file() else {})
    selected = {key: settings[key] for key in
                ("model", "model_provider", "model_providers", "model_reasoning_effort",
                 "service_tier", "approval_policy", "approvals_reviewer", "auto_review")
                if key in settings}
    if model:
        selected["model"] = model
    # These smoke agents have no tool work. Later suite adapters configure their
    # own tool exposure; do not inherit the author's MCP servers or plugins.
    selected["features"] = dict(shell_tool=False, unified_exec=False, apps=False,
                                multi_agent=False, skill_search=False)
    selected["web_search"] = "disabled"
    if mcp_servers is not None:
        selected["mcp_servers"] = mcp_servers
    destination = root / "codex-home"
    destination.mkdir(mode=0o700)
    if settings.get("model_catalog_json"):
        catalog = Path(settings["model_catalog_json"]).expanduser()
        if not catalog.is_absolute():
            catalog = source / catalog
        shutil.copyfile(catalog, destination / "model-catalog.json")
        selected["model_catalog_json"] = str(destination / "model-catalog.json")
    auth_file = source / "auth.json"
    if auth_file.is_file():
        shutil.copyfile(auth_file, destination / "auth.json")
        selected["cli_auth_credentials_store"] = "file"
    config_text = "\n".join(f"{key} = {toml_value(value)}"
                            for key, value in selected.items()) + "\n"
    (destination / "config.toml").write_text(config_text, encoding="utf-8")
    return destination
