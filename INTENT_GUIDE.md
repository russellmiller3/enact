# INTENT_GUIDE.md
# Instructions for Claude — how to bootstrap, maintain, and use the .intent spec for this repo.
# Read this file at the start of every session before touching any code.

---

## What this system is

This repo uses a lightweight spec file (the `.intent` file) as a canonical map of the application.

The spec is not documentation. It is not generated code.
It is a living description of WHAT IS TRUE about the app:
- Every piece of reactive state
- Every derived value and what it depends on
- Every named way state is allowed to change
- Every I/O boundary
- The complete data model

The spec exists for one reason: **so Claude can hold the full mental model of the app in one read, every session, without reconstructing it from code.**

---

## Who you're working with

Russell Miller. Solo dev. ADHD + Mito disease (limited daily energy).
- Be terse. Short sentences. High signal.
- Don't re-explain things he knows.
- Maximize output per unit of his energy.
- He is the strategic brain. You are the execution and memory.
- When you hold context correctly, he ships. When you don't, he burns out re-explaining.

---

## Every session — do these four steps first

### Step 1 — Read the .intent file
Find the `.intent` file in the repo root (e.g. `baryo.intent`, `cast.intent`).
Read it completely before reading any other file.
This gives you the full mental model of the app.

### Step 2 — Ask what changed
Say exactly this: "I've read the spec. What changed since last time?"
Wait for Russell's answer before proceeding.
Do not assume nothing changed.

### Step 3 — Update the spec
Reflect his answer in the `.intent` file before writing any code.
If he added a new state variable — add it.
If he changed how an action works — update it.
If he deleted something — remove it.
The spec must always reflect current reality, not aspirational reality.

### Step 4 — Flag any drift you notice
While reading the spec vs the code, flag anything that looks inconsistent.
Example: "spec says `researches` only changes in `startResearch` action
         but I see it's also updated in `realtime_sub.py` line 34 —
         should I add that to the spec?"
Do this before starting the requested work, not after.

---

## If no .intent file exists — bootstrap it

Do this exactly once. Takes 30–45 minutes.
The goal: extract the spec from the existing code, not write it from scratch.

### What to ask Russell for

Ask him to paste these — you don't need the whole codebase, just these:

```
1. DB schema or ORM models       → gives you shapes
2. State management files         → gives you state + derives
   (Svelte stores, Zustand, etc)
3. Main route/handler files       → gives you actions + effects
4. One example end-to-end flow    → validates your understanding
   e.g. "user starts a research run — what happens?"
```

### How to write the spec from those files

Read everything he pasted. Then write the `.intent` file in this order:

**1. Invariants first (SDK/library only)** — what does this system guarantee?
Look for things that are ALWAYS true regardless of code path.
Examples: "a receipt is always written," "all validators run, never short-circuit."
These are the promises callers rely on. If any break, it's a bug.
Skip this section for pure UI apps — it's mainly valuable for libraries and APIs.

**2. Error contracts second (SDK/library only)** — what can blow up?
For each public method, list what exceptions it raises and when.
Extract from `raise` statements and guard clauses in the code.
Format: `ClassName.method()` / `raises ExceptionType — condition`
Skip for UI apps — errors there live in effects and action handlers.

**3. Shapes** — what real-world things exist as data?
Extract from DB schema / ORM models.
One shape per entity. Fields and types only. No methods.

**4. State** — what can change in the app?
Extract from stores / session state / component state that matters.
Ignore local UI state (hover, focus, tooltip open) — only state that affects business logic.
For SDKs: this is the client config + any mutable runtime state.

**5. Derives** — what values follow automatically from state?
Look for computed properties, getters, memoized selectors.
Write as: `derive name = expression`

**6. Actions** — how is state allowed to change?
Look for store mutations, API call handlers, event handlers that update state.
Name them as verbs: `startResearch`, `receiveChunk`, `markDone`
Include the guard if there is one: `guard isMember`

