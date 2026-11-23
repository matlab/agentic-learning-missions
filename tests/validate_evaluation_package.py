"""Inspect a built toolbox's author evaluation assets and declared dependencies."""

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def validate(package, release=False):
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        required = {
            "src/author-skills/evaluate-tutor-skill/SKILL.md",
            "src/author-skills/simulate-mission-learner/SKILL.md",
            "src/author-skills/references/evaluation/requirements-win-py313.txt",
            "src/author-skills/references/evaluation/scripts/evaluate.py",
            "src/author-skills/references/evaluation/scripts/mission_evals/combined.py",
            "src/author-skills/references/evaluation/scripts/observe_mission.m",
            "src/author-skills/references/evaluation/evals/evals.json",
        }
        for relative in required:
            if "fsroot/" + relative not in names:
                raise ValueError(f"Missing packaged asset: {relative}")
        for name in names:
            if "__pycache__" in name.split("/") or name.endswith((".pyc", ".pyo")) or name.startswith(("fsroot/build/", "fsroot/design/", "fsroot/eval/")):
                raise ValueError(f"Generated runtime artifact was packaged: {name}")
            if name.startswith("fsroot/src/skills/") and name.endswith("/SKILL.md") and name != "fsroot/src/skills/mission-tutoring/SKILL.md":
                raise ValueError(f"Author skill exposed as a learner skill: {name}")
        manifest = json.loads(archive.read("fsroot/resources/mpackage.json"))
        dependencies = {item["name"] for item in manifest["dependencies"]}
        expected = {"MathWorksAgenticToolkitSetup", "MatlabMcpServerToolbox"}
        if release and dependencies:
            raise ValueError("Public release must omit package-setup dependencies")
        if not release and not expected.issubset(dependencies):
            raise ValueError("Declared package dependencies were lost during packaging")
        requirements = ET.fromstring(archive.read("metadata/systemRequirements.xml"))
        products = {item.attrib["name"] for item in requirements.findall(".//{*}product")}
        if release:
            gallery = ET.fromstring(archive.read("fsroot/DesktopToolset.xml"))
            if "fsroot/src/InteractiveMissions.m" not in names or not any(
                    tool.get("app_file_path") == "InteractiveMissions.m" for tool in gallery.findall(".//tool")):
                raise ValueError("Public app entry or gallery configuration missing")
        if not {"MATLAB", "Simulink"}.issubset(products):
            raise ValueError("Declared MATLAB/Simulink product dependencies were lost")
        cases = json.loads(archive.read("fsroot/src/author-skills/references/evaluation/evals/evals.json"))
        if cases["grading_calibration"] != "pending_validation" or len(cases["evals"]) != 15:
            raise ValueError("Expected the 15 accepted, provisionally calibrated pilot cases")
        return {"package": str(package.resolve()), "entries": len(names), "author_assets_present": True,
                "generated_artifacts_excluded": True, "package_dependencies": sorted(dependencies),
                "product_dependencies": sorted(products), "cases": len(cases["evals"]),
                "grading_calibration": cases["grading_calibration"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path("build/InteractiveMissions.mltbx"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.package)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
