# Interactive Missions Authoring Workspace

This folder is an Interactive Missions marketplace authoring workspace.

Read `docs/1-index.md` before changing mission content. The portable author skills are under `.interactive-missions/authoring/skills/`.

Use `/create-tutor-mission`, `/qa-mission`, `/maintain-missions`, `/evaluate-tutor-skill`, or `/simulate-mission-learner` to start the corresponding workflow. Evaluation skills invoke the Codex evaluation runner; they do not qualify Claude as an evaluation runtime. Set the `source_url` TODO in `marketplace/manifest.yaml` before publishing or registering the marketplace.
