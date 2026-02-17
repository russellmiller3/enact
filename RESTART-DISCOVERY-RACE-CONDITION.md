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
[-] **Race condition in SSE event handlers - agents render out of order**

## CURRENT ISSUE:
❌ SSE event handlers execute out of order. User sees: Discovery → Notify → Provision → Intake → Policy (random order)

**What WORKS:**
- Backend sends events in correct order: discovery → intake → policy → provision → notify → audit → done (confirmed in `backend/workflow.py` lines 39-160)
- Discovery card renders with all matched datasets, scores, keywords
- Stepper shows all 5 steps
- "5 agents" text correct everywhere

**What DOESN'T WORK:**
- Frontend event handlers are all `async` functions with `await sleep()` calls for animations
- When SSE events arrive while a previous handler is still animating, the new handler starts in parallel
- Result: agents render in random order instead of sequential

**What was tried:**
- Added `queueHandler` pattern (promise chain) to wrap all event listeners
- Syntax is now correct (all 7 handlers wrapped), but agents still render out of order
- The queueHandler approach should theoretically work but doesn't in practice

## ROOT CAUSE ANALYSIS:

The `queueHandler` pattern chains promises:
```javascript
let handlerQueue = Promise.resolve();
function queueHandler(fn) {
  handlerQueue = handlerQueue.then(fn).catch(err => console.error('Handler error:', err));
}
```

Each SSE event handler calls `queueHandler(async () => { ... })` instead of being `async (e) => { ... }` directly.

**Possible reasons it's not working:**
1. The `handlerQueue` variable might not be shared properly between handlers (scope issue)
2. The `tl` (timeline) variable is captured in closure from `runWorkflow()` - should be fine but worth checking
3. Maybe the `return` statement in the provision handler (for skipped provisioning) breaks the chain
4. **Most likely**: Check browser console for errors - if any handler throws, the chain breaks

## NEXT ACTIONS:

1. Open browser console (F12) and run workflow - look for JavaScript errors
2. If queueHandler errors: the promise chain is breaking on an exception
3. **Alternative approach - Event Buffer**: Instead of queueHandler, use an event buffer:
   ```javascript
   const eventQueue = [];
   let processing = false;
   
   function enqueueEvent(type, data) {
     eventQueue.push({type, data});
     if (!processing) processQueue();
   }
   
   async function processQueue() {
     processing = true;
     while (eventQueue.length > 0) {
       const {type, data} = eventQueue.shift();
       await handleEvent(type, data);
     }
     processing = false;
   }
   ```
4. Each SSE listener just calls `enqueueEvent('discovery', JSON.parse(e.data))`
5. `handleEvent()` has a switch statement calling the appropriate render function
6. Test: Discovery → Intake → Policy → Provision → Notify in correct order

## KEY FILES:

- `frontend/workflow.html` - THE main file (SSE-wired, currently broken race condition)
  - Lines 315-326: Stepper HTML (5 steps: DISCOVERY → INTAKE → POLICY → PROVISION → NOTIFY)
  - Lines 909-913: `queueHandler` definition
  - Lines 938-1075: Discovery event handler (renders matched datasets card)
  - Lines 1077-1148: Intake event handler
  - Lines 1150-1231: Policy event handler
  - Lines 1233-1301: Provision event handler
  - Lines 1303-1353: Notify event handler
  - Lines 1355-1362: Audit event handler
  - Lines 1364-1472: Done event handler
  
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

## DONE WHEN:
1. Click "Run Workflow" → agents render in order: Discovery → Intake → Policy → Provision → Notify
2. Each agent card appears AFTER the previous one finishes animating
3. Discovery card shows all matched datasets with scores
4. No JavaScript errors in console
5. Git commit with message: "fix: sequential SSE event rendering with event buffer"

Start by opening browser console at http://localhost:8000, run workflow, and check for JavaScript errors that might explain why queueHandler isn't working. If errors found, fix them. If no errors, switch to event buffer approach.
