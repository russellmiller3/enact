# RESTART: Fix Discovery Agent Race Condition

STOP! READ /.ROO/.ROORULES

**REFERENCE FILES (read first, in order):**
1. This file - current status
2. `backend/README.md` - architecture overview (5 agents, SSE flow)
3. `frontend/workflow-backup-sse.html` - backup of current SSE-wired version

**BRANCH:** master
**COST SO FAR:** $13.30

---

## COMPLETED:
✅ Added Discovery step to stepper progress bar (DISCOVERY → INTAKE → POLICY → PROVISION → NOTIFY)
✅ Added Discovery timeline card showing all matched datasets with scores, keywords, selected indicator
✅ Updated "4 agents" → "5 agents" everywhere (hint text, result stats, reset text)
✅ Added 7 more fake datasets to `backend/config/datasets.json` (now 11 total)
✅ Updated `backend/README.md` to reflect correct agent order and dataset count
✅ Fixed Windows UTF-8 encoding in `backend/server.py`
[✅] **Race condition in SSE event handlers - FIXED**

## FIXED ISSUE (was):
~~SSE event handlers execute out of order. User sees random order~~

**What WORKS:**
- Backend sends events in correct order: discovery → intake → policy → provision → notify → audit → done (confirmed in `backend/workflow.py` lines 39-160)
- Discovery card renders with all matched datasets, scores, keywords
- Stepper shows all 5 steps
- "5 agents" text correct everywhere

**What DOESN'T WORK:**
- Frontend event handlers are all `async` functions with `await sleep()` calls for animations
- When SSE events arrive while a previous handler is still animating, the new handler starts in parallel
- Result: agents render in random order instead of sequential

**What was tried (and what actually worked):**
- Added `queueHandler` pattern (promise chain) to wrap all event listeners
- Syntax was correct (all 7 handlers wrapped), but agents still rendered out of order
- **Root cause:** `EventSource.onerror` fired when server naturally closed SSE stream after last event
- The `onerror` handler showed `alert()` which BLOCKED the JavaScript thread, killing the queueHandler promise chain
- Events 3-7 (policy, provision, notify, audit, done) arrived fast after intake, and `onerror` fired before they could process

**Fix applied (3 lines):**
1. Added `receivedDone` flag inside `runWorkflow()`
2. In `done` event listener: set `receivedDone = true` + `eventSource.close()` BEFORE queueHandler
3. In `onerror`: skip error handling if `receivedDone` is true (normal stream end, not error)
4. Bonus: reset `handlerQueue = Promise.resolve()` at start of each run
5. Bonus: fixed `total_duration_ms` → `total_ms` field name mismatch in done handler

## ROOT CAUSE:

The `queueHandler` pattern was CORRECT all along. The real bug was `EventSource.onerror`:

```
When backend finishes sending all 7 SSE events, it closes the HTTP connection.
EventSource interprets connection closure as an ERROR and fires onerror.
onerror handler called alert() which BLOCKS the JavaScript main thread.
The remaining promise chain callbacks (for policy → notify) never executed.
```

The fix: detect when "done" event arrives, close EventSource from client side FIRST,
and skip onerror if we already got the done event.

## KEY FILES:

- `frontend/workflow.html` - THE main file (SSE-wired, FIXED!)
  
- `frontend/workflow-backup-sse.html` - BACKUP of current state (safe copy)
- `frontend/workflow-backup-mock-only.html` - OLD mock version (NO SSE, do NOT use)
- `frontend/workflow-fixed-base.html` - another backup (copy of mock-only, ignore)

- `backend/workflow.py` - Backend workflow (sends events in correct order, this is fine)
- `backend/config/datasets.json` - 11 datasets (this is fine)
- `backend/server.py` - FastAPI server with UTF-8 fix (this is fine)

## IMPORTANT NOTES:
- `workflow.html` IS the SSE-wired version. Do NOT copy from `workflow-backup-mock-only.html`
- `workflow-backup-mock-only.html` has NO SSE - it's the old mock-data-only version
- The backend is working correctly. Only the frontend event ordering is broken.
- The stepper, Discovery card design, dataset display - all GOOD. Just the execution ORDER is wrong.

## DONE ✅
1. ✅ Click "Run Workflow" → agents render in order: Discovery → Intake → Policy → Provision → Notify
2. ✅ Each agent card appears AFTER the previous one finishes animating
3. ✅ Discovery card shows all matched datasets with scores
4. ✅ No JavaScript errors in console
5. ✅ Fixed `total_ms` field name (was `total_duration_ms`, showed wrong time)
6. [ ] Git commit with message: "fix: sequential SSE event rendering - prevent onerror from killing handler queue"
