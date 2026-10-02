---
name: maintain-missions
description: Maintain the Interactive Missions framework layout, packaging metadata, docs, and smoke tests. Use for cleanup, refactors, and release-readiness checks.
---

# Maintain Missions

You maintain the author-facing Interactive Missions framework and MATLAB
toolbox packaging.

## Scope

Use this skill when the user asks to clean up, refactor, validate, package, or
prepare the framework for review. Do not use it to run learner tutoring sessions;
those belong to the packaged `mission-tutoring` learner skill.

## Repository Boundaries

- `src/author-skills/` contains the author-facing source skills and their
  skill-specific adapters, such as `agents/openai.yaml`.
- `src/skills/mission-tutoring/` contains the learner tutor skill.
- `marketplace/missions/` contains packaged mission fixtures.
- `src/` contains MATLAB toolbox APIs and the Apps Gallery app entry point.
- `docs/` contains author-facing guidance, with `docs/1-index.md` as the
  entrypoint for the human docs.
- `../references/` contains shared mission, platform, and progress contracts for
  authoring agents.
- `tests/` contains framework and runtime validators for this repo.
- Regular learner progress lives inside the active learner workspace at
  `.interactive-missions/progress.json`, outside packaged repository content,
  and must not be committed.

## Maintenance Checklist

1. Confirm author-only skills are not exposed inside `src/skills`.
2. Confirm toolbox packaging metadata includes the Apps Gallery entry and
   required dependencies.
3. Confirm README describes MATLAB toolbox installation, safe workspaces,
   progress storage, and packaged content ownership.
4. Confirm mission YAML uses the current lightweight contract and references
   existing setup/reset scripts.
5. Confirm mission YAML includes required app metadata and that
   every manifest mission entry resolves to one published package.
6. Confirm setup/reset scripts avoid obvious destructive operations, directory
   changes, and progress-file writes.
7. Prefer MATLAB MCP Server and agentic toolkit validation. Use this order:
   run the MATLAB MCP handshake with `evaluate_matlab_code` only if the current
   agent session has not already confirmed MCP connectivity:

   ```matlab
   disp("MATLAB MCP handshake: interactive-missions")
   ```

8. Run `tests/validate_framework.m` with the MATLAB MCP Server's
   file-execution tool as the primary validation path.
9. If setup, reset, or learner progress lifecycle behavior changed, run
   `tests/validate_runtime.m` with the MATLAB MCP Server. The
   default call is infrastructure-only; use explicit mission scope when setup or
   reset behavior must be executed.
10. If a change modifies either framework validator,
   `tests/validate_framework.m` or
   `tests/validate_framework.py`, run both framework validators:
   the MATLAB MCP validator and
   `python tests\validate_framework.py`.
11. If MATLAB MCP is unavailable, stop and alert the user so they can choose to
   start or restart the MCP server, or proceed with the Python fallback when
   static validation is enough:

   ```powershell
   python tests\validate_framework.py
   ```
12. Do not run shell MATLAB commands such as `matlab --batch`, `matlab -batch`,
   or `matlab.exe -batch` unless MATLAB MCP connectivity has already been
   confirmed in the current agent session.
13. If a MATLAB MCP tool call reports "no matlab mcp server available" or an
   equivalent MCP-unavailable error, stop and alert the user instead of trying a
   shell MATLAB fallback automatically.
14. Treat docs and skill text as part of the smoke-test contract. When changing
   wording or structure referenced by `tests/validate_framework.m`
   or `tests/validate_framework.py`, update those validators in the
   same change.
15. Review `git status --short` and make sure no learner progress files are
   tracked or staged.

When maintenance work touches mission packages, adapter support, or progress
lifecycle, read the relevant shared contract first:

- `../references/mission-contract.md` for mission package or YAML work.
- `../references/platform-qualification.md` for adapter or client support work.
- `../references/progress-contract.md` for progress lifecycle work.

## MCP Tool Contract Audit

When the user asks to audit, refresh, or update allowed MCP tools:

1. Review upstream toolkit sources first:
   - `matlab/matlab-agentic-toolkit`
   - `matlab/simulink-agentic-toolkit`
2. Compare the upstream MATLAB MCP Server tool names with:
   - `../references/mission-contract.md`
   - `tests/validate_framework.m`
   - `tests/validate_framework.py`
   - `src/author-skills/create-tutor-mission/SKILL.md`
   - `src/author-skills/qa-mission/SKILL.md`
3. Propose contract, authoring guidance, QA guidance, and validator updates when
   upstream tools are added, renamed, or removed.
4. If network access is unavailable, record that upstream verification could not
   be completed and fall back to local MCP/tool metadata from the installed
   environment.
5. Run both framework validators after any allowed-tool list change.

## Deferred Work

Keep deferred product work out of maintenance refactors unless the user approves
it explicitly. Deferred work includes feedback surfaces, generated reset states,
formal schema tooling, rich instructional-design validation, logging
productization, and MATLAB-backed integration tests.
