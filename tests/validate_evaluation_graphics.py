"""Opt-in real-MCP regression for persistent figures and unchanged learner intent."""

import argparse
import asyncio
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

from mission_evals.events import EventLog, write_json
from mission_evals.matlab_runtime import owned_matlab, result_text
from mission_evals.mission_backend import MissionBackend
from mission_evals.workspace import trial_workspace


async def validate(args):
    args.output.mkdir(parents=True, exist_ok=False)
    with EventLog(args.output / "events.jsonl", run_id=str(uuid.uuid4()),
                  suite="infrastructure", case_id="persistent-graphics") as log:
        with trial_workspace() as root:
            async with owned_matlab(root, log, server=args.matlab_server, matlab_root=args.matlab_root) as (broker, _):
                backend = MissionBackend(broker, root / "matlab-workspace", SCRIPTS / "observe_mission.m")

                async def execute(code):
                    reply = await backend.call("evaluate_matlab_code", {"code": code}, "fixture")
                    if reply.is_error:
                        raise RuntimeError(result_text(reply))

                await execute('respiratoryData=timeseries((1:3)\',(0:2)\'); figure; plot(respiratoryData);')
                visible = await backend.observe("root-inports-outports", "t01")
                await execute("close all; value=42;")
                omitted = await backend.observe("root-inports-outports", "t01")
                await execute('hiddenFigure=figure("Visible","off"); hiddenAxes=axes("Parent",hiddenFigure); '
                              'plot(hiddenAxes,respiratoryData.Time,respiratoryData.Data);')
                hidden = await backend.observe("root-inports-outports", "t01")
                results = {"visible_plot": visible["status"], "omitted_plot": omitted["status"],
                           "hidden_plot": hidden["status"]}
                log.emit("graphics.assertions", "checker", results)
                if results != {"visible_plot": "pass", "omitted_plot": "fail", "hidden_plot": "fail"}:
                    raise RuntimeError(f"Graphics regression: {results}")
        results["workspace_removed"] = not root.exists()
    write_json(args.output / "result.json", results)
    print(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matlab-server", required=True, type=Path)
    parser.add_argument("--matlab-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for name in ("matlab_server", "matlab_root", "output"):
        setattr(args, name, getattr(args, name).resolve())
    asyncio.run(validate(args))


if __name__ == "__main__":
    main()
