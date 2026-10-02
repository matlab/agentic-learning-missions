# Authoring Workflow

Mission authoring works best as a short cycle: draft, review, and maintain. The skills in this repository are designed to support that cycle without asking authors to hand-write every YAML field on the first pass.

## 1. Set Up an Authoring Workspace

Create an empty folder for the marketplace, change MATLAB's current folder to it, then run:

```matlab
startMissionAuthoring()
```

The function asks which supported agentic client to configure. 

It then creates `marketplace/manifest.yaml`, `marketplace/missions/`, shared assets folders, copied author documentation, and the selected agent's authoring instructions. It can also create `marketplace/missions/<mission-name>/mission-brief.md` for the first mission.

The generated manifest has an empty `source_url` TODO so authors can begin before creating a remote repository. Set a real HTTPS or SSH Git clone URL before registering or publishing the marketplace.

## 2. Create a Mission

Use `create-tutor-mission` when you want to create a learner mission. The skill interviews you, drafts the mission YAML, and adds setup code when the mission needs prepared learner state.

You can start from different levels of detail. A good mission has:

- a clear objective,
- observable learning outcomes,
- a short sequence of learner tasks,
- an ordered hint ladder that progresses from directional to specific to direct help,
- semantic completion checks that the tutor skill can verify, and
- optional setup that leaves the learner in a clean starting state.

### Option A: High-Level Details Only

Use this when you know the learning goal but do not yet have a task sequence.

Example prompt:

```text
Use create-tutor-mission to build a mission about configuring a Simulink root
inport with workspace data. The learners are new to Simulink but comfortable
with MATLAB arrays. I want them to inspect data, connect it to a model, run the
model, and interpret the output.
```

The skill will ask for details such as the domain context, stable mission-folder slug, learning outcomes, and setup needs.

### Option B: Goal Plus Task Sequence Sketch

Use this when you already know the learner journey, but want the skill to turn it into mission structure and completion checks.

Example prompt:

```text
Use create-tutor-mission to draft a mission on continuous and discrete time.
Task sketch:
1. Create a continuous sine source.
2. Add a discrete source with a fixed sample time.
3. Run the model and compare the traces.
4. Change the sample time and explain what changed.
```

The skill should preserve the sequence while shaping each task into a clear instruction, hints, and semantic completion checks.

### Option C: Goal Plus Specific Instruction and Hint Text

Use this when you have wording that should appear in the learner experience.

Example prompt:

```text
Use create-tutor-mission to build mission 03. I have draft task text below.
Preserve the instruction wording unless it conflicts with mission structure.

# Task 1

## Instruction

Open the model and find the signal path that starts at the root Inport.

## Hints

1. Look for the block named In1.
2. Follow the signal line from left to right.
```

If exact wording matters, say so. Otherwise, the skill can adapt your text for clarity and consistency.

## 3. Run a Quality Check

Use `qa-mission` after the first draft. QA is not only a schema check. It also reviews whether the mission supports the instructional design you described.

`qa-mission` can check:

- whether the mission YAML is well-formed,
- whether setup and reset files match the mission,
- whether completion checks are observable,
- whether hints become actionable enough to rescue a stuck learner,
- whether outcome-oriented completion checks accept behaviorally equivalent solutions and inspect current state,
- whether learning outcomes are mapped to tasks, and
- whether MATLAB&reg; or Simulink&reg; behavior can be verified through MCP tools.

Example prompt:

```text
Use qa-mission on root-inports-outports. Check whether the task sequence supports the
learning outcomes and whether a learner can complete each task from the stated
starting state.
```

Treat QA findings as design feedback. Some findings are mechanical fixes, and others are judgment calls for the author.

## 4. Publish The Mission

Keep draft and experimental content in an authoring workspace until it is ready to publish. To ship a reviewed mission, add its folder to `marketplace/missions/<mission-name>/`, add the mission to `marketplace/manifest.yaml`, and update the marketplace content version.

Run `qa-mission` and the marketplace validators before publication. Repository maintainers then package the updated marketplace with the toolbox release. Learners receive curated missions by updating or reinstalling the toolbox; individual mission ZIP export and import are not supported.

## 5. Maintain Missions Over Time

Use `maintain-missions` for periodic maintenance. Maintenance is useful when MCP tools change, mission content moves, validation rules evolve, or packaged missions need a release-readiness pass.

Example prompt:

```text
Use maintain-missions to check the mission framework after updating allowed MCP
tools. Confirm the mission contract, skill guidance, and validators still agree.
```

For day-to-day mission authoring, authors usually need `create-tutor-mission` and `qa-mission`. Use `maintain-missions` when you are caring for the mission set or framework itself.
