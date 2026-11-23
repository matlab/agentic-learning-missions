"""Portable review generation and loopback-serving behavior."""

import copy
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from threading import Thread
import unittest
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import urlopen


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src/author-skills/simulate-mission-learner"
spec = importlib.util.spec_from_file_location("skill_review_dashboard", SKILL / "scripts/review_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class SkillReviewDashboardTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "build/test-skill-review"
        temporary_root.mkdir(parents=True, exist_ok=True)
        # Python 3.13's Windows tempfile ACLs can exclude the sandbox identity.
        self.folder = temporary_root / str(uuid4())
        self.folder.mkdir()
        self.addCleanup(shutil.rmtree, self.folder)
        page = (SKILL / "assets/review.html").read_text(encoding="utf-8")
        self.packet = json.loads(dashboard.script_data(page, "review-data").group(2))

    def test_copied_skill_generates_without_design_folder(self):
        copied = self.folder / "copied-skill"
        shutil.copytree(SKILL, copied)
        copied_spec = importlib.util.spec_from_file_location("copied_dashboard", copied / "scripts/review_dashboard.py")
        module = importlib.util.module_from_spec(copied_spec)
        copied_spec.loader.exec_module(module)
        output = self.folder / "review"
        fingerprint = module.build_bundle(None, output)
        self.assertEqual(fingerprint, hashlib.sha256((output / "packet.json").read_bytes()).hexdigest())
        feedback = json.loads((output / "feedback-template.json").read_text(encoding="utf-8"))
        self.assertEqual(feedback["packet_sha256"], fingerprint)
        self.assertTrue(all(row["decision"] == "pending" for row in feedback["reviews"]))
        self.assertEqual({path.name for path in output.iterdir()},
                         {"index.html", "packet.json", "feedback-template.json", "REVIEW.md"})

    def test_unicode_and_script_text_are_preserved_as_inert_data(self):
        self.packet["items"] = self.packet["items"][:1]
        evidence = 'Δ sample — café </script><script>window.injected=true</script> & <tag>'
        self.packet["items"][0]["evidence"] = evidence
        packet_path = self.folder / "input.json"
        raw = json.dumps(self.packet, ensure_ascii=False).encode("utf-8")
        packet_path.write_bytes(raw)
        output = self.folder / "review"
        dashboard.build_bundle(packet_path, output)
        page = (output / "index.html").read_text(encoding="utf-8")
        embedded = dashboard.script_data(page, "review-data").group(2)
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded)["items"][0]["evidence"], evidence)
        self.assertEqual((output / "packet.json").read_bytes(), raw)
        self.assertIsInstance(json.loads(embedded)["items"], list)

    def test_invalid_packets_are_rejected_before_creating_output(self):
        invalid_packets = []
        duplicate = copy.deepcopy(self.packet)
        duplicate["items"][1]["id"] = duplicate["items"][0]["id"]
        invalid_packets.append(duplicate)
        choices = copy.deepcopy(self.packet)
        choices["items"][0]["choices"] = ["accept", "accept"]
        invalid_packets.append(choices)
        for index, packet in enumerate(invalid_packets):
            with self.subTest(index=index):
                source = self.folder / "input.json"
                source.write_text(json.dumps(packet), encoding="utf-8")
                output = self.folder / f"review-{index}"
                with self.assertRaises(ValueError):
                    dashboard.build_bundle(source, output)
                self.assertFalse(output.exists())

    def test_existing_review_is_not_overwritten(self):
        output = self.folder / "review"
        dashboard.build_bundle(None, output)
        with self.assertRaises(FileExistsError):
            dashboard.build_bundle(None, output)

    def test_loopback_server_confines_requests_and_stops(self):
        output = self.folder / "review"
        dashboard.build_bundle(None, output)
        (self.folder / "private.txt").write_text("private", encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(dashboard.ReviewRequestHandler, directory=str(output)))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            with urlopen(url + "/", timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"Review asset", response.read())
            with self.assertRaises(HTTPError):
                urlopen(url + "/%2e%2e/private.txt", timeout=5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_symlink_escape_is_rejected(self):
        output = self.folder / "review"
        dashboard.build_bundle(None, output)
        outside = self.folder / "private.txt"
        outside.write_text("private", encoding="utf-8")
        try:
            (output / "escape.txt").symlink_to(outside)
        except OSError:
            self.skipTest("Creating symlinks is not supported by this account")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(dashboard.ReviewRequestHandler, directory=str(output)))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{server.server_port}/escape.txt", timeout=5)
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
