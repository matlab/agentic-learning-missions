# Setup Script Reference

Use this reference only when the mission needs prepared workspace data, models,
or other starting state. `../references/mission-contract.md` remains the source of truth
for setup/reset constraints.

## Decision Rules

Skip setup when task 1 can start from the learner's current environment or can
instruct the learner to create the starting artifact manually.

Use setup when the mission needs prepared data, helper files, or model state
that would distract from the learning objective or take too long for the learner
to build from scratch.

Do not leave answers or expected final-state artifacts in the learner
workspace. Setup should provide starting material, not complete later tasks.

## Process

Before writing the setup script:

1. Load the `matlab-script-writing` skill for coding conventions.
2. Draft and run the code via `evaluate_matlab_code` or `run_matlab_file`.
3. Only after successful execution, write the script beside `mission.yaml`.

`setup_<mission_name>.m` is the recommended naming convention, not a runtime requirement. The `setup.script` value in `mission.yaml` is authoritative.

## Setup Script Structure

```matlab
% Setup for <mission-name>: <Title>
%
% Context: <Backstory - what the data represents, where it comes from>
% Goal: <What the learner will ultimately do with this data>

%% Generate signal/data
<construction code>

%% Package for Simulink
<timeseries or appropriate format>

%% Clean up internal variables
clear <construction vars that shouldn't be visible to learner>

```

Adapt section names when the setup prepares something other than signals or
data, but keep the file readable and organized.

## MATLAB Coding Rules

- Use double-quoted strings.
- Use `disp` with concatenation instead of `fprintf`.
- Clear construction variables; leave only what the learner needs.
- Keep clean, expected, answer, or final-state signals hidden from the learner.
- Avoid destructive filesystem operations, persistent path mutation, and
  environment changes.

## Setup Validation Requirements

Before committing a setup script:

- [ ] The setup script runs cleanly via `run_matlab_file` with no errors.
- [ ] The workspace variables left by the script match the YAML `setup.description`.
- [ ] The setup script clears construction variables that learners should not see.
- [ ] The script does not expose the expected answer or final artifact.
- [ ] The first task can be completed from the state left by setup.
