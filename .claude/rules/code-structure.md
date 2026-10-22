---
paths:
  - "src/**"
---
# Code structure

Decisions here are made by the owner in the brief. architect records them, agents follow them. If a decision marked TBD is needed for the task, do not choose: stop and return the question.

## Project decisions

<!-- architect fills from the brief; the owner edits by hand afterwards. Reasons and rejected options: .design/design.md, Decisions. -->

- Slicing: TBD  <!-- layers | entities -->
- ORM models: TBD
- Domain types: TBD
- API schemas: TBD
- Repository rows (what a repository returns): TBD

## Naming

- A module is named `<subject>_<role>`: `aggregation_service`, `user_repository`. The role suffix says what the module is; the subject says what it works on.
- Roles in use: `_service`, `_repository`. Other roles: TBD.

## Form of code

- A function is allowed only when it has no dependencies and no state: it computes from its arguments and returns a result.
- Anything with dependencies or state is a class. Dependencies come through `__init__`.
- The choice between function and class follows these two rules and is not reopened per task. If a case fits neither, return the question.

## Module size and splitting

- Guide: 200-300 lines per module. A guide, not a limit: exceeding it is a signal to check responsibility, not a reason to cut mechanically.
- A module has one responsibility. Split when a module serves two reasons to change, not when it only grows.
- Do not split into many tiny modules ahead of need.

## Patterns

- Introduce a pattern only when the scenario already scales (several variants, several implementations, a proven need). For a single case write the direct code.
- A pattern appears in code only if the brief or plan names it. Do not add one on your own initiative.

## Conventions

Principle: shared decisions are made once and reused, not reinvented per module. Error codes and response shapes, the exception hierarchy, defaults and settings are fixed in `.design/design.md`, section Conventions. Follow them; if a case is not covered, return the question instead of inventing a form.
