# Mission YAML Overview

Mission YAML is the learner mission definition. It describes the mission metadata, learner-facing task sequence, and completion checks. Published missions live in `marketplace/missions/<mission-name>/mission.yaml`; the folder slug is the stable identity.

This page is a practical overview. The exact contract is the shared author-skill [Mission Contract](../src/author-skills/references/mission-contract.md). In a workspace created by `startMissionAuthoring()`, the copied contract is at `.interactive-missions/authoring/skills/references/mission-contract.md`.
## Mission Metadata

Each mission starts with required package metadata, title, objective, and tasks.

```yaml
version: "1.0.0"
title: "Inspect and Filter a Signal"
objective: >
  Build a simple Simulink model that filters workspace data and compare the
  filtered output with the original signal.
supported_matlab_releases: [R2025a, R2025b]
required_capabilities: [matlab-mcp, simulink]
write_mode: read_inspect
capability_mode: guided_tutor
# Optional: declare an authored PNG or SVG thumbnail. Omit this field to use the app-rendered generic fallback.
allow_agent_edits: false
```

Use the objective to describe what the learner will be able to do, not just what blocks or commands they will touch. Ada also uses the title and objective, with optional Task 1 context, for a short opening background and prediction question. State any explicit prerequisite or assumed prior knowledge clearly in the objective so Ada can include it in that opening. Include enough context and intended outcome for the opening without relying on hints or completion checks.

`thumbnail` is optional. Omit it, or leave it empty, to use the app-rendered generic graphic. If you declare one, provide an existing PNG or SVG path relative to the mission folder or marketplace root.

`allow_agent_edits` is optional and defaults to `false`. Set it to `true` only
for missions where learners are meant to ask an agentic client to generate or
revise artifacts in their safe workspace, such as MATLAB&reg; scripts, notes, plots,
or model edits.

## App Metadata

Each runnable mission also includes an `app` block. `learner_visible` controls inclusion in the learner catalog. `status` is display metadata. The app does not filter or gate missions by audience, products, difficulty, or status.

```yaml
app:
  summary: "Inspect workspace data and feed it through root ports."
  audience: "Beginner Simulink learners comfortable with MATLAB variables."
  difficulty: beginner
  estimated_minutes: 45
  products: [MATLAB, Simulink]
  topics: [workspace data, root inports]
  status: published
  learner_visible: true
  tile_order: 10
```

Use `status: demo` for learner-visible UI validation missions and `status: draft` for draft metadata. Do not rely on status to hide a mission; set `learner_visible: false`.

## Runtime and Edit Metadata

| Field | Meaning | Current consumer |
| --- | --- | --- |
| `write_mode` | Required mission classification: `read_inspect` or `allow_agent_edits` | Framework validators and catalog metadata |
| `capability_mode` | Required workflow classification: `guided_tutor`, `agent_build`, or `review_only` | Framework validators and catalog metadata |
| `allow_agent_edits` | Optional runtime permission; defaults to `false` | `prepareWorkspace` and the learner tutor |

## Learning Outcomes

Learning outcomes are optional in the contract, but recommended for authored missions. Write them as observable learner capabilities.

```yaml
learning_outcomes:
  - id: lo01
    description: "Inspect workspace signal data before building a model."
  - id: lo02
    description: "Configure a root inport to use workspace data."
```

Tasks can refer back to these outcomes with `outcome_refs`.

## Setup

Use setup when learners need prepared data, models, or workspace state before task 1.

```yaml
setup:
  script: "setup_inspect_and_filter_a_signal.m"
  description: >
    Creates sample signal data and leaves signalData in the MATLAB workspace.
```

Setup scripts should leave only learner-needed state visible. If a learner can start from their current environment, omit the setup block.

## Discovery

Use discovery when the tutor needs to learn something from the learner's environment before later checks can work. A common case is the model name, because learners may create a model with their own name.

```yaml
discovery:
  model_name:
    tool: evaluate_matlab_code
    code: "bdroot"
    note: "Store the current model name for later model_read checks."
```

