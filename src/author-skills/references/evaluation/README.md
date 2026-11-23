# Evaluation Infrastructure

The standalone tutor-skill harness runs the actual `mission-tutoring` skill against controlled scenarios and real MATLAB state. The standalone learner simulator pairs the unchanged tutor with expert, casual, and naive learner contexts against full missions. Neither command runs the other suite. Optional `combined` execution runs both; saved composition only reads existing evidence. An infrastructure smoke command remains available for diagnosing the runtime.

## Author skills and copied workspaces

Use `evaluate-tutor-skill` for tutor behavior and teaching-quality checks, or `simulate-mission-learner` for mission specifications and simulated learners. These thin author-only skills invoke the same runner described below. `startMissionAuthoring` copies both skills and the complete shared evaluation resources into `.interactive-missions/authoring/skills`; Codex also receives the native copy under `.codex/skills`. Other author adapters point to the portable skills, but evaluation still uses the pinned Codex SDK. This does not expand evaluator runtime qualification.

Examples below use development-checkout paths. In a prepared authoring workspace, replace `src/author-skills/references/evaluation` with `.interactive-missions/authoring/skills/references/evaluation` (or the native Codex copy). Locate the selected tutor skill and `--toolbox-root` in the installed toolbox or an explicit source snapshot; they are not copied into authoring workspaces. Keep runtime environments and synthetic evidence outside packaged skills.

Author-workspace copying and toolbox packaging exclude Python bytecode and `__pycache__` folders. Packaging supplies its explicit source/documentation file list when constructing toolbox options, so it does not first scan ignored evaluation evidence or the pinned environment under `build/`. The metadata helper returns the updated value object so declared package and product dependencies persist.

## Setup

