# Skill Usage

The three author-facing skills support different parts of the mission lifecycle. You do not need to know every internal rule before using them. Give the skill clear intent, review its output, and ask it to revise when the mission does not match your design.

## create-tutor-mission

Use `create-tutor-mission` to create a new mission YAML file and optional setup script. If you are creating your first mission, start authoring with `startMissionAuthoring()` in an empty folder. It creates the marketplace layout, copies the author skills and documentation, configures the selected client, and can optionally create a first-mission brief. Write each published definition as `marketplace/missions/<mission-name>/mission.yaml`.

Best practices:

- State the learning goal in observable terms.
- Describe the learner audience and assumed MATLAB&reg; or Simulink&reg; experience.
- Provide a domain context when it helps the activity feel realistic.
- Say whether learners should start from an empty environment, prepared data, an existing model, or a partially completed model.
- Provide task text when wording matters.
- Tell the skill whether to preserve your wording verbatim or adapt it.
- For tasks that depend on simulation, figures, Simulation Data Inspector, or configuration state, identify how current learner work can be verified.

Useful prompt pattern:

```text
Use create-tutor-mission to create a mission about [concept]. Learners should
be able to [observable outcome]. They start from [starting state]. The mission
should use [domain context]. I want roughly [number] tasks.
```

The skill can work from a rough idea, a task sketch, or polished instruction text. More detail gives you more control; less detail gives the skill more room to propose a first draft.
## qa-mission

Use `qa-mission` to review a mission after it has been drafted. It checks both structure and instructional quality.

Best practices:

- Run QA before treating a mission as ready for learners.
- Share the instructional goal if it is not obvious from the YAML.
- Ask for heavier review when the mission has setup scripts, reset scripts, or complex Simulink behavior.
- Ask QA to review evidence ownership and freshness for tasks that depend on simulation, figures, Simulation Data Inspector, or configuration state.
- Review subjective findings as design prompts rather than automatic failures.
- Apply mechanical fixes only after checking that they preserve the intended learner experience.

Useful prompt pattern:

```text
Use qa-mission on continuous-and-discrete-time. Check YAML structure, setup consistency,
completion criteria, hints, and alignment with the learning outcomes.
```

`qa-mission` can use static review and MATLAB-assisted review. Static review checks the mission files directly. MATLAB-assisted review uses the live environment when behavior needs to be observed. It can review packaged missions, an authoring-workspace draft referenced by path, or a direct mission YAML file.

## maintain-missions

Use `maintain-missions` when you are maintaining the mission framework or a set of packaged missions.

Best practices:

- Run it after changing mission contracts, skill guidance, validators, or packaging structure.
- Use it when allowed MCP tool names change.
- Use it before release or review when several missions changed.
- Preserve focused correct, incorrect, and unverified inspection evidence after changing high-risk completion checks.
- Keep maintenance separate from instructional redesign unless you explicitly want both.

Useful prompt pattern:

```text
Use maintain-missions to validate the framework after these mission updates.
Check packaging, author-skill guidance, mission contracts, and smoke tests.
```

Maintenance should usually include validation. If either framework validator is changed, run both `tests/validate_framework.m` through MATLAB MCP and `python tests\validate_framework.py`.

## Evaluation skills

Use `evaluate-tutor-skill` to test a selected tutor version against controlled cases and optional live MATLAB checks. Use `simulate-mission-learner` to prepare mission evaluation specifications or run expert, casual, and naive learner simulations. The two evaluators run independently; neither requires the other to pass.

```text
Use evaluate-tutor-skill on this tutor snapshot. Run the behavior cases and report readiness and limitations.
Use simulate-mission-learner to prepare a draft evaluation specification for this mission for my review.
Use simulate-mission-learner to run a one-task expert diagnostic using the existing specification. Keep its results provisional.
```

Both skills are copied by `startMissionAuthoring`, along with their runner, cases, and references. Their `SKILL.md` links to the shared evaluation README with exact commands. In prepared workspaces it lives at `.interactive-missions/authoring/skills/references/evaluation/README.md`; native Codex copies also include it under `.codex/skills/references/evaluation`. In the development checkout, use `src/author-skills/references/evaluation/README.md`. Supply the tutor snapshot and installed toolbox location explicitly; authoring setup does not copy the learner tutor.

Reuse the pinned `build/evaluation-venv` environment. Evaluation runs use Codex SDK/CLI and MATLAB MCP for live product work, even when another authoring client invokes a wrapper. The pilot runtime is qualified only for the documented Windows/Python/MATLAB versions and stock observers; supported authoring adapters do not expand that claim.

Ask for both evaluations when studying coupled tutor/mission changes. The optional `combined` command can run both serially or compose saved runs without new agent calls. It preserves each component report, readiness, and evidence rather than producing one quality score. Changed snapshots or runtime versions remain distinct; use compatible component runs for baseline comparisons.

Reports distinguish evaluator mistakes, tutor behavior, mission defects, and infrastructure failures. Findings do not authorize automatic edits. Reviewed unknowns may be completed author decisions, and historical independent outcomes remain separate from later author adjudications. Reviewed-label agreement does not establish accuracy on unseen traces; preserve provisional flags.
