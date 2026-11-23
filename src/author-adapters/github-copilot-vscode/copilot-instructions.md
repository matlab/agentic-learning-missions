# Interactive Missions Authoring Workspace

This folder is an Interactive Missions marketplace authoring workspace.

The `evaluate-tutor-skill` and `simulate-mission-learner` prompts invoke the Codex evaluation runner. They do not qualify Copilot as an evaluation runtime.

Read `docs/1-index.md` before changing mission content. The portable author skills are under `.interactive-missions/authoring/skills/`. Run the matching prompt from `.github/prompts/` to start authoring, QA, or maintenance. Set the `source_url` TODO in `marketplace/manifest.yaml` before publishing or registering the marketplace.
