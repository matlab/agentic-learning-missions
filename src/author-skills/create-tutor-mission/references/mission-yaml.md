# Mission YAML Reference

Use this reference after gathering requirements and drafting the task sequence.
`../references/mission-contract.md` remains the source of truth for the mission schema
and allowed MCP tools.

## Completion Blocks

Write each task's completion block in this format:

```yaml
completion:
  strategy:
    - tool: <real_mcp_tool_name>
      check: "<semantic description of what to verify and how>"
  description: >
    <Human-readable summary of the completed state>
```

Completion checks should reference state that exists only after the learner
finishes the task. Use semantic descriptions the tutor can interpret through
MCP state, not brittle string matching.

Use `kind: learner_confirmation` instead of `tool` only when the finished state
is a learner choice or reflection that should stay in chat rather than become a
required workspace file.

## High-Risk Task Verification Design

Before drafting a completion strategy for a task that depends on a simulation result, figure, Simulation Data Inspector signal, or direct model configuration, record these six design decisions:

| Decision | Author question |
| --- | --- |
| Learner-facing claim | What outcome does the instruction ask the learner to achieve? |
| Authoritative state | Which current model, result, figure, or SDI signal can establish that outcome? |
| Binding | How will inspection show that the evidence belongs to the learner's current model or artifact? |
| Freshness | What makes the observation current for this task instead of setup output, a prior task, or cached state? |
| Positive and negative evidence | What proves success, and what proves an unmet requirement or failed run? |
| Unverified fallback | What should the tutor say when inspection is stale, unavailable, or conflicting? |

Do not use a variable name, an active figure, a stopped simulation status, or cached output as sufficient evidence by itself. A simulation result must belong to the learner's current model. A figure check must inspect the task-owned figure and plotted content. An SDI check must inspect the required selected signal and its data. A configuration check must read the current parameter value. When direct current evidence conflicts with cached evidence, use the direct evidence. When no current evidence is available, keep the task pending and explain that verification is unavailable without calling the learner's work wrong.

## Common Completion-Check Mapping

| Intent | Tool | How to check |
| --- | --- | --- |
| Workspace variables exist | evaluate_matlab_code | `whos` or `exist(varname,"var")` |
| Figure is open | evaluate_matlab_code | Find task-owned figures through `get(groot,"Children")`; do not rely on `gcf` alone |
| Figure has plotted data | evaluate_matlab_code | Inspect lines in the identified task-owned figure, not only the active figure |
| Figure has N data series | evaluate_matlab_code | `numel(findobj(gcf,"Type","line"))` |
| Discover open models | evaluate_matlab_code | `find_system("type","block_diagram")` or `bdroot` |
| Model contains block type | model_read | Read root scope, depth 0; look for block type |
| Signal connections exist | model_read | Read root scope, depth 0; check connectivity |
| Model config parameter | model_query_params | `targets: ["config:<model>"]`, e.g., ExternalInput, SaveOutput, OutputSaveName |
| Block parameter value | model_query_params | `targets: ["blk_X"]`, specific param name |
| Model structure overview | model_overview | scope: root, detail: interfaces or full |
| Model diagnostics | model_read_diagnostics | read Diagnostic Viewer messages after compile/simulation |
| Structural model health | model_check | validate unconnected ports, dangling lines, or Stateflow lint |
| Parameter references | model_resolve_params | resolve variable references shown by model_read expressions |
| Behavioral model test | model_test | run a Gherkin test specification when the task goal requires it |
| MATLAB code quality | check_matlab_code | check `.m` files supplied or modified by a mission |
| MATLAB file execution | run_matlab_file | run a setup or helper `.m` file when execution is the stated goal |
| MATLAB test execution | run_matlab_test_file | run a MATLAB test file when the task goal requires it |
| Toolbox discovery | detect_matlab_toolboxes | detect required installed products or toolboxes |
| Model edits | model_edit | verify or describe structural edits only when the mission explicitly allows tool-assisted model modification |
| Simulation has run | evaluate_matlab_code | Confirm a successful current result belongs to the learner's model; stopped status or a result variable name alone is insufficient |
| Learner choice or reflection | learner_confirmation | ask the learner to state the choice or reflection in chat |

## Mission YAML Template

