---
name: small-pace-run-fast-development
description: Use when building, modifying, debugging, testing, or reviewing software with AI collaboration where requirements, tasks, implementation, verification, documentation, and Git history must stay aligned. Applies to vague requirements, multi-file changes, feature work, bug fixes, refactors, acceptance checks, and development workflow control.
---

# 小步快跑 · 软件开发推进模型

Use this skill to move software work from unclear intent to verified delivery through small, traceable steps.

Core rule:

```text
不清不做，做必切小；
小步实现，步步可验；
问题回流，版本留痕。
```

## 1. First Classify The Entry Point

Do not assume every request starts at requirements.

| User request | Entry point | First action |
| --- | --- | --- |
| "I want to build..." but vague | Requirement refinement | Diverge, clarify, converge |
| "Here is the PRD/spec" | Spec review | Check if it is buildable |
| "Break this down" | Planning | Create ordered tasks |
| "Implement this" | Development | Check spec, task, and verification first |
| "Fix this bug" | Bug loop | Reproduce and classify |
| "Check if complete" | Acceptance | Build checklist against spec |
| "Commit / summarize" | Evidence | Align files, tests, docs, Git |

After identifying the entry point:

```text
Check prerequisites
→ Fill missing prerequisites
→ Execute the smallest verifiable action
→ Verify
→ Continue, stop, or loop back
```

## 2. Apply The Right Process Weight

| Task size | Use |
| --- | --- |
| Light | Clarify goal → edit → quick verify → brief note |
| Medium | Requirement check → minimal spec → tasks → incremental implementation → layered tests → commit |
| Complex | Current-state analysis → divergent clarification → spec → design → task tree → slices → staged verification → change loop → archive |

Do not over-process one-line edits. Do not under-process multi-module or high-risk changes.

## 3. Gate 0: Requirement Clarity

Before coding, confirm these are answerable:

1. Who is the user?
2. What problem is being solved?
3. What is the input?
4. What is the output?
5. What does success mean?
6. What is out of scope?
7. What edge cases matter?
8. What pages, APIs, data, permissions, or files are affected?
9. How will this be tested?
10. How will completion be judged?

Classify:

| Status | Meaning | Action |
| --- | --- | --- |
| CLEAR | Enough to build | Move to spec/tasks |
| PARTIAL | Direction exists, details missing | List assumptions and fill gaps |
| VAGUE | Goal/scope/success unclear | Do not code; refine first |

Use `[NEEDS CLARIFICATION: specific question]` for unresolved ambiguity. Clear it before implementation or turn it into an explicit assumption/risk.

## 4. Requirement Refinement

When vague, explore:

- user roles
- business goal
- workflow
- input/output
- data model
- UI states
- API boundaries
- permissions/security
- edge and failure cases
- deployment/cost/maintenance
- future extension
- out-of-scope items

Converge into:

```markdown
## Requirement Essence

## Must Have

## Should Have

## Later

## Out of Scope

## Acceptance Criteria

## Open Questions
```

## 5. Gate 1: Buildable Spec

For medium or complex tasks, create or update a spec before implementation. The spec should include:

- objective
- users and roles
- user stories by priority
- functional requirements
- non-goals
- page/API/module/data boundaries
- edge cases
- non-functional requirements
- acceptance criteria
- testing strategy
- risks and open questions

User stories should be independently testable:

```markdown
## User Story 1 - Title (Priority: P1)

### Value
- ...

### Independent Test
- ...

### Acceptance Scenarios
1. Given ..., When ..., Then ...
```

Keep specs focused on what and why. Avoid premature implementation detail unless it is a real constraint.

## 6. Plan Before Changing Code

Before implementation, produce a concise plan:

- module order
- dependency order
- files likely touched
- tests to add or run
- risks
- rollback points
- items intentionally not handled

Map dependencies and prefer vertical slices over horizontal layers.

Good slice:

```text
User can create a task: data + API + basic UI + test
```