**7. Effects** — what I/O happens?
Look for fetch calls, API calls, external service calls.
Map each one: what triggers it, what action handles success, what handles error.

**8. Open questions last** — anything you're unsure about
Write these explicitly. Russell will correct them.
Better to flag uncertainty than silently guess wrong.

### After writing it

Read it back to Russell as a summary:
"Here's what I understood — N shapes, N state vars, N actions, N effects.
The parts I'm uncertain about are X, Y, Z."

Let him correct it. Update the file. Now it's live.

---

## The .intent file format

Plain text. No special tooling required. Readable by any Claude.

```
// ── APP NAME ──────────────────────────────────────────────
// One line description of what this app does.

// ── INVARIANTS ────────────────────────────────────────────
// Promises the system always keeps. If any break, it's a bug.
// Most useful for SDKs/libraries. Optional for UI-only apps.

// 1. Statement of a guarantee the system makes.
// 2. Another guarantee. Be specific — name the code path.

// ── ERROR CONTRACTS ───────────────────────────────────────
// What each public method raises and when. Callers catch these.
// Most useful for SDKs/libraries. Optional for UI-only apps.

// ModuleName.method()
//   raises ExceptionType — when this condition is true

// ── SHAPES ────────────────────────────────────────────────
// The data model. Real-world things that exist.

shape Name {
  field : Type
  field : Type = default
  field : Type?              // nullable
}

// ── STATE ─────────────────────────────────────────────────
// Everything that can change. Single source of truth.

state name : Type = default
state name : List<Shape> = []
state name : Enum(a | b | c) = a
state name : Type? = null

// ── DERIVES ───────────────────────────────────────────────
// Truths that follow from state. Never stale.

derive name = expression
derive name = state.where(x => condition)
derive name = state[id]

// ── ACTIONS ───────────────────────────────────────────────
// The only ways state is allowed to change.
// Named. Guarded. Complete.

action name {
  guard condition
  state = newValue
  list += Item(...)
  list -= id
}

action name(param: Type) {
  guard condition
  state[id].field = value
}

// ── EFFECTS ───────────────────────────────────────────────
// I/O boundaries. Always triggered from actions.

effect name(param: Type) {
  GET /path/to/endpoint       // or POST, PUT, PATCH, DELETE
  on success => action successAction
  on error   => action errorAction
}

// ── OPEN QUESTIONS ────────────────────────────────────────
// Things that are uncertain, unresolved, or in flux.
// Update or remove as they get resolved.

// Q: Is X implemented or still TODO?
// Q: Does Y need to handle the null case?
```

---

## Drift detection — how to do it manually

You cannot fully automate this without a compiler. Do it manually each session.

When you read the spec and then look at code, ask:

1. **Mutation check** — does any state variable get assigned outside its declared actions?
   Search for `stateName =` across all files. Flag anything outside action handlers.

2. **Action completeness** — are there route handlers or store mutations not in the spec?
   Skim the main routes file and stores file. Flag anything unnamed in the spec.

3. **Shape drift** — does the DB schema match the shapes in the spec?
   Compare field names and types. Flag mismatches.

4. **Effect orphans** — are there fetch/API calls not mapped to a declared effect?
   Flag them.

Report drift before starting the requested work:
"Before we start — I noticed 2 drift issues: [X] and [Y]. Should I update the spec first?"

Always update the spec before writing new code.
A stale spec is worse than no spec.

---

## What the spec is NOT

- Not executable code
- Not a compiler input (yet)
- Not a replacement for tests
- Not documentation for users
- Not aspirational / future state

It is a snapshot of current truth.
Keep it honest. Keep it current. Keep it short.

---

## The one rule

**If you're about to write code that changes state in a way not described in the spec —
update the spec first. Then write the code.**

This one rule, followed consistently, makes the spec worth having.

---

*INTENT_GUIDE.md — part of the INTENT language project*
*github.com/[russell]/intent*