The validated environment is Windows, Python 3.13, Codex SDK/CLI 0.162.1, MATLAB MCP Core Server 0.10.1, and MATLAB R2026b. The [official Codex Python SDK](https://learn.chatgpt.com/docs/codex-sdk) supplies its own pinned CLI executable, so this runner does not depend on the `codex` shim on PATH.

From the repository root, create an isolated environment and install the pinned dependencies:

```powershell
python -m venv build\evaluation-venv
& '.\build\evaluation-venv\Scripts\python.exe' -m pip install -r src\author-skills\references\evaluation\requirements-win-py313.txt
```

Use the existing Codex model/provider configuration and authentication. The runner preserves the configured model catalog, service tier, and approval policy alongside model/provider settings and, when present, file-based authentication in a disposable runtime home. Provider environment variables remain available to the child process. It does not copy the author's skills, MCP configuration, plugins, or conversation history. Credential files are never included in reports. Keyring-only authentication has not been qualified. Automatic review stays enabled; review-service failures stop the affected trial as insufficient evidence rather than grading the tutor's blocked actions as failures.

## Run tutor-skill evaluations

Run controlled cases without MATLAB:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' src\author-skills\references\evaluation\scripts\evaluate.py skill-eval --skill src\skills\mission-tutoring --layer behavior --output build\evaluations\tutor-behavior
```

Run both layers and compare an explicit baseline skill with the candidate:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' src\author-skills\references\evaluation\scripts\evaluate.py skill-eval --skill src\skills\mission-tutoring --baseline path\to\baseline\mission-tutoring --output build\evaluations\tutor-comparison --matlab-server 'C:\Users\aschor\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe' --matlab-root 'C:\Program Files\MATLAB\R2026b' --toolbox-root 'L:\interactive-missions'
```

`--layer` selects `behavior`, `live`, or `all` (default). `--case` selects a case ID and can be repeated. `--cases-file` selects a case specification with the same schema as `evals/evals.json`. Each case runs twice by default; use `--trials 1` for a quick diagnostic, which cannot establish the confirming-run quality bar. The total budget defaults to 3600 seconds, and each trial is capped at 600 seconds. Configure these with `--timeout-seconds` and `--trial-timeout-seconds`.

The default suite contains 15 author-accepted cases: 14 controlled behavior cases and one live MATLAB case. These cover startup, invocation, hint/effort rules, disputed assessments, rescue, read-only ownership, missing capability, inspection failure/recovery, claimed alternative expressions, and deliberately inaccurate hints. They use scalar mission fixtures. `author_review=reviewed` approves case definitions; `grading_calibration=pending_validation` keeps broader qualification provisional because agreement on reviewed examples does not establish unseen-trace accuracy. This adapter is not a generic MATLAB interpreter.

All 15 cases in `evals/milestone-4-draft.json` are now accepted and included in the default suite; the filename is retained for compatibility. The alternative-expression case explicitly reports that the expression is not executed, and the inaccurate-hint case identifies the injected authoring error. Completed review decisions are preserved in the development history. Controlled cases can declare per-step `tool_errors` for evaluation or product detection; these return explicit errors only to the tutor while independent driver observations remain available. The next step resets these errors. Live cases reject this option and continue to use real MCP results.

Explicit invocation uses the Codex SDK's native `SkillInput` with the copied skill. Implicit and negative controls receive only an isolated catalog entry containing the skill's name, description, and path; invocation is evidenced by reading `SKILL.md`. This tests selection from the supplied catalog, not discovery of arbitrary host-installed skills. The skill and its references are unchanged.

The tutor has a workspace-bounded file reader and the selected product tools over a bearer-authenticated loopback MCP bridge. Shell execution and unrelated host MCP servers are not exposed. Controlled product calls return the case's declared observations. Live calls run the tutor's requested code in the owned MATLAB session under an error-capture wrapper; the wrapper does not repair the code. It catches MATLAB errors that Core Server 0.10.1 can otherwise return with `isError=false`. Original tool arguments and returned evidence remain in the trace. Live MATLAB execution is correctly marked as potentially destructive and remains subject to automatic approval review.

Live cases use `interactiveMissions.prepareWorkspace` with `ContentRoot`, `TutorSkillRoot`, and `RegisterWorkspace=false`. A separate empty learner folder avoids files MATLAB may create in its startup directory. Practice mode stays progress-free, and no test mode is added to the tutor skill. The harness driver changes fixture state between scripted messages; the tutor only observes and responds.

Independent deterministic checks assess invocation, required reads, fresh inspection, completion feedback, early recipe disclosure, protected product state, and bundle integrity. All learner-visible tutor messages, including commentary, are included in grading. A separate tool-free Codex context grades teaching quality against the case and mission, citing trace event IDs. Invalid or missing evidence references become `unknown`. Qualitative grades remain provisional; the shipped case specification records `grading_calibration=pending_validation` after the completed author review.

The qualitative grader also receives the learner requests, declared driver steps, and returned tool results. A successful-inspection assertion requires a successful observation; `inspection_error` separately checks that a scripted failed observation was encountered. Neither an unavailable observation nor the learner's confidence establishes completion.

Controlled state replies identify exact MATLAB variable names and properties; internal bookkeeping keys are not presented as learner variable names. Fixture labels belong in report context, not tutor behavior requirements: Ada handles the observations as conditions within its scenario and is not required to disclose an evaluation mode. The missing-capability case therefore permits normal connection-restoration guidance while still requiring startup to stop.

### Skill-evaluation outputs and offline commands

Inputs are frozen under `inputs/` before execution. `manifest.json` records source, case, fixture, runner, and dependency fingerprints. Each configuration/case/trial directory contains `events.jsonl` and `grading.json`, plus live server diagnostics when applicable. `benchmark.json` contains trial results and separate configuration summaries; `comparison.json` pairs compatible baseline/candidate trials; `report.md` summarizes outcomes and evidence references. Identical baseline/candidate skill hashes are identified explicitly, so such runs are repeatability checks rather than evidence of improvement.

Rebuild reports without model or MATLAB calls, including after an interrupted invocation:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' src\author-skills\references\evaluation\scripts\evaluate.py report --run build\evaluations\tutor-comparison
```

Compare two separate candidate-only runs with matching case, fixture, rubric, runner, dependency, and trial-count inputs:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' src\author-skills\references\evaluation\scripts\evaluate.py compare --baseline-run build\evaluations\old --candidate-run build\evaluations\new --output build\evaluations\comparison
```

Different resolved runtimes or incomplete execution make a trial pair non-comparable. Comparisons include per-assertion changes and links to the source traces. No single combined score hides a failed assertion. Exit code 0 means all executed trials passed; 1 means an observed failure; 2 means missing or incomplete evidence (or invalid command arguments). Inspect the separate readiness field before treating results as a quality gate: uncalibrated grading, fewer than two trials, and missing trials prevent a readiness pass.

## Run the smoke check

Supply the installed MCP executable and MATLAB installation root. The following paths match the validated development machine:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' src\author-skills\references\evaluation\scripts\evaluate.py smoke --output build\evaluations\runtime-smoke --matlab-server 'C:\Users\aschor\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe' --matlab-root 'C:\Program Files\MATLAB\R2026b'
```

The output directory must not exist. Use a different directory for each trial. `--component codex` runs only the context proof; `--component matlab` runs only the product-session proof. The default is `all`. `--model` explicitly selects a model; when omitted, the runner preserves the configured model. The smoke budget defaults to 600 seconds and can be changed with `--timeout-seconds`; individual MCP calls have a 120-second read timeout.

The Codex check starts two fresh, ephemeral threads. One receives a random marker, the other must report that it has no marker, and a subsequent turn in the first thread must recall its marker. Tool use is unexpected in this context-only proof. Thread IDs, effective model/provider, reasoning effort, CLI version, streamed events, and token-usage notifications are recorded.

The MATLAB check launches the MCP server with `--matlab-session-mode=new` and `--matlab-display-mode=nodesktop`. MATLAB is launched only by MCP. Before changing product state, the runner verifies the MATLAB PID belongs to its server process tree, the working directory and preferences are trial-local, and the requested installation is in use. A harness-driven learner call sets a value; a harness-driven tutor call verifies it through the same serialized broker. These role labels do not claim that Codex agents executed MATLAB calls in Milestone 1.

Both checks remove their temporary state after completion or failure. Cleanup waits for graceful exit, then stops only captured owned processes if necessary. It verifies that all captured processes exited. Read-only Git cache files are handled inside the verified trial directory. Short temporary paths accommodate MCP socket paths on Windows.

The broker provides serialization, attribution, and evidence capture. It is not a security sandbox for arbitrary MATLAB code. The skill-eval command supplies scripted scenarios; learner-sim supplies separate tutor, learner, and grader contexts.

## Run learner simulations independently

Generate a draft specification for each mission. This is an offline operation:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py learner-sim prepare --mission marketplace\missions\root-inports-outports --output build\evaluations\mission-specs\root-inports-outports.json
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py learner-sim prepare --mission marketplace\missions\continuous-and-discrete-time --output build\evaluations\mission-specs\continuous-and-discrete-time.json
```

The draft binds to the exact mission files and includes outcomes, acceptable alternatives, independent-check references, mistake cases, expected recovery, probes, and grading criteria. The initial observers support the two packaged missions. Drafts for other missions require an observer before execution. Review both the specification and `scripts/observe_mission.m`; changing `author_review` or `grading_calibration` to `reviewed` records an author's decision, not automatic approval. Unreviewed specifications and rubric judgments remain provisional and cannot produce a readiness pass.

Run all three profiles through both missions, without invoking `skill-eval`:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py learner-sim run --mission marketplace\missions\root-inports-outports --mission marketplace\missions\continuous-and-discrete-time --spec-dir build\evaluations\mission-specs --skill src\skills\mission-tutoring --output build\evaluations\learner-pilot --trials 1 --matlab-server 'C:\Users\aschor\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe' --matlab-root 'C:\Program Files\MATLAB\R2026b' --toolbox-root 'L:\interactive-missions' --extension-file 'C:\Users\aschor\.matlab\agentic-toolkits\simulink\tools\tools.json' --toolkit-root 'C:\Users\aschor\.matlab\agentic-toolkits\simulink'
```

The default is two trials per mission/profile, a 3600-second invocation budget, a 1200-second trial budget, and 12 dialogue turns per task. Each learner dialogue turn allows at most five bounded action-planning responses, each with at most four requested product calls. Trials run serially. Use repeated `--profile expert|casual|naive` to select profiles, `--seed` to select the first scenario seed, and `--max-tasks 1` for a one-task infrastructure diagnostic. A diagnostic cannot qualify a whole mission. `--timeout-seconds`, `--trial-timeout-seconds`, and `--turns-per-task` change the budgets. A seed reproducibly selects a mistake schedule; different seeds can select the same schedule, and model replies are not guaranteed to repeat. Budget exhaustion preserves partial evidence and is not success. Creating an empty `STOP` file in the output folder ends the current trial at the next dialogue boundary and prevents another trial from starting; cleanup and partial grading still run.

The installed Core Server 0.10.1 exposes only five core tools by default. Its `--extension-file` option loads the installed Simulink toolkit's `tools.json`, including the exact tool schemas and function mappings. The runner records the resulting catalog, verifies required tools, and exposes installed read/inspection tools to Ada. The learner can request those tools plus `model_edit`. The scalar skill-eval backend is unchanged. The runner adds the explicit `--toolkit-root` and its `tools/` subfolders to the owned MATLAB session path, verifies the functions exist, and records the installed toolkit version and file fingerprint. It does not share or attach to the author's MATLAB session.

Each trial prepares an unregistered practice workspace, a separate empty learner context folder, a separate product working folder, two fresh Codex clients, and one owned MATLAB MCP session. Before starting any thread, the runner uses the documented `skills/list` and `config/batchWrite` [app-server APIs](https://developers.openai.com/codex/app-server/) to disable host skills in the disposable configuration and verifies the effective catalog. The tutor retains only workspace-local skills; the learner and grader have empty catalogs. `CODEX_HOME` isolation alone does not hide `.agents/skills`. Ada receives the copied production skill through native `SkillInput`. The learner receives its profile, applicable assigned behavior, learner-visible messages, tool descriptions, and actual product results. It receives no mission YAML, unrevealed hints, reference solution, grader feedback, or authoring history. Its explicit action plans are executed exactly through the serialized broker; errors return to the learner and are never silently repaired. A separate tool-free grader sees the evidence only after the conversation. Pre/post probes are administered outside Ada's conversation using the learner's continuing context.

Role separation and file guards prevent accidental hidden-input access. Arbitrary MATLAB execution is not an OS security sandbox against a hostile learner. The tutor's normal read-only rules remain in the unchanged production skill; state observations and an independent rubric assess violations. No tutoring test mode, production logging, or automatic mission/tutor revision is added.

Core Server 0.10.1 uses Live Editor capture, which can delete implicit inline figures on the next MCP call. The full-mission wrapper restores MATLAB's normal `DefaultFigureVisible="on"` setting before executing the exact requested code. It does not create missing plots or override explicit figure visibility choices. This keeps learner-created figures available for later inspection without changing the tutor skill or repairing an intended mistake.

### Learner outputs and interpretation

Each run freezes the tutor, mission, specification, runner/observer, and extension definitions under `inputs/`. `manifest.json` records hashes, dependency versions, seeds, and budgets. Each `trials/<mission>/<profile>/seed-<seed>/` contains canonical `events.jsonl`, an `actions.jsonl` view, `grading.json`, and saved learner product files when available. Raw SDK notifications retain token-use events and resolved runtime details. Checkpoints record independent observations before learner actions and before/after tutor turns. Process ownership and cleanup are recorded. Temporary settings and credentials are removed; generated evidence stays local under ignored `build/` until archive upload/download checksums and retention are verified.

The action view includes `timestamp`, `learner_type`, `mission_name`, `mission_task_id`, `action`, `agent_message`, `learner_response`, and `product_actions`, with links to canonical events. Intentions, executed calls, observed results, incomplete turns, errors, and stop reasons remain reconstructable. This supports inspection, not deterministic replay.

Independent observers check actual input/plot data, root-port connectivity and configuration, simulation provenance, filtered output behavior, SDI data, comparison plots, and sampling configuration. The two continuous/discrete tasks that explicitly change source timing and require another run must produce a SimulationOutput newer than the task's initial observation; an old result cannot satisfy the required rerun. The low-pass check simulates slow and fast inputs using `SimulationInput` overrides and accepts equivalent implementations with the requested 0.15-second response. Numeric sample-time expressions and renamed blocks are accepted. Unqualified sampling-stage alternatives return `unknown`. Current observers do not establish desktop usability, Scope rendering, SDI window visibility, or every possible alternative. The independent rubric distinguishes false rejection from questions or hints; Ada's acceptance is checked against product evidence. Missing evidence never becomes a pass.

Persona fidelity and recovery are separate from tutor compliance. Scheduled partial attempts require actual actions, an observed state change, and an unmet outcome. The grader also assesses the profile over the conversation. Explanation and transfer probes receive separate pre/post scores from 0 to 2; a strong expert baseline need not improve. These are simulated learning proxies, not demonstrated human learning. Findings include severity, evidence IDs, consequence, likely cause, confidence, proposed change, and a confirming test.

The learner grader receives author-reviewed guidance from `scripts/mission_evals/author_calibration.json`: increasing casual understanding is allowed; advanced naive understanding before instruction is assessed separately; unexercised recovery and unresolved attribution remain unknown; and verification should address the instruction directly. Recovered API errors are acceptable when later successful checks establish the outcome. Reviewed probe anchors apply only to the exact questions. Missing answers use null/unknown rather than invented gains. The latest SDI author label is a task-scoped verification-sufficiency pass; the original independent outcome remains unknown. Tentative preferences for future passive verification and separate reference models are recorded without changing production tutor policy.

Saved-trace calibration accepts explicit `--source-root` and `--review-evidence` inputs. Restore archived traces into their original relative layout before replay. Portable review dashboards accept a self-contained `--packet`; `--initial-review` is only for historical checkout inputs. Historical checkout commands and completed review decisions live in the development history, outside installed authoring assets.

## Optional combined workflow

Run both suites only when both are useful to the author question. Tutor changes usually call for `skill-eval`; mission changes usually call for `learner-sim`. Neither evaluation requires a passing result from the other. A combined report preserves each component's full grades, review context, snapshots, runtimes, readiness, limitations, and trace links. It provides no aggregate quality score and makes no new qualification claim.

For a bounded integration diagnostic, prepare the mission specification as above, then run:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py combined --skill src\skills\mission-tutoring --layer behavior --case hint-before-effort --skill-trials 1 --mission marketplace\missions\continuous-and-discrete-time --spec-dir build\evaluations\mission-specs --profile expert --learner-trials 1 --max-tasks 1 --output build\evaluations\combined-diagnostic --matlab-server 'C:\Users\aschor\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe' --matlab-root 'C:\Program Files\MATLAB\R2026b' --toolbox-root 'L:\interactive-missions' --extension-file 'C:\Users\aschor\.matlab\agentic-toolkits\simulink\tools\tools.json' --toolkit-root 'C:\Users\aschor\.matlab\agentic-toolkits\simulink'
```

Fresh mode requires the shared `--skill`, mission/specification, and runtime inputs. Repeat `--case`, `--mission`, `--profile`, and `--extension-file` as needed. Defaults are all skill layers, all three learner profiles, two trials per suite, seed 73, 12 turns per task, and no task limit. `--skill-baseline` adds a baseline to the skill component only; use independent learner `compare` commands for learner baselines. `--cases-file` selects a different accepted case specification.

Skill evaluation runs first, then learner simulation, serially under one `--timeout-seconds` budget (default 3600). Separate `--skill-trial-timeout-seconds` and `--learner-trial-timeout-seconds` default to 600 and 1200. Snapshot/setup time counts against the shared deadline. Cleanup may extend elapsed wall time beyond that deadline. An observed failure in one suite does not gate the other. Budget exhaustion, cancellation, or an empty `STOP` file in the combined output folder prevents further trials; the active learner trial checks STOP at dialogue boundaries, while skill evaluation checks between trials. Cleanup and available partial results are retained.

Compose saved runs without model or MATLAB calls:

```powershell
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py combined --skill-run build\evaluations\tutor-behavior --learner-run build\evaluations\learner-pilot --output build\evaluations\combined-saved
& '.\build\evaluation-venv\Scripts\python.exe' -B src\author-skills\references\evaluation\scripts\evaluate.py report --run build\evaluations\combined-saved
```

Saved mode requires both source folders and rejects fresh execution options. The output must be new and outside both sources. Source suite identities, trace availability, ordering, and trial IDs are checked before composition; source reports are never rewritten. Missing initial evidence prevents composition. Rebuilding later records unavailable evidence and retains the last known component result without promoting it to a pass. Retain source folders: the combined output links them rather than duplicating all traces. Rebuilding reads their current saved evidence and records file fingerprints; it does not rerun graders. Interrupted trials without published grades are unknown.

Fresh outputs contain `skill-eval/` and `learner-sim/`, each with its normal independently usable files. The parent holds `manifest.json`, `benchmark.json`, and `report.md`. Saved output has the same parent files and links external component folders. The JSON preserves complete component results and limitations. The Markdown shows separate readiness and execution counts, source fingerprints, snapshot/runtime identifiers, and evidence links. Different source versions remain visible; composition does not make them compatible baselines. Exit 1 means at least one observed failure; otherwise 2 means incomplete, missing, or unknown evidence; otherwise 0 means executed trials passed. Readiness must still be inspected separately.

For coupled mission/tutor changes, use explicit old/new mission and tutor snapshots in a targeted four-way matrix, holding cases, schedules, and graders fixed. Use the existing independent comparison commands where their compatibility checks permit it; a changed mission or grader cannot bypass those checks through composition. Separate reports and targeted interaction analysis can still describe differences without claiming a controlled baseline comparison.

Preserve the completed author decisions: both boundary labels are unknown; the fuller SDI verification is pass, while its historical independent product outcome remains unknown. All 15 cases are accepted. Tentative passive-inspection/separate-reference-model preferences are future design guidance, not production policy. Evaluator review is not authorization to fix all reported tutor or mission issues. Calibration agreement on reviewed traces does not establish unseen-trace accuracy.

## Evidence

Each invocation writes:

- `manifest.json`: run identity, component selection, environment/package versions, requested model, and time budget.
- `events.jsonl`: ordered events written and flushed before each operation returns, including inputs, SDK notifications, tool calls/results/errors, ownership assertions, and cleanup outcomes.
- `report.json`: pass/failure status, checked outcomes, resolved Codex configuration, MATLAB release, elapsed time, and event count. Nested errors remain visible when both execution and cleanup fail.
- `matlab-server.stderr.log` and `matlab-server-logs/`: text diagnostics when the MATLAB component runs. Generated TLS credentials and other server runtime files stay in the disposable workspace and are removed.

Reports remain local until explicitly removed. A failed or timed-out smoke is an infrastructure failure; it cannot produce a mission-quality pass. A component-only pass covers only that component. The event reader rejects truncated, duplicate, unsupported-schema, or out-of-order evidence rather than dropping it silently.

## Validation

Use the repository framework and package validators when working in a development checkout. Prepared author workspaces use their copied skills and explicit saved inputs. Historical review dashboards and source-trace regressions are maintainer diagnostics; they do not expand runtime qualification. Keep environments and raw evidence outside packaged authoring assets.
