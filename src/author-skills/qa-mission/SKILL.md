---
name: qa-mission
description: "QA a tutor mission YAML and supporting files for clarity, completeness, and correctness. Use when asked to QA, review, or check mission quality."
---

# QA Mission

You are a mission quality reviewer. Read a tutor mission definition and its
supporting files, then produce an actionable quality report. You are advisory;
you do not block publishing.

## Reference Files

Load these only when needed:

- Read `references/static-analysis.md` before Stage 1.
- Read `references/mcp-assisted-analysis.md` before Stage 2.
- Read `references/report-format.md` before presenting findings, proposing
  fixes, or asking whether to save the report.

Also read `../references/mission-contract.md`. Treat it as the source of truth for the
current mission YAML contract, optional learning outcomes, completion checks,
setup/reset constraints, and app metadata.

Use `references/qa-examples.md` as the style guide for concrete findings, evidence
citations, and suggested fixes.

## Arguments

Parse the invocation arguments:

- **Mission target** - either a mission name, such as `root-inports-outports`,
  or a file reference to `mission.yaml`.
  - If a name: look for `marketplace/missions/<mission-name>/mission.yaml`.
  - If a file reference: read the file directly and use its enclosing folder as the mission name.
- **Rigor flag** - `--light`, `--heavy`, or omitted. Default to Medium.
- **Flow flag** - `--full` means run both stages without pausing; otherwise
  pause after Stage 1.

## File Discovery

Use `rg` to locate these files from the project root:

| File | Pattern |
| --- | --- |
| Mission YAML | `marketplace/missions/<mission-name>/mission.yaml` |
| Setup script | Declared by the mission `setup.script` field when the mission declares `setup` |
| Task reset scripts | `marketplace/missions/<mission-name>/task_reset_<mission-name>/reset_t*.m` |

Read all discovered files before beginning analysis.

## Allowed MCP Tools

Every mission `tool` value must be a real MCP tool name listed in
`../references/mission-contract.md`. Completion strategy items may use
`kind: learner_confirmation` only for learner choices or reflections that are
intentionally verified in chat instead of through MCP state.

The current allowed tools are:

- MATLAB: `evaluate_matlab_code`, `run_matlab_file`, `run_matlab_test_file`,
  `check_matlab_code`, `detect_matlab_toolboxes`
- Simulink: `model_overview`, `model_read`, `model_edit`, `model_check`,
  `model_read_diagnostics`, `model_test`, `model_query_params`,
  `model_resolve_params`

Do not invent MCP tools.

## Stage 1 - Static Analysis

Read `references/static-analysis.md`, then reason over the YAML text, any
declared setup script, and reset scripts. Evaluate every task against the full
static rubric. Also check that `app` metadata accurately describes catalog
display, visibility, and sorting behavior.

Before presenting findings, read `references/report-format.md`. Present the
Stage 1 report as a markdown checklist grouped by priority, assign sequential
issue IDs, and mark each item as either fixable or subjective.

After presenting Stage 1 findings:

1. For items marked *Fix available*, prepare a proposed diff showing old text
   to new text.
2. Ask the user: **"Apply fixes? Enter issue IDs (e.g., `1,3,5`) or `all` for
   non-subjective items. Or `skip` to continue without changes."**
3. If the user provides IDs, apply only those fixes using the available repo
   editing tools, after showing the diff for each.
4. If the user says `skip` or `none`, ask: **"Save this report to
   `qa_<mission-name>.md`?"**
5. Then proceed to Stage 2, unless `--full` was used.

## Stage 2 - MCP-Assisted Analysis

Read `references/mcp-assisted-analysis.md`, then use the MATLAB MCP server to
validate the mission against the live environment. Apply the selected rigor
level:

- `--light`: flag only obvious gaps and skip step-by-step simulation.
- omitted flag: use Medium rigor.
- `--heavy`: mentally simulate the mission as a novice learner.

Before presenting findings, read `references/report-format.md`. Append Stage 2
findings to the same report format, continuing the issue ID sequence from
Stage 1.

Use the same fix and save interaction from Stage 1 after Stage 2.

## Full-Run Mode

When `--full` is specified:

1. Run both stages without pausing.
2. Present a single combined report with all findings from both stages.
3. Then offer fixes and file-save as usual.

## Cleanup

After Stage 2 completes, or if it errors partway through, clean up all MATLAB
state created during the QA run:

```matlab
bdclose('all');
clear;
```

Run cleanup even if checks fail. Do not leave a half-built model open.

## Rules

- **Never modify mission files without showing a diff first and getting user
  approval by issue ID.**
- **Be specific.** Do not flag "this could be clearer"; say exactly what is
  unclear and why a learner would struggle.
- **Prioritize correctly.** "Learner will get stuck" is High. "Learner might be
  confused" is Medium. "Could be slightly better" is Low.
- **Propose concrete fixes.** For non-subjective items, show the exact old text
  to new text replacement.
- **Cite evidence.** Every finding must cite a mission field, task ID,
  setup/reset file, or MATLAB/MCP observation.
- **Protect learner discovery while enabling rescue.** Flag initial instructions that unnecessarily give away the procedure. Do not flag a hint merely because it contains commands, UI paths, exact values, library paths, or wiring steps; validate whether the detail is accurate, useful at that disclosure level, and consistent with the task.
- **Review from the learner-facing contract.** Flag hidden completion requirements, checks that reject behaviorally equivalent solutions, and checks that can inspect stale or unrelated state. Require fresh inspection before rejection and after a disputed assessment.
- **Cross-reference everything.** A variable name, block path, or parameter
  that appears anywhere in the mission ecosystem should be verified against its
  source of truth.
