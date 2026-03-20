---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git push:*), Bash(git log:*), Bash(git diff:*), Bash(git checkout:*), Bash(git merge:*), Bash(git branch:*), Read, Edit, Glob, Grep
description: Commit and push directly to master (solo dev — no branches, no PRs)
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## Your task

Solo dev workflow — no branches, no PRs. Based on the above changes:

### Step 1: End of Feature Checklist (verify before committing)

Check the diff above and confirm each item. If any are missing, do them now before committing:

1. **README updated?** — if public API changed (new connector, new method, new policy), README must reflect it
2. **SPEC updated?** — if a roadmap item was completed, mark it ✅ in SPEC.md
3. **Handoff.md updated?** — must include what was done this session and the exact next task
4. **Dead code deleted?** — any stale files, unused imports, or commented-out code to remove?

### Step 2 — Check what changed

Look at recent commits and the current diff to understand what's actually new or updated in this session. Use `git log --oneline -10` and `git diff HEAD` as your source of truth.

### Step 3 — Update the intent file, SPEC, and README

Read the project's intent file (e.g. `enact-intent.md`) and compare it against what changed. Update it if you:
- Added a new state variable — add it.
- Changed how an action works — update it.
- Deleted something — remove it.

The spec must always reflect current reality, not aspirational reality.

### Step 4 — Flag any drift you notice

While reading the spec vs the code, call out anything that looks inconsistent. Do not silently fix it — surface it first.

Example: "spec says `researches` only changes in `startResearch` action but I see it's also updated in `realtime_sub.py` line 34 — should I add that to the spec?"

Post any drift findings in the chat before proceeding.

### Step 5: Commit and push

5. Stage the relevant changed/untracked files (prefer specific file names over `git add -A`)
6. Create a single commit with an appropriate message on the current branch

### Step 6: Merge to master and push

7. If on a feature branch (not `master`):
   - `git checkout master`
   - `git merge <feature-branch> --no-edit`
   - `git push origin master`
   - Then push the backup remote if configured: `git push backup master`
8. If already on `master`:
   - `git push origin master`
   - Then push the backup remote if configured: `git push backup master`

You have the capability to call multiple tools in a single response. Do not create branches. Do not create pull requests.
