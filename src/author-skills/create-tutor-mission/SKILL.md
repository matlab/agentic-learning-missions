---
name: create-tutor-mission
description: Scaffold a new tutor mission YAML file, with an optional setup script, for the mission-tutoring skill. Use when creating a new hands-on lesson, designing a tutorial mission, or adding a mission to the tutor framework. Trigger on phrases like "new mission", "create a lesson", "add a filtering mission", or "scaffold a tutorial".
---

# Create Tutor Mission

Scaffold `marketplace/missions/<mission-name>/mission.yaml` for the learner-facing
`mission-tutoring` skill packaged by the MATLAB toolbox. The enclosing folder's
lowercase slug is the stable mission identity. If the mission needs prepared
workspace data, models, or other starting state, also scaffold a descriptive
setup script and reference it from the mission YAML.

Before drafting mission files, read `../references/mission-contract.md`. Treat that
document as the source of truth for required fields, optional learning outcomes,
completion checks, and reset/setup constraints.

If the selected mission folder contains `mission-brief.md`, read it before
intake. Preserve its mission title and folder ID unless the user explicitly
changes them. Use the brief as starting context, then gather the remaining
mission requirements before writing `mission.yaml`.

## Reference Files

Load these only when needed:

- Read `references/mission-yaml.md` before drafting completion checks, learning
  outcomes, `discovery`, or mission YAML.
- Read `references/setup-scripts.md` only when the mission needs setup code.

Keep repository-packaged mission content under `marketplace/missions`. Keep
draft or experimental mission content in an authoring workspace until it is
ready to publish into a marketplace.

## Step 1 - Optional Task Text Intake

Before presenting the general intake questions, ask whether the user wants to
supply draft task instructions, with or without hints.

If the user says no, continue to Step 2 with the current workflow.

If the user says yes, ask for the general intake information from Step 2 and the
instruction and hint text in the same prompt. Tell the user they can provide
task text as Markdown, YAML, or plain text, and that it can be specific
learner-facing instructions or a high-level task sequence.

Use this Markdown example:

```markdown
# Task 1

## Instruction

Add instruction paragraph here

## Hints

1. Numbered list
2. Of Hints
3. Follow
```

Hints are optional in user-supplied task text. If the user provides
instructions without hints, accept the instructions and derive 1-3 useful hints
for each task from the instruction text, mission goals, task sequence, and the
mission design rules below.

Classify supplied task text before drafting:

- **Specific task text** includes complete learner-facing instructions, concrete UI steps, commands, block names, parameter values, or explicit hints. Keep initial instructions focused on the goal and purpose. Move useful procedural material into the later positions of the hint ladder instead of categorically removing it.
- **High-level task text** includes rough task titles, conceptual bullets,
  sequencing ideas, or incomplete draft notes. Tell the user the tasks will be
  modified to fit the mission style.
- **Mixed task text** should be handled pragmatically: treat specific sections
  as draft wording and high-level sections as task intent.
- **Instruction-only task text** should be accepted. Generate hints that support
  the task without contradicting or duplicating the instruction.

Preserve exact wording only when the user chooses verbatim. Otherwise, preserve
the user's intent and sequencing while adapting instructions and hints to the
Mission 02-style guidance below.

## Step 2 - Gather Requirements

Ask the user:

1. **Concept to teach** - What Simulink/MATLAB workflow or feature? For
   example: root inports/outports, bus signals, data stores, model referencing.
2. **Domain/backstory** - What real-world context should frame the data? For
   example: medical device, automotive, aerospace, audio processing.
3. **Mission name** - What lowercase slug should be used for the mission folder?
   Derive a descriptive slug from the title when the user does not provide one.
4. **Learning outcomes** - What 2-5 observable capabilities should the learner
   demonstrate by the end?
5. **Setup needs** - Does the mission need setup code, or can task 1 start from
   the learner's current environment?
6. **Agent edit permissions** - Should the tutor remain read-only, or should
   the mission set `allow_agent_edits: true` because learners must ask an
   agentic client to generate or revise workspace artifacts?
7. **App catalog metadata** - Summary, audience, difficulty, estimated minutes,
   products, topics, status, learner visibility, and tile order.

Do not proceed until you have clear answers to all seven.

## Step 3 - Design The Task Sequence

Default to the short, direct tutorial-lab style used by Mission 02. Create 4-6
sequential tasks unless the concept genuinely needs more steps. If the user
provides more or fewer tasks, allow that.

Use this flexible arc:

| Position | Purpose | Pattern |
| --- | --- | --- |
| First | Create or inspect the initial artifact | Start from current state or prepared setup, then get something visible |
| Early | Configure one key behavior | Set the parameter, source, data, or mode that defines the concept |
| Middle | Add the core mechanism | Insert the block, code, connection, or workflow step being taught |
| Late | Compare, run, or observe | Produce visible evidence that the concept worked |
| Optional last | Interpret or inspect supporting state | Summarize, compare, enable overlays, or inspect logged output |

Guidelines:

- Each task is one learnable action, completable in 2-10 minutes.
- Write the objective with enough context and intended outcome for Ada to give a short opening background and ask one meaningful prediction before Task 1, without consulting hints or completion criteria. State explicit prerequisites or assumed prior knowledge clearly in the objective, because Ada includes that information in the opening summary.
- Instructions should give the learner a clear action and purpose without prescribing the procedure. Do not include runnable commands, click paths, library paths, wiring recipes, or a completed answer. Include an exact value only when the value itself is an explicit learner-facing requirement rather than hidden implementation guidance.
- Keep instruction text concise. Avoid long theory explanations and multiple
  alternate workflows in the instruction.