Weak slice:

```text
Build all database tables, then all APIs, then all UI
```

## 7. Gate 2: Task Size

Every task must have:

- a clear goal
- acceptance criteria
- verification method
- dependency notes
- likely files
- expected commit message

Task format:

```markdown
## Task T001 [P] [US1]: Short title

### Goal
- ...

### Scope
- Change:
- Do not change:

### Acceptance
- ...

### Verify
- Command:
- Manual:

### Files
- ...

### Commit
- ...
```

Use `[P]` only when tasks touch different files and have no dependency conflict.

Break a task down further if:

- it touches independent subsystems
- it needs more than one focused session
- acceptance cannot be stated in a few bullets
- the title contains "and"
- it would modify too many unrelated files

## 8. Incremental Implementation Loop

For each task:

```text
Read relevant spec and code
→ Implement smallest meaningful slice
→ Run local verification
→ Fix immediate errors
→ Record result
→ Commit or leave ready for commit
→ Move to next slice
```

Rules:

- Touch only what the task requires.
- Keep the project buildable after each increment.
- Do not mix refactors with feature work unless required.
- Prefer simple, obvious code before abstractions.
- If assumptions break, stop and return to spec/plan.
- If verification fails, do not start the next task.

## 9. Testing And Verification

Use the smallest useful proof first, then widen:

1. unit or single-point check
2. module or component test
3. integration flow
4. frontend/browser check if UI changed
5. backend/API/data check if server changed
6. full test/lint/build
7. acceptance against spec

For behavior changes, prefer test-first. For bug fixes, use the Prove-It pattern:

```text
Reproduce bug
→ Write failing test or reproduction note
→ Fix root cause
→ Verify test passes
→ Run regression check
```

For final acceptance, check:

- completeness: tasks, requirements, scenarios
- correctness: behavior, edge cases, errors
- coherence: implementation matches design and project conventions

## 10. Bug And Change Loop

Classify every issue:

| Type | Meaning | Action |
| --- | --- | --- |
| Bug | Violates existing requirement | Reproduce, fix, test, record |
| Requirement gap | Should have been specified but was missing | Update spec, then fix |
| New requirement | Adds scope | Evaluate whether current version includes it |

Start a new change when intent changes, scope becomes independent, or the original work can be shipped without it.

Update the existing change when the goal is the same and the work is a refinement, narrowed MVP, or implementation discovery.

## 11. Git Evidence

Use Git as evidence, not just storage.

Rules:

- One small task or logical slice per commit when possible.
- Do not stage unrelated files.
- Keep formatting-only, refactor, docs, tests, and behavior changes separate when practical.
- Commit messages should explain intent.
- Never commit secrets, tokens, local caches, or vendor repos.
- Failed tests must be reported, not hidden.

Before committing:

```text
git status
git diff --staged
run relevant verification
```

End-of-cycle report:

```markdown
## Completed
- ...

## Changed Files
- ...

## Verification
- Command:
- Result:

## Risks
- ...

## Next Step
- ...
```

## 12. Change Artifacts For Larger Work

For medium/complex changes, separate current truth from proposed changes:

```text
specs/      current behavior
changes/    proposed or active changes
```

A change can contain:

```text
changes/<name>/
├── proposal.md
├── design.md
├── specs/
└── tasks.md
```

Before closing a change:

- all intended tasks are checked or deferred
- requirements map to implementation
- acceptance scenarios are tested or manually verified
- design decisions match code or docs are updated
- stable requirements are merged back into the main spec

## 13. Red Flags

- Coding starts with no written acceptance criteria.
- "Implement feature" appears as a task.
- Tests are deferred to the end without reason.
- A task mixes feature, refactor, formatting, and dependency changes.
- A bug fix starts without reproduction.
- A new requirement is silently implemented without spec/task update.
- Git commit includes unrelated files.
- Final report omits tests or says "not run" without reason.
