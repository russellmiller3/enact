# Plan [NUMBER]: [FEATURE NAME]

> **📊 Find next plan number:** Run `node scripts/analyze-plans.cjs` to see current plan range and next available number.

---

## 🎯 CHOOSE YOUR TEMPLATE

**Pick the right template for your task:**

| Template                                                             | Use When                               | Structure                    | TDD?                      |
| -------------------------------------------------------------------- | -------------------------------------- | ---------------------------- | ------------------------- |
| **[A: Full TDD](#template-a-full-tdd-greenfield-features)**          | Building new features from scratch     | 17 sections, detailed cycles | ✅ Kent Beck cycles       |
| **[B: Small Plan](#template-b-small-plan-bug-fixes--tiny-features)** | Bug fixes, small features (<200 lines) | Lightweight, 8 sections      | ✅ Simplified cycles      |
| **[C: Refactoring](#template-c-refactoringmigration)**               | Renaming, restructuring, migrations    | Phase-based, linear          | 🔧 Test verification only |

**Decision tree:**

```
Is the logic already written and tested?
├─ YES → Template C (Refactoring/Migration)
└─ NO → Building new logic?
    ├─ Small (<200 lines, 1-2 files) → Template B (Small Plan)
    └─ Large (>200 lines, multiple systems) → Template A (Full TDD)
```

**Examples:**

- **Template A:** New research panel, new dashboard feature, new AI integration
- **Template B:** Fix text duplication bug, add keyboard shortcut, improve error message
- **Template C:** HUD→Desk rename, move components to new folder, merge two stores

---

## 🪃 EXECUTION MODE GUIDANCE

**After creating this plan, which mode should execute it?**

| Mode                     | Use When                                      | Example                                                          |
| ------------------------ | --------------------------------------------- | ---------------------------------------------------------------- |
| **💻 Code Mode**         | Single-domain implementation, clear TDD path  | Template A/B with <10 files, focused scope                       |
| **🪃 Orchestrator Mode** | Multi-domain coordination, >5 distinct phases | Feature spanning UX design + backend + frontend + testing + docs |

### Use Code Mode If:

- Plan is implementation-focused (just code changes)
- Single domain (frontend OR backend, not both + more)
- Template A/B/C fits in single TDD session
- <1000 lines, <10 files
- Clear path from start to finish

### Use Orchestrator Mode If:

- Plan requires UX decisions + implementation + debugging
- Spans multiple specialties (design, backend, frontend, testing, docs, deployment)
- > 5 distinct phases that could each be subtasks
- > 1000 lines, 10+ files across multiple systems
- Would benefit from parallel subtask delegation

### Decision Process:

1. **Simple feature/bugfix?** → Code mode executes directly
2. **Complex multi-phase project?** → Orchestrator breaks into subtasks
3. **Unclear scope?** → Start Code mode, escalate to Orchestrator if complexity grows

**When in doubt:** Start with Code mode. Code mode can delegate to Orchestrator mid-stream if needed.

---

## 🚨 CRITICAL RULES (ALL TEMPLATES)

These rules apply regardless of which template you use:

### Make sure to copy these rules below into any plan you create. everything in step 0.

Rules:

### Read the log of past 10 commits for context

### ALWAYS make a new branch first

### Keep PROGRESS.md updated AS YOU GO - Russell monitors it!

### ⚠️ UPDATE TESTS IMMEDIATELY WHEN REFACTORING

**CRITICAL:** When renaming/moving/refactoring code, update tests IN THE SAME STEP.

**Why:** Husky runs tests on pre-commit. If tests import non-existent files, commit fails.

**Pattern:**

```bash
# ✅ CORRECT
mv file.js new-file.js              # 1. Rename code
# Update imports in code...         # 2. Fix code imports
mv file.test.js new-file.test.js   # 3. IMMEDIATELY rename test
# Update imports in test...         # 4. Fix test imports
npm test                            # 5. Verify tests pass
git commit                          # 6. NOW commit works

# ❌ WRONG
mv file.js new-file.js              # 1. Rename code
# Update imports...                 # 2. Fix imports
git commit                          # 3. Husky fails - test imports old file!
# Now scramble to fix tests...      # 4. Frustration
```

**Use `git small` during refactoring to skip hooks, but FIX TESTS BEFORE FINAL COMMIT.**

### ⚠️ CRITICAL THINKING MANDATE (Karpathy's Law)

**BEFORE implementing ANYTHING:**

- **Flag confusion** - Any ambiguity? Stop. Ask Russell.
- **Surface inconsistencies** - Plan contradicts code? Stop. Point it out.
- **Present tradeoffs** - Multiple ways? Stop. Show options with pros/cons.
- **Simplest solution FIRST** - Can this be 100 lines instead of 1000?
- **Push back** - Plan seems overcomplicated? Tell Russell why.
- **Preserve unrelated code** - NEVER change code outside your task scope.

**Example:**

```markdown
"Russell, before implementing the DataGrid feature, I see 3 options:

Option A: New GridStore + GridComponent (200 lines)
✅ Clean separation
❌ More files to maintain

Option B: Extend existing editorStore (80 lines)
✅ Reuses existing state management
❌ Couples grid to editor

Option C: Pure component with props (50 lines)
✅ Simplest, no state complexity
❌ Parent must manage all state

I recommend C - simplest, least abstraction. We can refactor to A/B if we hit real complexity.
Agree?"
```

**Don't be a yes-man. Think critically. Propose the simple path.**

### NEVER ASK USER TO CHECK BROWSER/CONSOLE

**ABSOLUTELY FORBIDDEN:**

- Check the browser console
- Open DevTools / F12
- Check for errors in console
- Copy paste console output
- Check terminal output manually
- Look at any logs

**THE ONLY CORRECT APPROACH:**

- Wire ALL debugging output to `terminal.log` using logger.js
- Read terminal.log yourself using read_file tool to debug
- Check terminal.log after every change
- Russell will ONLY look at the UI, never console or logs
- You are responsible for all debugging - NOT Russell

**IF YOU ASK USER TO CHECK CONSOLE/LOGS YOU HAVE FAILED**

### How to Debug Properly

1. **Add logging via logger.js** - All debug output MUST use the logger
2. **Test in CLI FIRST** - Use test scripts, not browser
3. **Check terminal.log yourself** - Use read_file tool or query-logs.js
4. **Fix the issue** - Based on what you see in terminal.log
5. **NEVER ask user to check console** - That's your job, not theirs

### CLI Testing Mode (10x Faster Iteration)

**For API endpoint changes (chat, research, orchestrator):**

```bash
# Test chat endpoint directly (no browser needed)
npm run test:chat "your query here"

# Test research endpoint
npm run test:research "topic here"

# Test orchestrator (Plan 59+)
npm run test:orchestrate "complex query"

# With options
npm run test:chat -- --verbose "query"   # See full SSE stream
npm run test:chat -- --timing "query"    # Show timing metrics
```

**Debug workflow:**

```
1. Clear logs: node scripts/query-logs.js --clear
2. Run test: npm run test:chat "query"
3. Query logs: node scripts/query-logs.js KEYWORD
4. Fix → Run test again → Repeat
```

**Why CLI testing:**

- See SSE events in 10 seconds (vs 30-60s in browser)
- YOU can test without Russell
- No "can you test this again" loops
- Automated validation of response structure
- 10x faster iteration = ship features 10x faster

**See [`plans/plan-61-cli-testing-mode.md`](plans/plan-61-cli-testing-mode.md) for full details.**

---

## 🔍 STEP ZERO: Read The Codebase Reference FIRST

**MANDATORY before planning ANY feature:**

📚 **Read [`plans/CODEBASE-REFERENCE.md`](CODEBASE-REFERENCE.md) first**

**Why:** Contains what's actually built vs spec fiction, critical gotchas, data flow diagrams, test patterns to copy.

**How to use it:**

1. Read TL;DR (30 seconds) - get mental model
2. Scan ToC for relevant sections
3. Read those sections (2-5 minutes)
4. Proceed with planning fully informed

---

## 0. Before Starting (CRITICAL - ALL TEMPLATES)

### 0.0 AI-Proofing Checklist (RED TEAM PREVENTION)

**Complete BEFORE writing plan sections to prevent AI errors:**

#### 0.0.1 Codebase Syntax Check

**Read actual files to verify current patterns:**

- [ ] Read target component files - what's the actual event binding? (`onclick` vs `on:click`)
- [ ] Check Svelte version - Are we using runes ($state) or stores?
- [ ] Check loop variable names in similar components
- [ ] Check CSS class patterns used elsewhere
- [ ] Verify import patterns (default vs named)

**Example: Before planning component changes, READ the file to see:**

- Current: `onclick={() => mode = m.id}` (Svelte 5)
- NOT: `on:click={() => mode = mode.id}` (Svelte 4)
- Loop var: `m`, NOT `mode` (avoids shadowing)

#### 0.0.2 Write Actual Test Code (Not Wishes)

**In your plan, include COMPLETE test code:**

```javascript
// ✅ GOOD - Copy-paste ready
it("prevents double-click race condition", async () => {
  const mockFn = vi.fn();
  render(Component, { props: { onAction: mockFn } });

  const button = screen.getByText(/action/i);
  await fireEvent.click(button);
  await fireEvent.click(button); // Double click

  expect(mockFn).toHaveBeenCalledTimes(1); // Debounced
});

// ❌ BAD - Vague wish
// "Test that double-clicks are prevented"
```

#### 0.0.3 CSS Specs Table (Exact Classes)

**Create table with EXACT Tailwind classes:**

| Element | State    | Light Mode                                        | Dark Mode                |
| ------- | -------- | ------------------------------------------------- | ------------------------ |
| Button  | Hover    | `hover:bg-blue-700`                               | `dark:hover:bg-blue-600` |
| Button  | Disabled | `disabled:opacity-50 disabled:cursor-not-allowed` | (same)                   |

**NO VAGUE SPECS like "make it match the app" - write the classes.**

#### 0.0.4 Race Condition Analysis

**For EVERY user interaction, ask:**

| Question                                    | Code Prevention           |
| ------------------------------------------- | ------------------------- |
| What if they double-click?                  | Debounce with lock flag   |
| What if API is in-flight during navigation? | AbortController           |
| What if rapid mode switches?                | Cleanup in $effect return |
| What if auto-create runs twice?             | Lock flag check           |

**Include prevention CODE in plan, not just description.**

#### 0.0.5 Data Contracts (JSDoc + Examples)

**Write JSDoc AND example objects:**

```javascript
/**
 * @typedef {Object} ActionType
 * @property {'type1'|'type2'} type
 * @property {string} [optional] - Optional field
 */

// Example valid object:
const valid = { type: "type1", optional: "value" };

// Example edge case:
const missing = { type: "type1" }; // → Uses default
```

#### 0.0.6 Exact Error Message Strings

**Write the ACTUAL user-facing copy:**

```javascript
const ERROR_MESSAGES = {
  API_TIMEOUT: "Failed to load. This is taking longer than expected.",
  NO_AUTH: "Please sign in to continue.",
  // NOT: "show error message" (too vague)
};
```

#### 0.0.7 Edge Cases with Exact Handling

| Scenario      | Exact Error Copy                            | Handling Code                   |
| ------------- | ------------------------------------------- | ------------------------------- |
| Missing field | (No error - use default)                    | `field \|\| "Default"`          |
| Not found     | "Item not found. It may have been deleted." | Check exists, log, return early |

**NO VAGUE "handle gracefully" - write the code.**

### 0.1 Create Feature Branch FIRST 🌿

**BEFORE touching ANY code:**

```bash
git checkout -b feature/[descriptive-name]

# Examples:
# git checkout -b feature/datagrid-tab
# git checkout -b fix/text-duplication
```

**Why:** Protects main, easy rollback, merge only when complete + tested

### 0.1 Create PROGRESS.md

```markdown
# [Feature Name] Progress

**Current Cost:** $X.XX ⚠️ (flag if >$4)

## 🎯 CURRENT FOCUS

[What you're working on RIGHT NOW]

## ✅ Completed

- [x] Item 1

## 📋 Next Steps

- [ ] Item 3

## 🔥 Blockers

[Any issues]

## 🧪 Test Status

- Tests: X/X passing
- Browser: [Status]
```

**CRITICAL: Update PROGRESS.md AS YOU GO** - Russell monitors this!

### 0.2 Cost Efficiency: Resume Prompts

After major milestones, create resume prompts to save ~$0.60+ per step:

```markdown
Read plans/plan-[N].md for full context.

Continue [Feature] - [Milestone].

**Branch:** feature/[name]
**Status:** ✅ [Previous] complete, tests passing, committed
**Next:** [Current milestone]

Start with [next step] now.
```

### 0.3 Wire Up Logger

```javascript
import { log } from "$lib/utils/logger.js";

log("[TAG] functionName called", { data });
log("[ERROR] something failed", { error });
```

**YOU check terminal.log, NOT Russell.**

---

# TEMPLATE A: Full TDD (Greenfield Features)

**Use for:** New features from scratch (>200 lines, multiple systems)

## A.1 What We're Building

[User-facing description with ASCII diagrams]

```
┌───────────────────────┐
│ BEFORE                │
└───────────────────────┘
         ↓
┌───────────────────────┐
│ AFTER                 │
└───────────────────────┘
```

**Key Decisions:**

- [Decision 1 with rationale]

## A.2 Existing Code to Read First

| File   | Why    |
| ------ | ------ |
| `path` | Reason |

## A.3 Data Flow Diagram

```
User action → Store → localStorage/API
```

## A.4 Files to Create

### Component/Module Name

**Path:** `path/to/file`

```javascript
// Full code example with:
// - SSR guards (if browser APIs used)
// - Race condition prevention (debounce, AbortController)
// - Error handling with exact error messages
// - Logging with [TAG] convention
```

**Test File (COMPLETE CODE, NOT DESCRIPTION):**

```javascript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import ComponentName from "./ComponentName.svelte";

describe("ComponentName", () => {
  beforeEach(() => {
    // Reset state
  });

  it("handles user interaction correctly", async () => {
    render(ComponentName, { props: { onAction: vi.fn() } });
    const button = screen.getByRole("button", { name: /action/i });
    await fireEvent.click(button);
    // Assert expected behavior
  });

  it("prevents double-click race condition", async () => {
    const mockFn = vi.fn();
    render(ComponentName, { props: { onAction: mockFn } });

    const button = screen.getByText(/action/i);
    await fireEvent.click(button);
    await fireEvent.click(button); // Double click

    expect(mockFn).toHaveBeenCalledTimes(1); // Debounced
  });

  it("handles API errors gracefully", async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error("timeout")));
    render(ComponentName);

    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
```

**⚠️ WRITE FULL TEST CODE - Not "test for double-clicks" (too vague)**

### 🎯 What to Actually Test (Updated Feb 2026)

**Testing Philosophy:**

Write tests ONLY for:
1. **Complex business logic** - Algorithms, parsing, data transformations with branches
2. **Multi-step workflows** - E2E flows that users actually experience
3. **Bug regression** - ONE test when you fix a real bug

**When you create new tests, update [`plans/TEST-REFERENCE.md`](plans/TEST-REFERENCE.md):**
- Add test file to appropriate section
- Document key tests/purpose
- Add new patterns if applicable
- Update test count

**DO NOT test:**
- ❌ Null/undefined/empty string handling (JavaScript works, stop verifying it)
- ❌ Getters/setters (`store.save('x')` then `store.value === 'x'` is not a test)
- ❌ Trivial utilities (<30 lines, no branches, obvious behavior)
- ❌ UI component structure (brittle, breaks on every refactor)

**Prefer:**
- ✅ One E2E test over ten unit tests
- ✅ Integration tests over mocks
- ✅ Real user workflows over isolated functions

**Cost/benefit check before writing a test:**

| Question | Test It? |
|----------|----------|
| What breaks if this fails? User can't log in | ✅ YES - test it |
| What breaks if this fails? HTML parser returns 49 chars instead of 50 | ❌ NO - who cares |
| Is this testing MY logic or JavaScript's? My deduplication algorithm | ✅ YES - test it |
| Is this testing MY logic or JavaScript's? JavaScript handles null | ❌ NO - don't test |
| Will this break on refactors? Exact DOM structure | ❌ NO - too brittle |
| Will this break on refactors? "Research returns sources" | ✅ YES - stable contract |

**See [`plans/TEST-COVERAGE-ANALYSIS.md`](plans/TEST-COVERAGE-ANALYSIS.md) for full analysis and examples.**

### ⚠️ TEST FILE GOTCHAS

1. **Import vi if mocking:**

   ```javascript
   import { describe, it, expect, vi } from "vitest";
   ```

2. **Check render pattern:** `props:` wrapper or not?

3. **Match assertions:** Use regex for partial matches

4. **Race conditions:** Test double-clicks, rapid interactions

5. **SSR:** `sessionStorage`/`localStorage` should never be called in test (Node environment)

## A.5 Files to Modify

### ⚠️ LINE NUMBER DRIFT PROTECTION

**Format:** `Line ~XX (after: \`exact code snippet\`)`

**Why:** Line numbers drift. Text markers don't.

### File Name

**Path:** `path`

**Line ~XX** (after `marker code`)

```javascript
▶ ADD/REPLACE:
[code]
```

## A.6 Edge Cases & Error Handling

**⚠️ RED TEAM RULE:** Write EXACT error copy, not descriptions.

| Scenario               | Exact User-Facing Error                                | Handling Code                                         | Test?   |
| ---------------------- | ------------------------------------------------------ | ----------------------------------------------------- | ------- |
| API timeout            | "Failed to load. This is taking longer than expected." | `catch (err) { error = ERROR_MESSAGES.API_TIMEOUT; }` | ✅ test |
| Missing required field | (No user error - use default)                          | `title \|\| "Untitled"`                               | ✅ test |
| Document not found     | "Document not found. It may have been deleted."        | `if (!docExists) { log("[ERROR]..."); return; }`      | ✅ test |

**Format:** Exact copy + code snippet + test reference

### 🛡️ Universal Patterns

**State Drift:** Combine related state vars

**Destructive Actions:** Add confirmation

**Component Lifecycle:** Use CSS `.hidden` vs unmounting

**Error Recovery:** Try/catch localStorage, API calls

### ⚠️ EXTERNAL API/URL LIMITS

| Service           | Limit             | What Happens       |
| ----------------- | ----------------- | ------------------ |
| Gmail compose URL | ~8000 chars       | Silently truncated |
| Browser URL       | ~2000-16000 chars | May fail           |
| localStorage      | ~5MB              | QuotaExceededError |

## A.7 Implementation Order (Kent Beck TDD)

### ⚠️ PRE-IMPLEMENTATION CHECKPOINT

1. **Can this be simpler?** (YAGNI check)
2. **Do I understand the task?**
3. **Scope discipline** - What am I NOT touching?

### 🎯 TDD Cycle Pattern

| Phase           | Action                                |
| --------------- | ------------------------------------- |
| 🔴 **RED**      | Write failing test                    |
| 🟢 **GREEN**    | Make it pass (minimal)                |
| 🔄 **REFACTOR** | Clean up NOW                          |
| ✅ **VERIFY**   | YOU run tests, YOU check terminal.log |
| 🌐 **UI CHECK** | Ask Russell about UI only             |

### ⚠️ STOP - VERIFY BEFORE CONTINUING

**After EVERY cycle, YOU (Claude) must:**

1. **Run tests yourself:** `npm test -- [test-file]`
2. **Read terminal.log yourself** - Look for `[ERROR]` tags
3. **All tests pass?** ✅ Yes → Proceed | ❌ No → FIX FIRST
4. **Goal achieved?** Restate cycle goal - Does code actually do it? ✅ Yes → Proceed | ❌ No → DEBUG
5. **For UI cycles only:** Ask Russell about UI (NOT errors/tests)
6. **Update PROGRESS.md FIRST**
7. **Commit:** `git add -A && git commit -m "[Feature] - Cycle N"`

### Cycle 1: [Smallest testable unit]

**Goal:** [What this achieves]

| Phase | Action                                                          |
| ----- | --------------------------------------------------------------- |
| 🔴    | Test: `it('description')`                                       |
| 🟢    | Implement minimal code                                          |
| 🔄    | Refactor                                                        |
| ✅    | **YOU run tests, YOU check terminal.log, verify goal achieved** |
| 🌐    | Ask Russell: "Check browser - does [X] work?"                   |

**Files changed:** [list]
**Test command:** `npm test -- [file]`
**Commit:** `"Feature - Cycle 1: [desc]"`

**After cycle complete:** Create resume prompt for next cycle if cost is climbing.

### Cycle 2, 3, etc...

[Repeat pattern]

## A.8 Test Strategy

### CLI Testing for API Endpoints (FASTEST - 10x Speed)

**For /api/chat, /api/research, /api/orchestrate changes:**

```bash
# Test endpoint directly (10s vs 60s in browser)
npm run test:chat "your query"
npm run test:research "topic"
npm run test:orchestrate "complex query"

# Debug workflow
node scripts/query-logs.js --clear
npm run test:chat "query"
node scripts/query-logs.js KEYWORD
# Fix → test again → repeat
```

**When to use:**

- Testing streaming responses
- Validating SSE event structure
- Performance benchmarking
- YOU can test without Russell
- 10x faster iteration

**See [`plans/plan-61-cli-testing-mode.md`](plans/plan-61-cli-testing-mode.md) for full details**

### Frontend Bugs: Playwright TDD

```javascript
test("description", async ({ page }) => {
  await page.goto("http://localhost:5173");
  // ... interaction
  await expect(element).toHaveText("expected");
});
```

**Run Order:**

1. **CLI tests first** (if API endpoint changed)
2. `npm test -- [store-test]`
3. `npm test -- [component-test]`
4. `npm run test:ui -- [e2e-test]`
5. Browser manual test (last resort)

## A.9 Pre-Flight Checklist

- [ ] Every edge case has test or graceful handling
- [ ] Line numbers have text markers
- [ ] Test patterns match codebase
- [ ] TDD cycles are minimal

## A.10 Logging Strategy

**Tags:** `[TAG]` for this feature

**Key points:** Function entry, state changes, errors

## A.11 Browser Testing Protocol

1. Update PROGRESS.md FIRST
2. **Check terminal.log yourself** (MANDATORY)
3. Ask Russell about UI ONLY
4. Wait for confirmation

## A.12 Mopup Check (After EVERY Change)

Hunt dead code:

- State variables
- Imports
- Functions
- CSS

**Do this DURING, not at end.**

## A.13 Refactoring (CONTINUOUS)

### REFACTOR CHECKLIST (After Every GREEN)

1. **🧹 Clean:** Remove console.logs, unused vars
2. **📛 Names:** Rename unclear variables NOW
3. **♻️ DRY:** Extract duplicated code
4. **🗑️ DEAD CODE HUNT:** Delete replaced functions NOW

### Refactor Triggers

| Situation            | Action                |
| -------------------- | --------------------- |
| Same logic 2+ places | Extract function NOW  |
| Function >30 lines   | Break into smaller    |
| **File >300 lines**  | **STOP and simplify** |

## A.14 Integration Points

**Data contracts:**

| Producer | Consumer | Format  |
| -------- | -------- | ------- |
| [System] | [System] | [Shape] |

## A.15 ENV VARS

**Required:** [list or "None"]

## A.16 Vercel Deployment Verification

### SSR Guard Patterns

```javascript
// Pattern 1: Guard in $effect
$effect(() => {
  if (typeof ResizeObserver === "undefined") return;
  // ...
});

// Pattern 2: Use browser check
import { browser } from "$app/environment";
if (browser) {
  /* safe */
}
```

### Vercel Checklist

- [ ] Push branch → Vercel creates preview
- [ ] Check build errors
- [ ] Test on preview URL

**DO NOT merge until Vercel preview passes.**

## A.17 Success Criteria & Cleanup

**Complete when:**

- [ ] All tests pass
- [ ] Browser checklist complete
- [ ] terminal.log clean
- [ ] Mopup complete

**Post-Feature Cleanup:**

1. [ ] Get commit hash: `git log -1 --oneline`
2. [ ] Update log file with commit hash (newest first)
3. [ ] Update this plan - check off items, add lessons learned
4. [ ] **Update CODEBASE-REFERENCE.md** - Document new features/patterns/gotchas
5. [ ] Update baryo-spec.md - Move feature to ✅ DONE
6. [ ] Commit docs: `git add -A && git commit -m "docs: update plan/codebase-ref/spec" --no-verify`
7. [ ] Delete PROGRESS.md

**What to update in CODEBASE-REFERENCE.md:**

- New features: Add section with description, code examples, key patterns
- Bug fixes: Add to "Critical Gotchas" if tricky
- Refactoring: Update file paths, architecture diagrams, remove obsolete sections
- **Your work isn't done until CODEBASE-REFERENCE.md reflects the changes**

---

# TEMPLATE B: Small Plan (Bug Fixes & Tiny Features)

**Use for:** Bug fixes, small features (<200 lines, 1-2 files)

## B.1 🎯 THE PROBLEM

**What's broken or missing:** [1-2 sentences]

**Root Cause:** [Why current approach fails]

**Previous Attempts:**

1. [What was tried] → [Why it didn't work]

## B.2 🔧 THE FIX

**Key Insight:** [The "aha" moment]

### Architecture

```
┌─────────────────┐
│   User Action   │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│   Processing    │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│     Result      │
└─────────────────┘
```

**Why This Works:**

- [Reason 1]
- [Reason 2]

## B.3 📁 FILES INVOLVED

### New Files to Create

| File                | Purpose     |
| ------------------- | ----------- |
| `path/file.js`      | Description |
| `path/file.test.js` | Tests       |

### Files to Modify

| File               | Changes                 |
| ------------------ | ----------------------- |
| `path/existing.js` | What gets added/changed |

## B.4 🚨 EDGE CASES

| Scenario | Handling           |
| -------- | ------------------ |
| [Case 1] | [How we handle it] |
| [Case 2] | [How we handle it] |

## B.5 🎯 ERROR UX

**User Experience:**

- What user sees when it works
- What user sees when it fails
- Loading states (if any)

**Internal Logging:**

- Log tag: `[TAG_NAME]`
- What gets logged

**Degraded Mode (if applicable):**

- When it kicks in
- What still works

## B.6 🔄 INTEGRATION NOTES

**Key Points:**

- How this integrates
- Performance implications
- Breaking changes (if any)

**Flow:**

1. [Step 1]
2. [Step 2]
3. [Step 3]

## B.7 📋 IMPLEMENTATION STEPS

### Cycle 1: [Smallest unit] 🔴🟢🔄

| Step | Action                  |
| ---- | ----------------------- |
| 🔴   | Test: expect [behavior] |
| 🟢   | Implement minimal code  |
| 🔄   | Refactor: [cleanup]     |

**Verify:**

1. YOU run tests
2. YOU check terminal.log
3. **Goal achieved?** Does code actually do what cycle header says? ✅ Yes → Proceed | ❌ No → DEBUG

**Commit:** `"Fix/Feature - Cycle 1: [desc]"`

### Cycle 2: [Next unit] 🔴🟢🔄

[Same pattern]

### Cycle 3: [Integration] 🔴🟢🔄

| Step | Action                |
| ---- | --------------------- |
| 🔴   | E2E test: [scenario]  |
| 🟢   | Wire up components    |
| 🔄   | Clean up, add logging |

**Result:** Feature complete

## B.8 🧪 TESTING STRATEGY

**CLI Tests (if API endpoint):**

```bash
# Test endpoint changes directly (10x faster)
npm run test:chat "query"
npm run test:research "topic"

# Debug with logs
node scripts/query-logs.js --clear
npm run test:chat "query"
node scripts/query-logs.js KEYWORD
```

**Unit Tests:**

```bash
npm test -- path/to/file.test.js
```

**Browser Testing:**

1. [Scenario to test]
2. [Another scenario]
3. [Edge case]

**Success Criteria:**

- [ ] CLI tests pass (if API endpoint)
- [ ] All unit tests pass
- [ ] Browser scenarios work
- [ ] terminal.log clean

**See [`plans/plan-61-cli-testing-mode.md`](plans/plan-61-cli-testing-mode.md) for CLI testing details**

---

# TEMPLATE C: Refactoring/Migration

**Use for:** Renaming, restructuring, migrations (existing tested logic)

## C.0 Pre-Implementation Checklist (RED TEAM PREVENTION)

**BEFORE writing the plan, complete these to prevent AI errors:**

### C.0.1 Codebase Syntax Check

**Read actual files to verify current patterns:**

```markdown
- [ ] Read target component files - what's the actual event binding? (`onclick` vs `on:click`)
- [ ] Check Svelte version - Are we using runes ($state) or stores?
- [ ] Check loop variable names in similar components
- [ ] Check CSS class patterns used elsewhere
- [ ] Verify import patterns (default vs named)
```

**Example: Before planning ViewModeToggle changes, READ the file to see:**

- Current: `onclick={() => mode = m.id}` (Svelte 5)
- NOT: `on:click={() => mode = mode.id}` (Svelte 4)
- Loop var: `m`, NOT `mode` (avoids shadowing)

### C.0.2 Write Actual Test Code (Not Wishes)

**In the plan, include COMPLETE test code:**

```javascript
// ✅ GOOD - Copy-paste ready
describe("DeskView", () => {
  it("prevents double-click race condition", async () => {
    const mockNavigate = vi.fn();
    render(DeskView, { props: { onNavigateToWork: mockNavigate } });

    const button = screen.getByText(/test/i);
    await fireEvent.click(button);
    await fireEvent.click(button); // Double click

    expect(mockNavigate).toHaveBeenCalledTimes(1); // Should debounce
  });
});

// ❌ BAD - Vague wish
// "Test that double-clicks are prevented"
```

### C.0.3 CSS Specs Table (Exact Classes)

**Create table with EXACT Tailwind classes:**

| Element   | State    | Light Mode                                        | Dark Mode                |
| --------- | -------- | ------------------------------------------------- | ------------------------ |
| Container | Default  | `bg-gray-50 min-h-screen p-6`                     | `dark:bg-gray-900`       |
| Button    | Hover    | `hover:bg-blue-700`                               | `dark:hover:bg-blue-600` |
| Button    | Disabled | `disabled:opacity-50 disabled:cursor-not-allowed` | (same)                   |

**NO VAGUE SPECS like "make it match the app" - write the classes.**

### C.0.4 Race Condition Analysis

**For EVERY user interaction, ask:**

| Question                                    | Code Prevention           |
| ------------------------------------------- | ------------------------- |
| What if they double-click?                  | Debounce with lock flag   |
| What if API is in-flight during navigation? | AbortController           |
| What if rapid mode switches?                | Cleanup in $effect return |
| What if auto-create runs twice?             | Lock flag check           |

**Include prevention CODE in plan, not just description.**

### C.0.5 Data Contracts (JSDoc + Examples)

**Write JSDoc AND example objects:**

```javascript
/**
 * @typedef {Object} DeskAction
 * @property {'prep-doc'|'draft-reply'|'open-doc'} type
 * @property {string} [title] - Doc title (for prep-doc)
 */

// Example object:
const validAction = {
  type: "prep-doc",
  title: "Meeting notes",
};
```

### C.0.6 Exact Error Message Strings

**Write the ACTUAL user-facing copy:**

```javascript
const ERROR_MESSAGES = {
  API_TIMEOUT: "Failed to load your desk. This is taking longer than expected.",
  NO_AUTH: "Please sign in to see your personalized desk.",
  // NOT: "show error message" (too vague)
};
```

### C.0.7 Edge Cases with Exact Handling

| Scenario             | Exact Error Copy                                | Handling Code                              |
| -------------------- | ----------------------------------------------- | ------------------------------------------ |
| Missing action.title | (No error - use default)                        | `action.title \|\| "Untitled"`             |
| Document not found   | "Document not found. It may have been deleted." | Check `docExists`, log error, return early |

**NO VAGUE "handle gracefully" - write the code.**

## C.1 Observations

[What currently exists - where files are, how they're structured]

**Current state:** [Describe existing implementation]

**Goal:** [What we want to achieve with refactoring]

## C.2 Approach

[Phase-based breakdown]

1. **Phase 1:** [e.g., Rename all references]
2. **Phase 2:** [e.g., Move to new structure]
3. **Phase 3:** [e.g., Cleanup old code]
4. **Phase 4:** [e.g., Polish and verify]

## C.3 Phase 1: [Name]

**Goal:** [What this phase achieves]

### 1.1 [Specific task]

**Action:**

```bash
git mv old/path new/path
```

**Then update file internally:**

- `oldName` → `newName`
- Update imports
- Update references

**Add logging:**

```javascript
log("[TAG] newName initialized");
```

### 1.2 [Next task]

[Similar structure]

### 1.3 Verify Tests Pass

```bash
npm test -- [affected-tests]
```

**Verify checklist:**

1. **Check terminal.log yourself** - look for errors
2. **Tests pass?** ✅ Yes → Proceed | ❌ No → FIX FIRST
3. **Phase goal achieved?** Restate what Phase 1 should accomplish - did it? ✅ Yes → Proceed | ❌ No → DEBUG

**Fix any failures BEFORE proceeding.**

### 1.4 Mopup Check (Phase 1)

Hunt for dead code after rename:

- Old imports still referenced?
- Old test files exist?

**Search:**

```bash
# Use search_files tool
# Pattern: "oldName|oldImport"
```

### 1.5 Commit Phase 1

```bash
git add -A
git commit -m "Phase 1: [Description]

- [Change 1]
- [Change 2]
- All tests passing
"
```

**Update PROGRESS.md** - move Phase 1 to completed

### 1.6 Resume Prompt (Cost Savings)

**Create `RESUME-[FEATURE]-PHASE2.md`:**

```markdown
Read plans/plan-[N].md for full context.

Continue [Feature] - Phase 2.

**Branch:** feature/[name]
**Status:** ✅ Phase 1 complete, tests passing, committed
**Next:** Phase 2 (lines X-Y) - [description]

Start with Phase 2 Section 2.1 now.
```

**Tell Russell:** "Phase 1 complete. Start fresh with RESUME file to save ~$0.60."

## C.4 Phase 2: [Name]

**Goal:** [What this achieves]

### 2.1 [Task]

[Similar structure to Phase 1]

### 2.2 SSR Guards (If Applicable)

**Check for browser API usage:**

```javascript
import { browser } from "$app/environment";

$effect(() => {
  if (!browser) return;
  // Safe to use sessionStorage, localStorage, window
});
```

### 2.3 Verify Tests Pass

```bash
npm test
```

**Verify checklist:**

1. **Check terminal.log** for errors
2. **Tests pass?** ✅ Yes → Proceed | ❌ No → FIX FIRST
3. **Phase goal achieved?** Restate what Phase 2 should accomplish - did it? ✅ Yes → Proceed | ❌ No → DEBUG

### 2.4 Browser Test (First UI Check!)

**Update PROGRESS.md FIRST**

**Ask Russell:**

- "Check browser - does [X] appear correctly?"
- "Does clicking [Y] work?"
- **NEVER ask:** "Are there errors?" (YOU check terminal.log)

### 2.5 Mopup Check (Phase 2)

### 2.6 Commit Phase 2

### 2.7 Resume Prompt

## C.5 Phase 3: [Cleanup]

**Goal:** Remove old code, update references

### 3.1 Remove Old Routes/Files

```bash
rm path/to/old/file
```

### 3.2 Update All References

Use search_files to find and update:

- Old route references
- Old import paths
- Old cache keys

### 3.3 Verify No Stray References

**Search pattern:** `"oldRoute|oldImport"`

Should find ZERO results.

### 3.4 Verify Tests Pass

```bash
npm test
```

**Verify checklist:**

1. **Check terminal.log** for errors
2. **Tests pass?** ✅ Yes → Proceed | ❌ No → FIX FIRST
3. **Phase goal achieved?** Old code removed, no stray references? ✅ Yes → Proceed | ❌ No → DEBUG

### 3.5 Mopup Check (Phase 3)

### 3.6 Commit Phase 3

## C.6 Phase 4: Polish

**Goal:** Final styling, docs, full testing

### 4.1 Styling Consistency

Ensure new components match existing:

- Background colors
- Button styles
- Responsive layout

### 4.2 Update Documentation

**Update CODEBASE-REFERENCE.md:**

Add new section for refactored code.

### 4.3 Full Feature Browser Test

**Test checklist:**

- [ ] Feature loads correctly
- [ ] All interactions work
- [ ] Refresh persists state
- [ ] Error states work

**Ask Russell after EACH scenario**

### 4.4 Vercel Preview Test

```bash
git push origin feature/[name]
```

**Verify:**

- Build successful
- Preview URL works
- No SSR errors

**DO NOT merge until Vercel passes.**

### 4.5 Mopup Check (Final)

Hunt ALL dead code:

- Unused imports
- Old references
- Dead CSS classes

**Remove everything found.**

### 4.6 Final Commit

### 4.7 Merge to Main

**Verify:**

- [ ] All tests pass
- [ ] Vercel preview works
- [ ] Russell confirmed browser tests

**Merge:**

```bash
git checkout main
git merge feature/[name]
git push origin main
git branch -d feature/[name]
```

## C.7 Post-Feature Cleanup

1. [ ] Update log file with commit hash
2. [ ] Update this plan - check off items, add lessons learned
3. [ ] **Update CODEBASE-REFERENCE.md** - Document refactored structure, new paths, updated patterns
4. [ ] Update baryo-spec.md - Move to ✅ DONE
5. [ ] Commit docs: `git add -A && git commit -m "docs: update plan/codebase-ref/spec" --no-verify`
6. [ ] Delete PROGRESS.md

**What to update in CODEBASE-REFERENCE.md after refactoring:**

- Update file paths (old → new locations)
- Update architecture diagrams if structure changed
- Remove obsolete sections
- Add migration notes if breaking changes
- Document new naming conventions

## C.8 Logging Strategy

**Tags:** `[TAG]` for this refactoring

**Key log points:**

- Initialize new names
- State changes
- Errors

## C.9 Edge Cases

| Scenario | What Happens | Test?    |
| -------- | ------------ | -------- |
| [Case]   | [Behavior]   | ✅/🔧/❌ |

## C.10 Success Criteria

**Complete when:**

- [ ] All phases complete
- [ ] Tests passing
- [ ] Browser tests confirmed
- [ ] Vercel preview works
- [ ] No dead code
- [ ] Merged to main

---

## 📎 QUICK REFERENCE: Which Template?

**"I'm adding a new feature that doesn't exist yet"**
→ Is it >200 lines? YES = Template A | NO = Template B

**"I'm fixing a bug in existing code"**
→ Is the fix >200 lines? Unlikely - use Template B

**"I'm renaming, moving, or restructuring existing code"**
→ Template C (Refactoring/Migration)

**"I'm not sure which to use"**
→ Start with Template B (Small Plan)
→ Escalate to Template A if it grows beyond 200 lines

**Still confused?**
→ Ask Russell: "This task is [X]. Should I use Template A, B, or C?"