```yaml
version: "1.0.0"
title: <Mission Title>
objective: >
  <1-2 sentence learning objective with context and intended outcome. Clearly state any explicit prerequisite or assumed prior knowledge so Ada can include it in the opening summary. What will the learner be able to do by the end?>
supported_matlab_releases: [R2025a, R2025b]
required_capabilities: [matlab-mcp, simulink]
write_mode: read_inspect
capability_mode: guided_tutor
# Optional: declare an authored PNG or SVG thumbnail. Omit this field to use the app-rendered generic fallback.
allow_agent_edits: false

app:
  summary: <One-sentence tile summary>
  audience: <Intended learner audience>
  difficulty: beginner
  estimated_minutes: 30
  products: [MATLAB, Simulink]
  topics: [<topic tags>]
  status: published
  learner_visible: true
  tile_order: 10

setup:
  script: "setup_<mission_name>.m"
  description: >
    <What the script prepares in the workspace and why>

# Optional: verify setup and reset states with tests/validate_runtime.m.
runtime_expectations:
  setup:
    assertions:
      - type: workspace_var
        name: <prepared_variable>
  resets:
    - task: t02
      assertions:
        - type: model_loaded
          name: <prepared_model>

discovery:
  model_name:
    tool: evaluate_matlab_code
    code: "bdroot"
    note: >
      The learner creates their own model. Use bdroot or
      find_system('type','block_diagram') to discover its name.
      Store the result for all subsequent model_read / model_query_params calls.

tasks:
  - id: "t01"
    title: <Task title>
    involves: [<categories>]
    outcome_refs: [lo01]
    instruction: >
      <Learner-facing action + purpose. Include essential how-to details when needed.>
    completion:
      strategy:
        - tool: <tool_name>
          check: "<what to verify>"
      description: >
        <Completed state in plain language>
    hints:
      - <Directional prompt that identifies the relevant idea or area>
      - <Specific guidance for the likely unmet part>
      - <Optional direct procedure or complete recipe>
```

If the mission has explicit outcomes, add them before `setup`:

```yaml
learning_outcomes:
  - id: lo01
    description: <Observable learner capability>
```

Include the `setup` block only when the mission uses a setup script. If no setup
script is needed, omit `setup` and make task 1 explicit about the learner's
manual starting condition.

Include `discovery` when any task uses `model_read`, `model_query_params`, or
other model-specific MCP tools that need the learner's model name. Do not
prescribe a model name when the learner creates the model.

## Runtime and Edit Metadata

| Field | Purpose | Current consumer |
| --- | --- | --- |
| `write_mode` | Required static classification: `read_inspect` or `allow_agent_edits` | Validators and catalog |
| `capability_mode` | Required workflow classification: `guided_tutor`, `agent_build`, or `review_only` | Validators and catalog |
| `allow_agent_edits` | Optional runtime permission; defaults to `false` | Workspace preparation and learner tutor |
| `runtime_expectations` | Optional expected setup/reset state for runtime tests | `tests/validate_runtime.m` |

## Learning Outcome Rules

Every `outcome_refs` value must match one `learning_outcomes.id`. Each outcome
should be referenced by at least one task.

Make outcomes observable. If an outcome says the learner can "articulate" or
"explain" a concept, include a task that explicitly asks for that explanation
or reflection. Otherwise, phrase the outcome as an observable model-building,
configuration, comparison, or interpretation capability.

## YAML Verification Checklist

After creating or revising the mission YAML:

- [ ] Setup script is omitted when no setup code is needed.
- [ ] `allow_agent_edits` is omitted or `false` for read-only tutoring missions,
      and `true` only when tasks explicitly ask the learner to use an agent to
      generate or revise workspace artifacts.
- [ ] Required top-level metadata includes `version`, `supported_matlab_releases`, `required_capabilities`, `write_mode`, and `capability_mode`.
- [ ] The `app` block has summary, audience, difficulty, duration, product, topic, status, visibility, and tile-order metadata.
- [ ] All `tool` values in the YAML are real MCP tool names listed in `../references/mission-contract.md`; all `kind` values are supported completion kinds.
- [ ] Each completion check references state that only exists after the task is done, not before.
- [ ] The objective and Task 1 instruction support a concise opening background and one prediction question without using hints or completion criteria, and any explicit prerequisite or assumed-prior-knowledge statement is clear enough for Ada to include in that opening.
- [ ] Task sequence builds progressively; no task requires something from a later task.
- [ ] Instructions state goals and purpose without unnecessarily revealing the procedure or completed answer.
- [ ] Hints form a directional-to-specific-to-direct ladder and are not duplicated, contradictory, misleading, or technically inaccurate.
- [ ] Commands, UI paths, exact values, library paths, and wiring recipes appear only in later hints where their disclosure level is appropriate.
- [ ] Completion checks accept behaviorally equivalent solutions unless the instruction explicitly requires a particular implementation, and every check uses current observable state.
- [ ] Each high-risk task records its learner-facing claim, authoritative state, model or artifact binding, freshness evidence, positive and negative evidence, and unverified fallback.
- [ ] Simulation, figure, SDI, and configuration checks do not rely only on a result variable name, active figure, stopped status, or cached observation.
- [ ] Learner-visible names, values, and behavior agree across instructions, hints, completion checks, setup/reset scripts, and `runtime_expectations`.
- [ ] `runtime_expectations`, when present, assert only learner-relevant task-start state rather than incidental UI state such as autoscaled Scope axes.
- [ ] The `discovery` section is present if any task uses model-specific tools that need a model name.
- [ ] Learning outcomes, when present, use stable `loNN` IDs and are referenced by task `outcome_refs`.
- [ ] Any "articulate" or "explain" learning outcome is explicitly practiced or checked by a task.
- [ ] User-supplied instruction or hint text was either preserved verbatim by request or adapted consistently with the user's stated choice.
- [ ] If the user supplied instructions without hints, each task has generated hints derived from the instructions and mission rules.
