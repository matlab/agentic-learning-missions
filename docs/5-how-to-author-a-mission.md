# How to Author a Mission

This walkthrough shows one practical path from rough instructional goal to a reviewed mission. The details will vary by topic, but the authoring rhythm is the same: describe the learning experience, let the skill draft, review the mission, and iterate.

## 1. Start With the Learner Goal

Begin with the capability you want learners to demonstrate.

Example:

```text
Learners should connect MATLAB workspace data to a Simulink model, run the
model, and compare the logged output with the original data.
```

This is close to the sample Mission 01 in this repository, which teaches root inports and outports in Simulink&reg;. Notice that the goal names an observable workflow rather than only a feature.

Run `startMissionAuthoring()` from an empty folder before launching the authoring client. The command creates the marketplace layout and can optionally write a first-mission brief containing the initial title and goal.

## 2. Decide the Starting State

Ask whether learners can begin from their current environment or whether the mission should prepare something for them.

Mission 01 uses setup because learners need a noisy respiratory signal in the workspace. Mission 02 does not need setup because learners can build the model from a clean Simulink environment.

Use setup when it removes irrelevant preparation work. Avoid setup when doing the preparation is part of the learning goal.

## 3. Prompt create-tutor-mission

Give the skill the goal, audience, rough scope, and any task wording you care about.

Example:

```text
Use create-tutor-mission to create a mission about root inports and outports.
Learners know MATLAB basics but are new to Simulink. The mission should use a
realistic signal dataset, ask learners to inspect it, feed it into a model,
filter it, and compare the result in MATLAB. Use 5 to 7 tasks.
```

If you have a sequence, include it:

```text
Task sketch:
1. Plot the prepared workspace data.
2. Create a model with an Inport.
3. Configure the model to load the workspace input.
4. Add a Scope and run the model.
5. Add a filter and Outport.
6. Compare filtered and unfiltered results.
```

The skill should turn this into mission YAML with task IDs, instructions, hints, completion checks, and outcome mappings.

## 4. Review the Draft as an Author

After the first draft, read the learner-facing parts first:

- Does the objective match the mission you intended?
- Are the tasks in a sensible learning order?
- Does each task ask for one main action?
- Do instructions state the goal and purpose without giving the procedure or answer?
- Do the ordered hints progress from directional to specific to direct help, with a final hint that is actionable for a stuck learner?

Then scan the mission structure:

- Are learning outcomes observable?
- Does each outcome appear in one or more `outcome_refs`?
- Are setup requirements clear?
- Do completion checks describe observable finished states?

## 5. Run qa-mission

Use `qa-mission` to check the draft.

Example:

```text
Use qa-mission on <mission-name>. Check whether the mission YAML is well-formed,
whether the completion checks are observable, and whether the task sequence
supports the stated learning outcomes.
```

Expect two kinds of feedback:

- Mechanical issues, such as missing outcome mappings or unsupported tool names.
- Instructional-design issues, such as hints that never become actionable, hidden completion requirements, stale-state checks, overly narrow structural checks, or a task that does not actually demonstrate the claimed outcome.

Apply fixes that preserve your intent. For subjective findings, decide whether the recommendation improves the learner experience.

## 6. Iterate Until the Mission Reads Like a Lab

A mission should feel like a focused hands-on lab. It does not need to explain all theory up front. It should give learners enough context to act, then help them inspect the result.

Mission 02 is a useful example of a compact mission. It teaches continuous and discrete time through a direct sequence of model-building and comparison tasks. Mission 01 is a fuller example with setup data, runtime validation metadata, and a longer workflow.

When the mission is ready, installed toolbox users keep the authored content in
an authoring workspace, then publish it through marketplace content. Repository
maintainers keep curated packaged content under `marketplace/missions` and use
maintenance checks before review or release.
