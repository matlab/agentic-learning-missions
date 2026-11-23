"""Infrastructure tests without model calls or a MATLAB installation."""

import asyncio
import json
import os
import stat
import subprocess
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import psutil
from mcp.types import CallToolResult, TextContent

SCRIPTS = Path(__file__).resolve().parents[1] / "src/author-skills/references/evaluation/scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from mission_evals.events import EventLog, read_events, write_json
from mission_evals.codex_runtime import prove_codex
from mission_evals.matlab_runtime import MatlabBroker
from mission_evals.processes import OwnedProcessTree
from mission_evals.workspace import prepare_codex_home, remove_trial_workspace, toml_value, trial_workspace


class EvidenceTests(unittest.TestCase):
    def test_report_rebuild_survives_an_old_partial_staging_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            write_json(path, {"completed": 1})
            stale = path.with_name("benchmark.json.tmp")
            stale.write_text('{"completed":')
            write_json(path, {"completed": 2})
            self.assertEqual(json.loads(path.read_text()), {"completed": 2})
            self.assertTrue(stale.exists())

    def test_interrupted_run_leaves_readable_ordered_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with self.assertRaises(RuntimeError):
                with EventLog(path, run_id="run", suite="infrastructure", case_id="case") as log:
                    identifier = log.emit("tool.call", "learner", {"text": "two\nlines α"})
                    self.assertEqual(read_events(path)[0]["event_id"], identifier)
                    raise RuntimeError("simulated interruption")
            self.assertEqual(len(read_events(path)), 1)
            with self.assertRaises(FileExistsError):
                EventLog(path, run_id="other", suite="infrastructure", case_id="case")

    def test_non_json_payload_does_not_consume_sequence_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with EventLog(path, run_id="run", suite="infrastructure", case_id="case") as log:
                with self.assertRaises(ValueError):
                    log.emit("invalid", "harness", {"value": float("nan")})
                log.emit("valid", "harness", {})
            self.assertEqual(read_events(path)[0]["sequence"], 1)

    def test_damaged_evidence_is_not_silently_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text('{"schema_version":"1.0","sequence":2,"event_id":"a"}\n')
            with self.assertRaises(ValueError):
                read_events(path)
            path.write_text('{"schema_version":')
            with self.assertRaises(json.JSONDecodeError):
                read_events(path)


class WorkspaceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows extended path regression")
    def test_long_plugin_cache_paths_are_removed(self):
        with trial_workspace() as root:
            deep = root / ("a" * 80) / ("b" * 80) / ("c" * 80)
            native = Path("\\\\?\\" + str(deep))
            native.mkdir(parents=True)
            (native / "cache.txt").write_text("owned cache")
        self.assertFalse(root.exists())

    def test_readonly_cache_cleanup_preserves_original_failure(self):
        with self.assertRaisesRegex(RuntimeError, "original failure"):
            with trial_workspace() as root:
                path = root / "git-pack.idx"
                path.write_text("cache")
                path.chmod(stat.S_IREAD)
                raise RuntimeError("original failure")
        self.assertFalse(root.exists())

    def test_cleanup_rejects_wrong_parent(self):
        with trial_workspace() as root:
            with self.assertRaises(RuntimeError):
                remove_trial_workspace(root, root)
            self.assertTrue(root.exists())

    def test_workspace_cleanup_on_failure(self):
        with self.assertRaises(RuntimeError):
            with trial_workspace() as root:
                (root / "learner.txt").write_text("work")
                raise RuntimeError("trial failed")
        self.assertFalse(root.exists())

    def test_provider_roundtrip_and_no_host_instructions(self):
        provider = {"base_url": "https://example.invalid/v1", "env_key": "TEST_KEY",
                    "http_headers": {"quoted-key": "text with \\\" and \n"}}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original"
            source.mkdir()
            config = (f'model = "configured-model"\nmodel_provider = "test"\n'
                      f'model_providers = {toml_value({"test": provider})}\n'
                      '[mcp_servers.unrelated]\ncommand = "unrelated"\n')
            (source / "config.toml").write_text(config, encoding="utf-8")
            (source / "AGENTS.md").write_text("private instructions")
            (source / "auth.json").write_text('{"fake":true}')
            with patch.dict(os.environ, {"CODEX_HOME": str(source)}):
                with trial_workspace() as root:
                    destination = prepare_codex_home(root)
                    generated = tomllib.loads((destination / "config.toml").read_text(encoding="utf-8"))
                    self.assertEqual(generated["model_providers"]["test"], provider)
                    self.assertNotIn("mcp_servers", generated)
                    self.assertFalse((destination / "AGENTS.md").exists())
                    self.assertTrue((destination / "auth.json").exists())
                    self.assertEqual(os.environ["CODEX_HOME"], str(source))
                self.assertFalse(destination.exists())
            self.assertEqual((source / "config.toml").read_text(encoding="utf-8"), config)


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_roles_are_serialized_and_correlated(self):
        class Session:
            active = 0
            maximum = 0

            async def call_tool(self, name, arguments, **kwargs):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0)
                self.active -= 1
                return CallToolResult(content=[TextContent(type="text", text="ok")], is_error=False)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            session = Session()
            with EventLog(path, run_id="run", suite="infrastructure", case_id="case") as log:
                broker = MatlabBroker(session, log)
                await asyncio.gather(broker.call("learner", "tool", {}),
                                     broker.call("tutor", "tool", {}))
            events = read_events(path)
            self.assertEqual(session.maximum, 1)
            self.assertEqual([e["event_type"] for e in events],
                             ["tool.call", "tool.result", "tool.call", "tool.result"])
            self.assertEqual(events[0]["action_id"], events[1]["action_id"])
            self.assertEqual(events[2]["action_id"], events[3]["action_id"])
            self.assertNotEqual(events[0]["action_id"], events[2]["action_id"])

    async def test_transport_failure_retains_call_and_error(self):
        class Session:
            async def call_tool(self, *args, **kwargs):
                raise TimeoutError("connection stalled")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with EventLog(path, run_id="run", suite="infrastructure", case_id="case") as log:
                with self.assertRaises(TimeoutError):
                    await MatlabBroker(Session(), log).call("tutor", "tool", {})
            events = read_events(path)
            self.assertEqual([e["event_type"] for e in events], ["tool.call", "tool.error"])
            self.assertEqual(events[1]["payload"]["error_type"], "TimeoutError")

    async def test_product_error_is_preserved_and_fails_the_call(self):
        class Session:
            async def call_tool(self, *args, **kwargs):
                return CallToolResult(content=[TextContent(type="text", text="product error")],
                                      is_error=True)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            with EventLog(path, run_id="run", suite="infrastructure", case_id="case") as log:
                with self.assertRaisesRegex(RuntimeError, "product error"):
                    await MatlabBroker(Session(), log).call("learner", "tool", {})
            self.assertTrue(read_events(path)[1]["payload"]["isError"])


class CodexLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_initialization_still_closes_client(self):
        class Client:
            closed = False

            async def __aenter__(self):
                raise RuntimeError("initialization failed")

            async def __aexit__(self, *exc):
                raise AssertionError("__aexit__ is not called when __aenter__ fails")

            async def close(self):
                self.closed = True

        client = Client()
        with trial_workspace() as root:
            with EventLog(root / "events.jsonl", run_id="run", suite="infrastructure", case_id="case") as log:
                with patch("mission_evals.codex_runtime.AsyncCodex", return_value=client):
                    with patch("mission_evals.codex_runtime.prepare_codex_home", return_value=root / "runtime"):
                        with self.assertRaisesRegex(RuntimeError, "initialization failed"):
                            await prove_codex(root, log)
        self.assertTrue(client.closed)


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_stops_owned_process_and_preserves_sibling(self):
        args = [sys.executable, "-c", "import time; time.sleep(30)"]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        owned = subprocess.Popen(args, creationflags=flags)
        sibling = subprocess.Popen(args, creationflags=flags)
        try:
            tree = OwnedProcessTree(psutil.Process(owned.pid))
            result = await tree.finish()
            self.assertTrue(result["all_exited"])
            self.assertIn(owned.pid, result["forced_pids"])
            self.assertIsNone(sibling.poll())
        finally:
            for process in (owned, sibling):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

    async def test_refuses_the_runner_as_an_owned_child(self):
        with self.assertRaisesRegex(RuntimeError, "outside this runner"):
            OwnedProcessTree(psutil.Process())


if __name__ == "__main__":
    unittest.main()
