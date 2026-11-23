"""Generate a self-contained review bundle or serve it on loopback (stdlib only)."""

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re


SKILL_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_KIND = "mission-learner-review-feedback"


def script_data(page, element_id):
    """Read a single inert JSON script from the shared HTML template."""
    pattern = rf'(<script id="{element_id}" type="application/json">)(.*?)(</script>)'
    match = re.search(pattern, page, re.DOTALL)
    if match is None:
        raise ValueError(f"Template is missing {element_id}")
    return match


def validate_packet(packet):
    """Reject ambiguous review IDs and unusable decision controls."""
    if not isinstance(packet, dict) or packet.get("schema_version") != "1.0":
        raise ValueError("Expected a version 1.0 review packet")
    for field in ("title", "instructions"):
        if not isinstance(packet.get(field), str):
            raise ValueError(f"Packet {field} must be text")
    sources = packet.get("sources")
    if not isinstance(sources, list) or not all(isinstance(source, str) for source in sources):
        raise ValueError("Packet sources must be an array of strings")
    items = packet.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Packet must contain review items")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be an object")
        for field in ("id", "group", "title", "question", "evidence"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Item {field} must be nonempty text")
        if item["id"] in seen:
            raise ValueError("Review item IDs must be unique")
        seen.add(item["id"])
        choices = item.get("choices")
        if (not isinstance(choices, list) or len(choices) < 2
                or not all(isinstance(choice, str) and choice.strip() for choice in choices)
                or len(set(choices)) != len(choices) or "pending" in choices):
            raise ValueError("Choices must contain distinct nonempty decisions, excluding pending")


def embed_json(page, element_id, value):
    """Keep source text from closing its inert script element."""
    match = script_data(page, element_id)
    encoded = json.dumps(value, ensure_ascii=True)
    for character, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(character, escaped)
    return page[:match.start(2)] + encoded + page[match.end(2):]


def build_bundle(packet_path, output):
    """Write a fresh bundle; never overwrite an existing review folder."""
    page = (SKILL_ROOT / "assets/review.html").read_text(encoding="utf-8")
    raw_packet = (Path(packet_path).read_bytes() if packet_path else
                  script_data(page, "review-data").group(2).encode("utf-8"))
    packet = json.loads(raw_packet.decode("utf-8"))
    validate_packet(packet)
    fingerprint = hashlib.sha256(raw_packet).hexdigest()
    feedback = {"schema_version": "1.0", "kind": FEEDBACK_KIND,
                "packet_sha256": fingerprint, "reviewer": "", "overall_notes": "",
                "reviews": [{"id": item["id"], "decision": "pending", "notes": ""}
                            for item in packet["items"]]}
    page = embed_json(embed_json(page, "review-data", packet), "packet-fingerprint", fingerprint)
    guide = (SKILL_ROOT / "references/human-feedback.md").read_text(encoding="utf-8")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "packet.json").write_bytes(raw_packet)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "feedback-template.json").write_text(json.dumps(feedback, indent=2) + "\n", encoding="utf-8")
    (output / "REVIEW.md").write_text(
        "# This review bundle\n\nOpen `index.html`, or review `packet.json` and edit a copy of "
        "`feedback-template.json`. Return `packet.json` and the saved feedback path to the agent.\n\n"
        + guide, encoding="utf-8")
    return fingerprint


class ReviewRequestHandler(SimpleHTTPRequestHandler):
    """Do not expose files through symlinks or junctions outside the review root."""

    def send_head(self):
        requested = Path(self.translate_path(self.path)).resolve()
        if not requested.is_relative_to(Path(self.directory).resolve()):
            self.send_error(403, "Path is outside the review folder")
            return None
        return super().send_head()


def serve_bundle(directory, port=0):
    """Serve without a write endpoint; Ctrl+C closes the owned server."""
    directory = Path(directory).resolve()
    if not (directory / "index.html").is_file():
        raise ValueError("Review folder must contain index.html")
    handler = partial(ReviewRequestHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Review URL: http://127.0.0.1:{server.server_port}/", flush=True)
        print("Stop with Ctrl+C. Feedback is downloaded, not written by the server.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Generate HTML, packet, feedback template, and instructions")
    build.add_argument("--packet", type=Path, help="UTF-8 packet; omit for the dummy example")
    build.add_argument("--output", type=Path, required=True, help="New output folder")
    serve = commands.add_parser("serve", help="Serve an existing review folder on loopback")
    serve.add_argument("--directory", type=Path, required=True)
    serve.add_argument("--port", type=int, default=0, help="0 chooses an available port")
    args = parser.parse_args()
    try:
        if args.command == "build":
            fingerprint = build_bundle(args.packet, args.output)
            print(f"Review: {args.output.resolve() / 'index.html'}\nPacket SHA-256: {fingerprint}")
        else:
            serve_bundle(args.directory, args.port)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Review dashboard: {error}\n")


if __name__ == "__main__":
    main()
