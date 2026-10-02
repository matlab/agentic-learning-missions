# Interactive Missions

This repository is the development workspace for the Interactive Missions
MATLAB toolbox. It packages learner missions, a learner-facing tutor skill, a
MATLAB Apps Gallery launcher, authoring skills, and smoke tests.

## Default behavior

- Use `create-tutor-mission` when the user wants to create or revise a mission.
- Use `qa-mission` when the user wants to review mission quality.
- Use `maintain-missions` when the user wants framework cleanup, packaging
  checks, docs maintenance, or smoke-test updates.
- If the user wants to run a learner mission from this checkout, use
  `interactiveMissions.prepareWorkspace` to create a safe workspace bundle and
  invoke the copied `mission-tutoring` skill from that workspace.

## Workspace architecture

- `src/` - MATLAB toolbox APIs, the Apps Gallery app entry point, internal helpers, learner Help documentation under `src/doc/`, and `src/app/` UIHTML assets (`index.html`, `app.js`, `styles.css`).
- `marketplace/missions/` - packaged learner mission folders with `mission.yaml`,
  setup scripts, reset scripts, thumbnails, and mission-owned content.
- `src/skills/mission-tutoring/` - packaged learner tutor skill. Gets copied into prepared learner workspaces.
- `src/author-skills/` - source authoring skills shipped with the toolbox. Authors can copy these into separate agentic projects using `startMissionAuthoring`
- `docs/` - global author and maintainer documentation.
- `src/author-skills/references/` - shared author-skill contracts for missions, progress, and platform qualification.
- `tests/` - MATLAB and Python framework validators plus runtime smoke tests.
- `buildfile.m` - build tool entry point and toolbox packaging implementation. Use `buildtool package` to build `InteractiveMissions.mltbx`.
- `build/` and `progress/` - generated local output ignored by Git.

## Skills

- `mission-tutoring` - learner-facing mission tutor packaged at `src/skills/mission-tutoring`.
- `create-tutor-mission` - authoring skill for creating or revising mission
  YAML and optional setup/reset scripts.
- `qa-mission` - authoring skill for mission quality review.
- `maintain-missions` - maintainer skill for layout, packaging, docs, and smoke
  test upkeep.

`src/author-skills/` is the source of truth for author-facing skills. Optional agent-specific adapters live under each skill's `agents/` folder.

## Rules

- Do not soft-wrap Markdown files. Keep each paragraph and list item on one line unless a line break is meaningful to the rendered content.
- Do not expose author-only skills inside `src/skills`.
- Treat `docs/agent-support-matrix.json` as the release source of truth for
  supported client adapters.
- Regular-mode learner progress lives under the active learner workspace at
  `.interactive-missions/progress.json`. Practice mode starts without progress,
  but the learner may explicitly ask Ada to save progress and make that
  workspace resumable. Do not permanently mutate unrelated learner progress files.
- Mission content belongs under `marketplace/missions/<mission-name>/mission.yaml`.
- App web assets belong under `src/app`, not under mission content.
- During learner tutoring, treat learner models and workspaces as read-only
  unless the user explicitly switches to mission authoring, QA, or debugging
  work where edits are requested.
- For MATLAB and Simulink work, prefer MATLAB MCP Server and agentic toolkit
  introspection before guessing APIs, block names, model paths, or parameter
  names.
- Do not run shell MATLAB commands such as `matlab --batch`, `matlab -batch`,
  or `matlab.exe -batch`. Use MATLAB MCP tools instead.
- If MATLAB MCP is unavailable, stop and alert the user instead of trying a
  shell MATLAB fallback automatically.

## Validation

After framework, documentation, skill-text, packaging, setup/reset, or progress
lifecycle changes, validate before review using this order:

1. Verify MATLAB MCP Server connectivity with the MATLAB MCP handshake only if
   the current agent session has not already confirmed MCP connectivity:
   `disp("MATLAB MCP handshake: interactive-missions")`.
2. Run `tests/validate_framework.m` through the MATLAB MCP Server as the primary framework validation path.
3. For setup, reset, workspace provisioning, or progress lifecycle changes, run `tests/validate_runtime.m` through the MATLAB MCP Server. The default call is infrastructure-only; use explicit mission scope when setup or reset behavior must be executed.
4. If a change modifies either framework validator, `tests/validate_framework.m` or `tests/validate_framework.py`, run both framework validators: the MATLAB MCP validator and `python tests\validate_framework.py`.
5. If MATLAB MCP is unavailable, stop and alert the user so they can choose to start or restart the MCP server, or proceed with `python tests\validate_framework.py` when static validation is enough.

If a smoke test encodes required phrases or structure, update the validator in
the same change.

After every validation command or test run, return the active working directory to the repository root before running further commands or completing the task.
