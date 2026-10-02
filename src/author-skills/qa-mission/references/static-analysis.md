# Static Analysis Reference

Use this reference during Stage 1 after reading the mission YAML, any declared
setup script, reset scripts, `../references/mission-contract.md`, and `references/qa-examples.md`.

Reason over the YAML text, supporting scripts, and reset scripts. Evaluate each
task against these categories.

## Clarity

Flag instructions that are ambiguous, use unclear referents such as "it",
"that", or "the thing", or introduce jargon without context. A learner reading
the instruction cold should understand what they need to accomplish.

## Opening Organizer Fit

The tutor derives a short opening background and one prediction question from the mission title, objective, and optionally Task 1 instruction. Ada includes explicit prerequisite or assumed-prior-knowledge statements from the title or objective in that opening. Flag an objective when it is too vague to provide context, intended outcome, and any stated prerequisite; is solution-oriented; or depends on hints, completion checks, commands, parameter values, mechanical steps, or other hidden fields to make the opening meaningful.

## Completeness

This is the most critical check. For each task instruction, ask: "If a learner
does exactly and only what this instruction says, will they reach the completion
state?"

Flag when:

- Completion criteria depend on a hidden arbitrary value or procedure that the learner cannot derive from prior work, visible starting state, or a safe hint.
- A configuration has multiple required parts but the task gives no conceptual route for the learner to discover them.
- The completion criteria require state that cannot be inferred from the task goal, prior work, or visible starting state.

## Instructional Fit

Check whether the instruction states one clear goal and purpose without unnecessarily revealing the procedure or answer. Learners should begin from the goal and use the ordered YAML hint ladder when they need increasingly direct help.

Flag when:

- Instructions bury a simple task under excessive theory or unrelated
  explanation.
- Initial instructions include unnecessary runnable commands, UI click paths, library paths, wiring recipes, or completed solutions.
- Instructions provide multiple competing solution workflows.
- Procedural details contradict the hints or completion criteria.

## Variable And Name Consistency

Cross-reference names that appear in:

- Task instructions and hints, such as "the respiratoryData variable".
- Completion strategy checks, such as
  `get_param(mdl,'ExternalInput') should reference respiratoryData`.
- The setup script's output, when present, including variables and state that
  remain after `clear` at the end.
- Reset scripts, especially model or block names they hardcode.

Flag mismatches, including a YAML reference to a name that does not exist in the
setup script output or a reset script that assumes a model name the learner
might not use.

## Task Ordering And Dependencies

For each task, verify that everything it references was created or configured in
a prior task.

Flag:

- A task that reads state only produced by a later task.
- A task whose completion criteria depend on something no prior task
  established.
- Circular dependencies.

## Hint Quality

Each task should have 1-3 ordered, useful hints that increase disclosure from directional to specific to direct. Later hints may include commands, UI paths, exact values, library paths, wiring steps, or a complete recipe.

Flag when:

- Hints are duplicated or do not add useful support beyond the instruction.
- The available hints do not help a stuck learner complete the task.
- A hint contradicts the task instruction.
- A hint gives a workaround that would not satisfy the completion criteria.
- A hint is more revealing than its ladder position warrants.
- A procedural detail is incorrect, misleading, inconsistent with the instruction, or does not satisfy the completion criteria.

## Completion Criteria Validity

Check that:

- Every `tool` value is a real MCP tool name listed in
  `../references/mission-contract.md`, and every non-tool `kind` value is supported by
  the mission contract.
- The `check` description is semantically meaningful, not a brittle string
  match.
- The check would not already pass before the learner does the task.
- The check is achievable given what the instruction asks the learner to do.
- The check accepts behaviorally equivalent implementations whenever the instruction is outcome-oriented.
- The check inspects current task state rather than stale workspace results, an incidental active figure, or a previous simulation.

## Agent Edit Permission Fit

Check `allow_agent_edits` against the mission tasks:

- If omitted or `false`, flag tasks that require the tutor or agent to create,
  modify, or regenerate learner artifacts as written.
- If `true`, verify the tasks make the learner's agentic-editing role explicit
  and that edits are scoped to learner-owned workspace artifacts.
- Always preserve protection for copied mission content, setup/reset scripts,
  manifests, installed mission files, and progress files except normal progress
  updates.

## App Metadata

Check that:

- The mission has an `app` block with summary, audience, difficulty,
  estimated minutes, products, topics, status, learner visibility, and tile
  order.
- `summary` is short enough for a mission tile and does not duplicate the full
  description.
- `audience`, `difficulty`, and `estimated_minutes` set realistic learner
  expectations.
- `products` and `topics` are useful descriptive metadata; the app does not currently filter or gate on them.
- `learner_visible` controls learner-catalog inclusion, while `status` is display metadata only.

## Learning Outcome Alignment

If `learning_outcomes` is present:

- Each outcome has a stable `loNN` ID and an observable capability statement.
- Each `outcome_refs` value on a task matches a declared outcome ID.
- Each declared outcome is referenced by at least one task.
- Outcome coverage matches the mission description and task sequence.
- Any outcome that says the learner can "articulate" or "explain" something is
  explicitly practiced or checked by a task. Otherwise, recommend rephrasing the
  outcome as an observable building, configuration, comparison, or
  interpretation capability.

If no learning outcomes are present, report that as a Low priority advisory
finding unless the mission claims to validate outcomes.
