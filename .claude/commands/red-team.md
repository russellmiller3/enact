---
description: Red-team a plan — find holes, write fixes, bulletproof it
---

## Context

- Red Team guide: !`cat plans/guides/RED-TEAM-MODE-GUIDE.md`
- Plan template: !`cat PLAN-TEMPLATE.md`

## Task

Plan to attack: $ARGUMENTS

Read the plan file at the path above. Then systematically attack it using the Red Team guide.

**Attack Checklist (run ALL of these):**

1. 🚨 **Idempotency** — Does every mutating method return `already_done` in output? Check each one.
2. 🚨 **Transaction rollback** — Does every `conn.commit()` have a paired `conn.rollback()` in except? Is `conn = None` initialized before try?
3. 🚨 **Mock cursor pattern** — Are test cursor mocks set up as context managers (`__enter__`/`__exit__`)?
4. 🚨 **Import/export audit** — Is the module importable without optional deps? `__init__.py` updated?
5. 🚨 **SQL injection** — Any f-strings in SQL? Replace with `pgsql.Identifier`/`pgsql.Placeholder`.
6. 🚨 **ActionResult shapes** — Are success AND failure output shapes documented for every method?
7. 🚨 **Missing tests** — Any "add a test for X" without actual test code? Write the test.
8. 🚨 **Edge cases** — Empty dicts, None values, retries, dropped connections — handled?

**Devil's advocate questions (ask these for every feature):**
- What if the DB connection drops mid-transaction?
- What if the agent retries this workflow? (`already_done` handled?)
- What if `where` dict is empty? (Deletes everything?)
- What if an optional dep isn't installed?

**Output rules — TWO separate outputs:**

### Output 1: Update the plan file directly
Apply all fixes to `$ARGUMENTS`. The plan file gets corrected code, written-out tests, fixed ActionResult shapes — ZERO Red Team commentary. Clean spec only.

### Output 2: Attack report in chat
Tell Russell:

**🎯 Attack Summary**
- Critical (blocks implementation): [list with fixes applied]
- Moderate (will cause bugs): [list with fixes applied]
- Low (tech debt): [note for later]

**📝 Tests written** — list any tests you added to the plan

**⚠️ Remaining risks** — anything still risky that needs attention during implementation

**If you find architectural issues that require redesign:** say so in chat and stop. Do not patch over a broken design.
