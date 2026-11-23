"""Opt-in real-MCP regression for independent SDI checks with multiple runs."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "src/author-skills/references/evaluation/scripts"
sys.path.insert(0, str(SCRIPTS))

from mission_evals.events import EventLog, write_json
from mission_evals.matlab_runtime import owned_matlab, result_text
from mission_evals.mission_backend import MissionBackend
from mission_evals.skill_assets import matlab_string
from mission_evals.workspace import trial_workspace


async def validate(args):
    args.output.mkdir(parents=True, exist_ok=False)
    with EventLog(args.output / "events.jsonl", run_id=str(uuid.uuid4()),
                  suite="infrastructure", case_id="sdi-multiple-runs") as log:
        with trial_workspace() as root:
            async with owned_matlab(root, log, server=args.matlab_server, matlab_root=args.matlab_root,
                                    extensions=[args.toolkit_root / "tools/tools.json"]) as (broker, _):
                backend = MissionBackend(broker, root / "matlab-workspace", SCRIPTS / "observe_mission.m")

                async def execute(code):
                    reply = await backend.call("evaluate_matlab_code", {"code": code}, "fixture")
                    if reply.is_error:
                        raise RuntimeError(result_text(reply))

                await execute(f'addpath(genpath({matlab_string(args.toolkit_root / "tools")})); '
                              'load_system("simulink"); '
                              'assert(string(get_param("simulink/Sources/Constant","BlockType"))=="Constant"); '
                              'assert(isfield(get_param("simulink/Sources/Constant","DialogParameters"),"Value")); '
                              'new_system("evaluationSdiProbe"); open_system("evaluationSdiProbe");')
                await broker.call("fixture", "model_read", {"model": "evaluationSdiProbe", "scope": "root", "depth": "0"})
                operations = [{"op": "add_block", "type": "Constant", "name": "Source", "ref": "source", "params": {"Value": "2"}},
                              {"op": "add_block", "type": "Outport", "name": "Result", "ref": "result"},
                              {"op": "connect", "target": "#source.y1 -> #result.u1"}]
                reply = await broker.call("fixture", "model_edit", {"model": "evaluationSdiProbe", "scope": "root",
                                          "layout_mode": "full", "operations": json.dumps(operations)})
                if "status: ok" not in result_text(reply):
                    raise RuntimeError("SDI fixture creation failed: " + result_text(reply))
                await execute('in=Simulink.SimulationInput("evaluationSdiProbe"); '
                              'in=in.setModelParameter("StopTime","0.01","SaveOutput","on","OutputSaveName","yout","SaveFormat","Dataset"); '
                              'out=sim(in); Simulink.sdi.clear; '
                              'unrelated=timeseries(99*ones(size(out.yout{1}.Values.Data)),out.yout{1}.Values.Time); '
                              'sdiUnrelatedId=Simulink.sdi.createRun("Unrelated","vars",unrelated); '
                              'sdiUnrelatedRun=Simulink.sdi.getRun(sdiUnrelatedId); '
                              'sdiUnrelatedSignal=sdiUnrelatedRun.getSignalByIndex(1); sdiUnrelatedSignal.Checked=true;')
                before = await backend.observe("root-inports-outports", "t06")
                log.emit("sdi.observation", "checker", {"stage": "unrelated_only", "observation": before})
                await execute('sdiMatchingId=Simulink.sdi.createRun("Matching","vars",out.yout); '
                              'sdiMatchingRun=Simulink.sdi.getRun(sdiMatchingId); '
                              'sdiMatchingSignal=sdiMatchingRun.getSignalByIndex(1); sdiMatchingSignal.Checked=false; '
                              'assert(numel(Simulink.sdi.getAllRunIDs)>=2); '
                              'disp("SDI_RUN_ID_SHAPE "+mat2str(size(Simulink.sdi.getAllRunIDs)));')
                unselected = await backend.observe("root-inports-outports", "t06")
                log.emit("sdi.observation", "checker", {"stage": "matching_but_not_plotted", "observation": unselected})
                await execute('sdiMatchingSignal.Checked=true;')
                after = await backend.observe("root-inports-outports", "t06")
                log.emit("sdi.observation", "checker", {"stage": "multiple_with_match", "observation": after})
                results = {"unrelated_only": before["status"], "matching_but_not_plotted": unselected["status"],
                           "multiple_with_match": after["status"]}
                if results != {"unrelated_only": "fail", "matching_but_not_plotted": "fail", "multiple_with_match": "pass"}:
                    raise RuntimeError(f"SDI regression: {results}")
        results["workspace_removed"] = not root.exists()
    write_json(args.output / "result.json", results)
    print(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("matlab-server", "matlab-root", "toolkit-root", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    for name in ("matlab_server", "matlab_root", "toolkit_root", "output"):
        setattr(args, name, getattr(args, name).resolve())
    asyncio.run(validate(args))


if __name__ == "__main__":
    main()
