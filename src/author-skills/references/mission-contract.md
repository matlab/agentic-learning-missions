# Mission Contract

This document defines the mission package contract for Interactive Missions.

## Marketplace Layout

Packaged missions live under `marketplace/missions`. Each mission has one folder, and the folder name is the stable mission identity.

```text
marketplace/
  manifest.yaml
  missions/
    root-inports-outports/
      mission.yaml
      setup_root_inports_outports.m
      task_reset_root-inports-outports/
```

User-authored missions are published by adding them to a marketplace layout and sharing via Git.

## Required Fields

Each `mission.yaml` requires:

- `version`: mission package version.
- `title`: learner-facing mission title.
- `objective`: short description of what the learner will be able to do. It also supplies Ada's opening background, so include enough context and intended outcome to support a meaningful prediction question without relying on hints or completion checks. Write any explicit prerequisite or assumed-prior-knowledge statement clearly in the objective, because Ada includes it in the opening summary.
- `supported_matlab_releases`: nonempty list of supported releases.
- `required_capabilities`: nonempty list of runtime capabilities.
- `write_mode`: `read_inspect` or `allow_agent_edits`.
- `capability_mode`: `guided_tutor`, `agent_build`, or `review_only`.
- `app`: metadata used by the MATLAB app.
- `tasks`: ordered list of learner tasks.

Optional fields:

- `thumbnail`: optional path relative to the mission folder or marketplace root for an authored PNG or SVG graphic. Omit it, or leave it empty, to use the app-rendered generic fallback.
- `allow_agent_edits`: boolean. Use `true` only for missions that explicitly teach agentic artifact generation or tool-assisted learner artifact editing.
- `setup`: setup script metadata.
- `learning_outcomes`: observable capabilities practiced by the mission.

## Tutor Edit Permissions

`allow_agent_edits` controls whether the learner tutor may create or modify learner-owned artifacts during a mission. The default is `false`; ordinary missions stay read-only, with the tutor observing state and guiding the learner.

| Field | Purpose | Current consumer |
| --- | --- | --- |
| `write_mode` | Required static classification of read-only versus agent-editing work | Validators and catalog |
| `capability_mode` | Required static classification of the tutoring workflow | Validators and catalog |
| `allow_agent_edits` | Runtime permission to edit learner-owned workspace artifacts | Workspace preparation and tutor |

When `allow_agent_edits: true`, edits are allowed only inside the active safe workspace and only when the current task or learner explicitly asks for artifact generation or revision. Copied mission content, setup/reset scripts, tutor skill files, manifests, installed marketplace files, and progress files remain protected except for normal progress updates.

## App Metadata

Every runnable mission must include an `app` block with:

- `summary`
- `audience`
- `difficulty`: `beginner`, `intermediate`, `advanced`, or `unspecified`
- `estimated_minutes`
- `products`
- `topics`
- `status`: `published`, `draft`, `demo`, or `deprecated`
- `learner_visible`
- `tile_order`

`learner_visible` controls inclusion in the learner catalog. `status` is displayed but does not control inclusion. The app does not currently filter or gate missions by audience, products, difficulty, or status.

## Setup And Reset

Setup scripts are optional. If present, `setup.script` must name a file in the mission folder.

Reset scripts for later tasks live under `task_reset_<mission-name>/reset_tNN.m` inside the same mission folder. Setup and reset scripts must not change folders permanently, delete unrelated files, or write learner progress.

`prepareWorkspace` copies `mission.yaml`, the file declared by `setup.script`, an explicitly declared thumbnail, and the complete `task_reset_<mission-name>` directory when present. Omitted or empty thumbnails use the app-rendered generic fallback and do not add a workspace file. It does not copy undeclared helpers or arbitrary mission-folder assets.

## Tasks

Task IDs must be sequential: `t01`, `t02`, and so on.

Required task fields:

- `id`
- `title`
- `instruction`
- `completion`
- `hints`

Optional task fields:

- `involves`
- `outcome_refs`

Task instructions state the learner's goal and why it matters. They must not give the task answer through runnable code, command sequences, UI click paths, library paths, wiring recipes, or a completed model structure. A task may name observable learner state, such as a workspace variable, and may state an exact value when that value is itself an explicit learner-facing requirement rather than hidden implementation guidance.

`hints` is an ordered list of one to three learner-facing strings and is Ada's primary authored task-help source. Hints should increase in disclosure from directional to specific to direct. Later hints may contain technically accurate commands, UI paths, exact values, block or library paths, and wiring steps when those details help the learner act. Ada silently captures task-relevant product state when presenting a task and counts effort only when inspection shows a relevant change or partial result. Before effort, requests for answers or more help receive one eligible authored hint at a time; direct or repeated requests, anger, and hint exhaustion alone do not permit a generated complete recipe. After effort, Ada may provide a recipe when prior guidance was attempted, remaining hints do not address the blocker, or applicable hints are exhausted. The learner still performs the work.

Task-effort baselines and attempt observations are session-only state. They do not change mission YAML, `hintCounts`, or the progress schema. On resume, clearly task-relevant partial work may establish effort; ambiguous state requires a fresh relevant change.

Completion checks should describe semantic evidence and name real MATLAB MCP
tools. They should be specific enough for Ada to verify progress without
brittle implementation guesses. A completion strategy item may use
`kind: learner_confirmation` instead of `tool` only when the finished state is
a learner choice or reflection that should remain in conversation rather than a
required workspace file.

Learner-facing instructions define success. Completion checks must require every authored task and observable outcome, but must accept behaviorally equivalent implementations unless the instruction explicitly requires a particular structure. Ada must inspect current state before every rejection and after a learner disputes an assessment.

## Progress

Regular and resume modes use the manager-supplied workspace-local progress path
at `.interactive-missions/progress.json`. Practice mode starts without
progress, but the learner may explicitly ask Ada to save progress or resume
later. That request promotes the current workspace to a tracked/resumable
session and creates `.interactive-missions/progress.json`.

Progress schema 2.0 fields are:

- `schemaVersion`
- `learnerName`
- `marketplaceSource`
- `missionName`
- `missionId`
- `missionVersion`
- `workspacePath`
- `mode`
- `currentStepId`
- `completedStepIds`
- `hintCounts`
- `updatedAt`
- `notes`

Completion is derived from the mission task IDs and `completedStepIds`; persisted summary fields are display cache only.
