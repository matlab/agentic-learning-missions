# MCP-Assisted Analysis Reference

Use this reference during Stage 2 after static analysis. Validate the mission against the live MATLAB environment through the MATLAB MCP server.

## Setup Script Execution

If the mission declares a setup script, run it via `mcp__matlab__run_matlab_file`:

- If it errors, report the error as a High priority finding.
- If it warns, report it as a Medium priority finding.
- Note any version-specific error messages, such as "Undefined function" that might indicate a toolbox or release mismatch.

If the mission omits `setup`, skip execution and verify that task 1 states the manual starting condition clearly enough for the learner to begin.

## Environment Matches Task 1 Expectations

After running the setup script, when one exists, verify that the state described in t01's instruction actually exists. Read what t01 says the learner should find, then confirm it:

- If t01 references workspace variables, use `evaluate_matlab_code` with `whos` or `exist`.
- If t01 references an open model, check with `find_system('type','block_diagram')`.
- If t01 references a figure or app, check with `get(groot,'Children')` or an equivalent query.
- If t01 references data properties, such as size, type, or sample rate, verify those properties.

Flag any mismatch between what t01 tells the learner is there and what actually exists after setup. For no-setup missions, flag task 1 if it assumes prepared variables, models, figures, or files without telling the learner how those should already exist.

## Library Paths In Hints

Scan all hints for Simulink library paths, such as `simulink/Sources/In1` or `simulink/Sinks/Scope`. For each unique path found, validate it:

```matlab
find_system('simulink', 'SearchDepth', 2, 'Name', '<BlockName>')
```

Flag any path that does not resolve as High priority because the learner will hit an error if they follow the hint.

## Block Parameters In Completion Checks

Scan all completion `check` fields for `get_param` calls or parameter names. For each referenced parameter, verify it exists on the expected block type:

```matlab
params = get_param('<library_block_path>', 'ObjectParameters');
isfield(params, '<param_name>')
```

Flag invalid parameters as High priority.

## Behavioral Equivalence And Fresh State

For each outcome-oriented instruction, test at least one reasonable alternative implementation when practical. Flag a check that accepts an expected block merely by presence while its behavior is incorrect, or rejects a different structure that demonstrably satisfies the instruction.

Review every rejection path for fresh inspection. Figure checks should inspect all candidate figures instead of relying on `gcf`; simulation checks should tie results and SDI runs to the current model and run; model checks should reacquire current structure after learner changes. Re-run inspection after a simulated learner dispute.

## Reset Script Chain

If reset scripts exist for this mission, run them in sequence, such as `reset_t02`, `reset_t03`, and onward, to verify they execute without error. Each reset script should produce the state that its task number starts from.

Flag any script that errors. If a reset script hardcodes a model name, note this as a Medium finding because it is fragile if the learner names their model differently.

## Version-Specific Issues

If any MCP check fails with an error that mentions a release, deprecated function, or removed parameter, flag it explicitly:

> This may be version-specific. Current MATLAB reports: [error]. Check whether
> this changed in a recent release.

## Rigor: Reachability Analysis

Apply the appropriate rigor level during Stage 2.

**Light** (`--light`):

- Only flag obvious gaps, such as missing prerequisites or out-of-order dependencies found during static analysis.
- Skip step-by-step simulation.

**Medium** (default):

- For each task from t02 onward, ask: "Given the state that exists after all prior tasks complete, can the learner reach this task's completion criteria by following this task's instruction?"
- Use reset scripts as ground truth for what state each task starts from.
- Flag any completion criterion that requires state not producible from the instruction plus prior state.

**Heavy** (`--heavy`):

- Mentally simulate the entire mission as a novice learner would experience it.
- For each task, enumerate what the learner knows at that point, what they might try, and where they could get stuck.
- Report stuck points where a reasonable learner following the instructions would not know what to do next.
- Consider ambiguous instructions that could lead to wrong paths, missing procedural detail, and missing recovery guidance for common mistakes.

## Cleanup

After Stage 2 completes, or if it errors partway through, clean up all MATLAB state created during the QA run:

```matlab
bdclose('all');
clear;
```

This ensures the QA pass does not leave models, variables, or figures behind that could interfere with the user's next action, such as starting a tutor session or running the setup script fresh.

Run cleanup even if checks fail.