Discovery should use real MCP tool names listed in the mission contract.

## Tasks

Tasks are the heart of a mission. Each task has an ID, title, instruction, completion block, and hints.

```yaml
tasks:
  - id: "t01"
    title: "Plot the input data"
    involves: [command, output_interpretation]
    outcome_refs: [lo01]
    instruction: >
      Plot the workspace variable signalData and inspect its shape before
      building the model.
    completion:
      strategy:
        - tool: evaluate_matlab_code
          check: "A figure is open with plotted signal data."
      description: >
        The learner has plotted the input data in a MATLAB figure.
    hints:
      - "Start by checking which variables are in the workspace."
      - "A timeseries keeps measurements and time together, which helps you choose a useful view."
      - "The `plot` function helps you visualize data."
```

Good task instructions tell learners what to do and why it matters without revealing the procedure. Do not include runnable commands, UI click paths, library paths, wiring recipes, or completed answers. An exact value can appear when the value itself is an explicit learner-facing requirement rather than hidden implementation guidance.

## Completion Checks

Completion checks are tool-facing descriptions of the finished state. They should be semantic and observable.

Prefer:

```yaml
check: "model contains a Scope block connected to the Inport output"
```

Avoid checks that depend on incidental wording or brittle formatting unless the exact text is the learner-facing goal.

For subjective choices or final reflections that should stay in chat instead of
becoming required files, use `kind: learner_confirmation`:

```yaml
completion:
  strategy:
    - kind: learner_confirmation
      check: >
        The learner has chosen one safe example and explained why it fits the
        rest of the mission.
```

## Hints

Hints are one to three ordered strings. Ada shows one eligible authored hint at a time and skips hints that the learner's current work has already addressed. Build a useful disclosure ladder: start with directional help, become specific, and make the final hint direct enough to act on. Later hints may include accurate commands, UI paths, exact values, library paths, or wiring steps.

```yaml
hints:
  - "Think about where a signal crosses from the workspace into a model."
  - "Use a root-level Inport block to create the model boundary."
  - "In the Library Browser, add Simulink > Sources > In1 at the root of the model."
```

Ada silently captures a task-relevant product-state baseline when presenting each task. Before inspection shows a relevant change or partial result, Ada responds to answer requests with one eligible authored hint at a time; direct or repeated requests, anger, and exhausted hints do not bypass this effort gate. After observable effort, Ada can use product knowledge to provide a complete recipe when prior guidance was attempted, remaining hints do not address the blocker, or applicable hints are exhausted, while leaving the learner to perform the work. Baselines and attempt observations remain session-only and do not change mission YAML, `hintCounts`, or progress.

Completion checks should follow the learner-facing instruction. Require every authored task and observable outcome, but accept behaviorally equivalent implementations unless the instruction explicitly requires a particular structure. Checks should inspect current state before rejecting work, including after a learner disputes an assessment.

## Possible Future Structured Guidance

The current schema intentionally keeps hints as one to three ordered strings. A future backward-compatible schema could make disclosure levels explicit:

```yaml
hints:
  - level: conceptual
    text: <explain the idea or invite observation>
  - level: directional
    text: <identify the relevant capability or area>
  - level: procedural
    text: <name the exact control, object, or operation>
  - level: solution
    text: <optional complete recipe>
```

Future design work should decide whether structured hints allow one to four entries, whether `solution` is optional when Ada can generate a recipe, how legacy strings map to levels, whether tutoring states should be persisted, how rescue transitions work, whether `hintCounts` is sufficient, and how long bundled-mission compatibility lasts. This schema is not currently supported.

## involves and outcome_refs

`involves` helps the tutor frame guidance. Current examples include `command`, `configuration`, `file_edit`, and `output_interpretation`.

`outcome_refs` maps a task to the learning outcomes it practices or demonstrates. These mappings help authors and reviewers check whether the task sequence supports the mission goal.
