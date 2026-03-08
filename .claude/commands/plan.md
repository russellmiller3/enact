---
description: Create an implementation plan using PLAN-TEMPLATE.md
---

## Context

- Recent commits: !`git log --oneline -10`
- Current branch: !`git branch --show-current`
- Handoff context: !`cat Handoff.md`
- App state map: !`cat enact-intent.md`

## Task

Feature to plan: $ARGUMENTS

Create an implementation plan for the feature above.

**Step 1 — Pick the right template:**

```
Is the logic already written and tested?
|-- YES → Template C (Refactoring/Migration)
|-- NO → Building new logic?
    |-- Small (<200 lines, 1-2 files) → Template B
    |-- Large (>200 lines, multiple systems) → Template A
```

**Step 2 — Read relevant existing code** before writing a single line of the plan. Read `PLAN-TEMPLATE.md` for the exact template to follow.

**Step 3 — Write the plan** to `plans/YYYY-MM-DD-<kebab-name>.md` (use today's date). Follow the chosen template exactly — do not skip sections. For Template A, every TDD cycle must include:
- Exact test code (copy-paste ready)
- The exact pytest command to run it
- The implementation code for that cycle

**Step 4 — State in chat** which template you chose and why, then the plan file path.

**Rules:**
- Plans go in `plans/` — never in `.claude/plans/`
- Write files in chunks ≤150 lines (write first chunk, then Edit to append)
- After creating the plan, tell Russell to run `/red-team plans/<filename>` to bulletproof it
