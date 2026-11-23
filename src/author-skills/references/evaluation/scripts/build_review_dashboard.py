"""Build an offline calibration dashboard from the exact review sources (stdlib only)."""

import argparse
import ast
import hashlib
import json
from pathlib import Path


def build_data(root):
    evidence_path = root / "design/mission-tutor-calibration-evidence.json"
    review_path = root / "design/mission-tutor-evaluation-calibration.md"
    evaluation = root / "src/author-skills/references/evaluation"
    cases_path = evaluation / "evals/milestone-4-draft.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    review = review_path.read_text(encoding="utf-8")
    probes_ast = ast.parse((evaluation / "scripts/mission_evals/learner_spec.py").read_text(encoding="utf-8"))
    questions = next(ast.literal_eval(node.value) for node in probes_ast.body
                     if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROBES" for t in node.targets))
    probe_section = review.split("## Learning-probe anchors for review", 1)[1].split("## Prepared implementation", 1)[0]
    rows = [line for line in probe_section.splitlines() if line.startswith("| Root ports /") or line.startswith("| Continuous/discrete /")]
    if len(rows) != 4:
        raise ValueError("Expected four learning-probe rows in the review document")
    items = []
    titles = {"inspection-displaces-output": "Inspection displaces output", "observed-recovery": "Observed recovery",
              "unexercised-recovery": "Unexercised recovery", "casual-tool-fluency": "Casual tool fluency",
              "naive-strong-baseline": "Naive strong baseline", "observer-error-at-acceptance": "Observer exception"}
    for case in evidence["cases"]:
        items.append({**case, "group": "evidence", "title": titles.get(case["id"], case["id"]),
                      "id": "evidence/" + case["id"]})
    for index, case in enumerate(cases["evals"]):
        fixture = (cases_path.parent / case["fixture"] / "mission.yaml").resolve()
        if not fixture.is_relative_to(cases_path.parent.resolve()):
            raise ValueError("Fixture must remain inside the evaluation specification directory")
        items.append({**case, "id": "case/" + case["id"], "case_id": case["id"], "group": "cases",
                      "title": case["id"].replace("-", " ").capitalize(), "existing": index < 4,
                      "fixture_text": fixture.read_text(encoding="utf-8")})
    for row in rows:
        title, full, partial, wrong = [cell.strip() for cell in row.strip("|").split("|")]
        mission = "root-inports-outports" if title.startswith("Root") else "continuous-and-discrete-time"
        kind = title.split(" / ")[1]
        items.append({"id": f"probe/{mission}/{kind}", "group": "probes", "title": title,
                      "question": questions[mission][0 if kind == "explanation" else 1],
                      "scores": {"2": full, "1": partial, "0": wrong}})
    source_paths = [evidence_path, cases_path, review_path]
    data = {"schema_version": "1.0", "title": "Mission tutor calibration", "milestone": 4,
            "status": "pending_author_review", "items": items, "review_document": review,
            "probe_principles": "\n".join(line for line in probe_section.splitlines() if line.strip() and not line.startswith("|")),
            "sources": [{"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in source_paths]}
    data["packet_sha256"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return data


def build(root, output, packet_path=None):
    if packet_path is None:
        data = build_data(root.resolve())
    else:
        data = json.loads(packet_path.read_text(encoding="utf-8"))
        if data.get("schema_version") != "1.0" or not data.get("items") or not data.get("groups"):
            raise ValueError("Expected a review packet with items and groups")
        if len({item["id"] for item in data["items"]}) != len(data["items"]):
            raise ValueError("Review item IDs must be unique")
        if any(item["group"] not in data["groups"] for item in data["items"]):
            raise ValueError("Unknown review group")
        data.pop("packet_sha256", None)
        data["packet_sha256"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assets = Path(__file__).parent / "review_dashboard"
    html = (assets / "template.html").read_text(encoding="utf-8")
    html = html.replace("__REVIEW_COUNT__", str(len(data["items"])))
    html = html.replace("/* REVIEW_STYLE */", (assets / "style.css").read_text(encoding="utf-8"))
    html = html.replace("/* REVIEW_APP */", (assets / "app.js").read_text(encoding="utf-8"))
    # Embedded source text is data: never permit a source excerpt to close the script tag.
    embedded = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = html.replace("__REVIEW_DATA__", embedded)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("build/evaluations/calibration-review/index.html"))
    parser.add_argument("--packet", type=Path, help="Render a self-contained follow-up packet instead of the initial review")
    parser.add_argument("--initial-review", action="store_true", help="Checkout-only historical review; requires original design inputs")
    args = parser.parse_args()
    if not args.packet and not args.initial_review:
        parser.error("Supply --packet for portable review, or --initial-review for historical checkout inputs")
    data = build(args.repo_root, args.output, args.packet)
    print(f"Dashboard: {args.output.resolve()} ({len(data['items'])} review items)")


if __name__ == "__main__":
    main()
