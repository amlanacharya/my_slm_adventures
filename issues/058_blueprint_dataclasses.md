---
title: [simple_kurma_v2] Add blueprint dataclasses and JSON/YAML loading
number: "058"
---

## Target
Branch: simple_kurma_v2
Milestone: Kurma_v2
Label: eady-for-agent
## What to build
Define the workflow blueprint data model and loader for workflow_id, version, mode, actions, action kind, conditions, and allowed tools. Keep this limited to parsing/validation and serialization. Do not add evaluator behavior in this issue.
User stories covered: 1, 2, 3, 4, 9
## Acceptance criteria
- [ ] A blueprint can be loaded from a fixture file into typed Python objects.
- [ ] Invalid required fields produce clear validation errors.
- [ ] Unit tests cover at least one valid blueprint and one invalid blueprint.
## Blocked by
None - can start immediately
