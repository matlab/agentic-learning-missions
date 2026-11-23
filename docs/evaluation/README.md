# Tutor and Mission Evaluation Workflows

Choose a workflow based on your role and the question you need to answer. Each guide includes its own preparation, inputs, outputs, result interpretation, and feedback steps.

| Your role | Start here | What comes next |
| --- | --- | --- |
| Repo maintainer | [Evaluate the tutor](evaluate-tutor-skill.md) to check Ada's behavior and teaching rules. | Use [learner simulation](simulate-mission-learner.md) to examine how Ada works across representative full missions. |
| Content author or educator | [Simulate mission learners](simulate-mission-learner.md) to review and test your mission. | Use the evidence to refine the mission and gather confirming results. |

Content authors can use the learner simulation workflow on its own. It does not require tutor evaluation. Maintainers can use both workflows to study tutor changes, but neither evaluation gates execution of the other.

## Guides

- [Tutor evaluation workflow](evaluate-tutor-skill.md): choose cases and layers, evaluate a tutor version, review findings, and continue with mission-level evidence.
- [Learner simulation workflow](simulate-mission-learner.md): prepare and review a mission specification, run learner profiles, interpret outcomes, and return author feedback.

These guides are written for reading in the Git repository. For environment setup, exact commands, and technical contracts, use the shared [evaluation runner and interpretation guide](../../src/author-skills/references/evaluation/README.md).

For content review before simulation, use [mission QA](../3-skill-usage.md#qa-mission). For setup, reset, progress, and infrastructure checks, use [framework and runtime validation](../6-runtime-validation.md). Learners who want to work through a mission can follow [the learner workflow](../../README.md#for-learners).