- Hints are an ordered 1-3 item ladder that increases disclosure. Start with directional guidance, make the next hint specific, and make the final hint direct enough to act on.
- Later hints may include technically accurate commands, click paths, exact values, block or library paths, wiring steps, or a complete recipe. Keep earlier hints useful, and do not reveal more than their position in the ladder warrants.
- Prefer early visual feedback: plots, Scopes, logged output, diagrams, or
  inspectable model state.
- `involves` tags must come from `output_interpretation`, `command`,
  `file_edit`, and `configuration`.
- Draft `instruction`, `hints`, `completion.check`, and
  `completion.description` first. Then derive `involves` and `tool` values from
  the actual task content.
- When the user supplies task text, preserve the requested intent and
  sequencing. Preserve exact instruction or hint wording only when the user
  chose verbatim; otherwise adapt the text for clarity, consistency, and mission
  style.
- If the user supplies instructions without hints, derive hints from those
  instructions and the mission rules. Do not ask the user to provide hints just
  to proceed.

## Step 4 - Map Completion Checks

Read `references/mission-yaml.md` before writing completion checks or YAML. Use
`../references/mission-contract.md` as the source of truth for allowed MCP tool names.

The current allowed tools are:

- MATLAB: `evaluate_matlab_code`, `run_matlab_file`, `run_matlab_test_file`,
  `check_matlab_code`, `detect_matlab_toolboxes`
- Simulink: `model_overview`, `model_read`, `model_edit`, `model_check`,
  `model_read_diagnostics`, `model_test`, `model_query_params`,
  `model_resolve_params`

Do not invent MCP tools. Choose completion strategies from the allowed list and
write semantic checks that the tutor can interpret instead of brittle string
matches.

## Step 5 - Write The Mission YAML

Use `references/mission-yaml.md` for the mission template, learning outcome
rules, completion block format, and YAML verification checklist.

Write the full YAML to the selected mission content root as
`mission.yaml`. Use `marketplace/missions/<mission-name>/mission.yaml` for
marketplace missions. User-supplied
instructions and optional hints must still be converted into valid mission YAML
with sequential task IDs, completion blocks, `involves`, `outcome_refs`, and
allowed MCP tools. If hints were omitted, generate them before writing the YAML.

Include the `setup` block only when the mission uses a setup script. If no setup
script is needed, omit `setup` and make task 1 explicit about the learner's
manual starting condition.

Include the required `app` block. For normal learner
missions use `status: published` and `learner_visible: true`. For UI validation
missions use `status: demo` only when the user explicitly wants learners to see
the demo tile.

Include `allow_agent_edits: true` only when the learner-facing tasks explicitly
teach agentic artifact generation or tool-assisted editing. Otherwise omit the
field or set it to `false` so the tutor stays read-only.

When creating the first mission in an initialized authoring workspace, add its
folder and `mission.yaml` path to `marketplace/manifest.yaml`. The initializer
leaves `source_url` as a TODO; the author must set it before publishing or
registering the marketplace.

Only `mission.yaml`, the declared setup script, an explicitly declared thumbnail, and the
`task_reset_<mission-name>` directory are copied into learner workspaces. Do not
depend on undeclared helpers or arbitrary mission-folder assets at runtime. Omit
`thumbnail` to use the app-rendered generic fallback.

## Step 6 - Write The Setup Script, If Needed

Skip this step when the mission does not need setup code. If setup is needed,
read `references/setup-scripts.md` and follow it before writing
`setup_<mission_name>.m` beside the mission YAML in the selected mission content
root.

The setup process must:

1. Load the `matlab-script-writing` skill for MATLAB coding conventions.
2. Draft and run the code via `evaluate_matlab_code` or `run_matlab_file` to
   validate it.
3. Write the setup script only after successful execution.

Do not skip MCP validation for setup scripts.

## What Not To Do

- **Don't invent MCP tools.** Only reference allowed tools from
  `../references/mission-contract.md` and the compact list above.
- **Don't make checks too rigid.** Use semantic descriptions the tutor
  interprets, not brittle string matching.
- **Don't hide success criteria.** Make the task goal achievable from the instruction, prior learning, supplied starting state, and the ordered hint ladder. Revise a hidden arbitrary completion target; use later hints for accurate procedures when the procedure is useful support.
- **Don't front-load theory.** The learner learns by doing; use short
  task-local explanations tied to the action.
- **Don't skip MCP validation for setup scripts.** If the mission uses setup,
  run the setup script via MCP before writing it to disk.
- **Don't prescribe a model name.** Discover it dynamically after the learner
  creates it.

## Final Validation

After creating the mission files:

1. Run the mission YAML checklist in `references/mission-yaml.md`.
2. If setup exists, run the setup validation in `references/setup-scripts.md`.
3. Confirm all `tool` values are real MCP tool names listed in
   `../references/mission-contract.md`.
4. Confirm user-supplied procedural text was kept out of the initial instruction when it would give away the method, and was preserved or adapted into an appropriate later hint when useful.
5. Confirm required `app` metadata is present and internally consistent.
6. Confirm the objective and Task 1 instruction can support the opening organizer without consulting hints or completion criteria, and that any explicit prerequisite or assumed-prior-knowledge statement in the objective is clear enough for Ada to repeat.
7. Use the `qa-mission` skill for a full QA pass on the new mission.
