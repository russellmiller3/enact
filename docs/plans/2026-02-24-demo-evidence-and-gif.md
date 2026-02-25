# Demo Evidence + Terminal GIF Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `examples/demo.py` self-evidently convincing by showing actual row data and receipt evidence (answer "how do they know?"), then record it as an embeddable terminal GIF for the landing page.

**Architecture:** Two changes to the existing `examples/demo.py` output (no connector logic changes), plus a VHS `.tape` file to produce a reproducible GIF, plus one HTML embed on `landing_page_v2.html`. No new dependencies in the SDK itself — VHS is a standalone CLI tool used only for recording.

**Tech Stack:** Python 3.9+ (existing), VHS (Charmbracelet CLI tool for terminal GIF recording), HTML/CSS for landing page embed.

---

## Existing Code to Read First

| File | Why |
|---|---|
| `examples/demo.py` | The demo we're modifying — understand all print helpers and the Act 3 flow |
| `enact/rollback.py` | How rollback dispatches — what `rollback_data` looks like for `delete_row` |
| `enact/models.py` | `ActionResult.rollback_data` shape, `Receipt` fields |
| `enact/receipt.py` | `load_receipt()` — used to show receipt evidence |
| `landing_page_v2.html` | Where the GIF will be embedded |

---

## Task 1: Add row-level evidence to Act 3 output

**Files:**
- Modify: `examples/demo.py` — the Act 3 section of `run_demo()` (around lines 348–411)

**What we're adding:** After the delete happens and before the rollback, show:
1. The actual customer rows that were deleted (names, emails, ARR) — pulled from the receipt's `rollback_data`
2. A one-liner about the receipt capturing them at deletion time
3. After the rollback, a live verification query showing the rows are back

### Step 1: Write the evidence display code

In `examples/demo.py`, find the "Wait. Those were live customer accounts" section (around line 389). We need to insert the evidence display between the horror moment and the rollback command.

**Find this block** (around lines 389-400):
```python
    print(f"  {Y}{B}⚠  Wait. Those were live customer accounts.{RST}")
    print(f"  {Y}⚠  {rows_deleted} records gone. ${ rows_deleted * 14400:,} ARR just disappeared from the CRM.{RST}")
    print()

    time.sleep(0.5)

    print(f"  {DIM}enact.rollback(\"{receipt3.run_id[:8]}...\"){RST}")
    print()

    _, rollback_receipt = enact3.rollback(receipt3.run_id)

    print(f"  {B}Rollback:{RST}")
    _print_rollback_actions(rollback_receipt.actions_taken)
```

**Replace with:**
```python
    print(f"  {Y}{B}⚠  Wait. Those were live customer accounts.{RST}")
    print(f"  {Y}⚠  {rows_deleted} records gone. ${ rows_deleted * 14400:,} ARR just disappeared from the CRM.{RST}")
    print()

    # Show what was deleted — pull from the receipt's rollback_data
    delete_action = next(
        (a for a in receipt3.actions_taken if a.action == "delete_row"), None
    )
    if delete_action and delete_action.rollback_data.get("deleted_rows"):
        deleted_rows = delete_action.rollback_data["deleted_rows"]
        print(f"  {B}What was deleted{RST} {DIM}(captured in receipt at deletion time):{RST}")
        for row in deleted_rows:
            name = row.get("name", "?")
            email = row.get("email", "?")
            arr = row.get("arr_usd", 0)
            print(f"    {R}x{RST}  {name}  ·  {email}  ·  ${arr:,} ARR")
        print(f"  {DIM}Stored in receipts/{receipt3.run_id[:8]}...json · HMAC-SHA256 signed{RST}")
        print()

    time.sleep(0.5)

    print(f"  {DIM}enact.rollback(\"{receipt3.run_id[:8]}...\"){RST}")
    print()

    _, rollback_receipt = enact3.rollback(receipt3.run_id)

    print(f"  {B}Rollback:{RST}")
    _print_rollback_actions(rollback_receipt.actions_taken)
```

### Step 2: Add post-rollback verification query

After the rollback actions print, add a live `select_rows` check to prove the rows are actually back. This is the "how do they know?" answer — we query the database and show results.

**Find this block** (around lines 406-411):
```python
    print(f"  {B}Rollback:{RST}")
    _print_rollback_actions(rollback_receipt.actions_taken)
    print()
    color = G if rollback_receipt.decision in ("PASS", "PARTIAL") else R
    print(f"  {B}Decision:{RST} {color}{rollback_receipt.decision}{RST}  ·  {rows_deleted} customer records restored.")
    print(f"  {DIM}receipts/{rollback_receipt.run_id[:8]}...json  (rollback receipt, signed){RST}")
```

**Replace with:**
```python
    print(f"  {B}Rollback:{RST}")
    _print_rollback_actions(rollback_receipt.actions_taken)
    print()

    # Verify: query the database to prove the rows are actually back
    verify = pg.select_rows(table="customers", where={"status": "inactive"})
    restored_rows = verify.output.get("rows", [])
    if restored_rows:
        print(f"  {B}Verified{RST} {DIM}(live query after rollback):{RST}")
        for row in restored_rows:
            name = row.get("name", "?")
            email = row.get("email", "?")
            print(f"    {G}✓{RST}  {name}  ·  {email}  ·  {G}back{RST}")
        print()

    color = G if rollback_receipt.decision in ("PASS", "PARTIAL") else R
    print(f"  {B}Decision:{RST} {color}{rollback_receipt.decision}{RST}  ·  {rows_deleted} customer records restored.")
    print(f"  {DIM}receipts/{rollback_receipt.run_id[:8]}...json  (rollback receipt, signed){RST}")
```

### Step 3: Run demo to verify it works

Run: `python examples/demo.py`

Expected Act 3 output should now include:

```
  ⚠  Wait. Those were live customer accounts.
  ⚠  5 records gone. $72,000 ARR just disappeared from the CRM.

  What was deleted (captured in receipt at deletion time):
    x  Customer 043  ·  customer43@example.com  ·  $46,400 ARR
    x  Customer 044  ·  customer44@example.com  ·  $47,200 ARR
    x  Customer 045  ·  customer45@example.com  ·  $48,000 ARR
    x  Customer 046  ·  customer46@example.com  ·  $48,800 ARR
    x  Customer 047  ·  customer47@example.com  ·  $49,600 ARR
  Stored in receipts/88f6ff6c...json · HMAC-SHA256 signed

  enact.rollback("88f6ff6c...")

  Rollback:
    ✓  rollback_delete_row  →  REVERSED  ·  5 rows restored

  Verified (live query after rollback):
    ✓  Customer 043  ·  customer43@example.com  ·  back
    ✓  Customer 044  ·  customer44@example.com  ·  back
    ✓  Customer 045  ·  customer45@example.com  ·  back
    ✓  Customer 046  ·  customer46@example.com  ·  back
    ✓  Customer 047  ·  customer47@example.com  ·  back

  Decision: PASS  ·  5 customer records restored.
```

### Step 4: Run full test suite

Run: `pytest tests/ -v`

Expected: All 163 tests still pass. We only changed print output — no logic changes.

### Step 5: Commit

```bash
git add examples/demo.py
git commit -m "feat: add row-level evidence to demo Act 3 (deleted rows + verification query)"
```

---

## Task 2: Install VHS and create the recording tape file

**Files:**
- Create: `examples/demo.tape` — VHS script that records demo.py running

VHS is a CLI tool from Charmbracelet that records terminal sessions as GIFs from a declarative `.tape` file. Reproducible, scriptable, no manual recording needed.

### Step 1: Install VHS

On Windows, install via scoop or download the binary:

```bash
# Option A: scoop
scoop install vhs

# Option B: winget
winget install charmbracelet.vhs

# Option C: go install (if Go is installed)
go install github.com/charmbracelet/vhs@latest
```

Verify: `vhs --version`

If VHS is not installable (Windows issues), fall back to asciinema:
```bash
pip install asciinema
asciinema rec --command "python examples/demo.py" examples/demo.cast
```

### Step 2: Write the .tape file

Create `examples/demo.tape`:

```tape
# Enact demo recording — produces examples/demo.gif
# Run: vhs examples/demo.tape

Output examples/demo.gif

Set FontSize 14
Set Width 800
Set Height 600
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 50ms

Type "python examples/demo.py"
Enter
Sleep 12s

# Leave the final output visible for a few seconds
Sleep 4s
```

### Step 3: Record the GIF

```bash
cd /c/Users/user/Desktop/programming/enact
vhs examples/demo.tape
```

Expected: `examples/demo.gif` is created. Should be ~500KB-2MB.

If file is too large (>2MB), adjust:
- Reduce `Set Width` to 700
- Reduce `Set FontSize` to 13
- Or convert to a smaller format with `gifsicle --optimize=3 --lossy=80 examples/demo.gif -o examples/demo-opt.gif`

### Step 4: Verify the GIF looks good

Open `examples/demo.gif` in a browser. Confirm:
- [ ] All 3 acts visible
- [ ] ANSI colors render
- [ ] The deleted rows evidence is readable
- [ ] The verification query is readable
- [ ] The final summary line is visible
- [ ] Total duration ~15-20 seconds

### Step 5: Commit

```bash
git add examples/demo.tape examples/demo.gif
git commit -m "feat: add VHS tape file and terminal GIF recording of demo"
```

---

## Task 3: Embed GIF on landing page

**Files:**
- Modify: `landing_page_v2.html` — add GIF embed in the receipt demo section or create a new "See it in action" section

### Step 1: Add terminal demo section

In `landing_page_v2.html`, find the quickstart section (search for `id="quickstart"`). Add a new section ABOVE the quickstart that shows the GIF.

Add this HTML block before the quickstart section:

```html
<!-- Terminal Demo -->
<section style="padding: 80px 0; background: var(--bg);">
    <div style="max-width: 800px; margin: 0 auto; padding: 0 24px; text-align: center;">
        <h2 style="font-size: 28px; font-weight: 800; margin-bottom: 12px;">See it run</h2>
        <p style="color: var(--muted); font-size: 16px; margin-bottom: 32px;">
            Three scenarios in 15 seconds. No credentials needed.
        </p>
        <div style="border-radius: 12px; overflow: hidden; border: 1px solid var(--border); box-shadow: 0 4px 24px rgba(0,0,0,.12);">
            <div style="background: #1e1e2e; padding: 8px 16px; display: flex; align-items: center; gap: 8px;">
                <span style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f56;"></span>
                <span style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></span>
                <span style="width: 12px; height: 12px; border-radius: 50%; background: #27c93f;"></span>
                <span style="flex: 1; text-align: center; font-family: var(--mono); font-size: 12px; color: #6c7086;">python examples/demo.py</span>
            </div>
            <img src="examples/demo.gif" alt="Enact demo — BLOCK, PASS, and ROLLBACK in 15 seconds"
                 style="width: 100%; display: block; background: #1e1e2e;"
                 loading="lazy" />
        </div>
        <p style="margin-top: 16px; font-size: 13px; color: var(--muted);">
            <code style="font-family: var(--mono); font-size: 12px; background: var(--surface); padding: 3px 8px; border-radius: 4px;">pip install enact-sdk && python examples/demo.py</code>
        </p>
    </div>
</section>
```

### Step 2: Verify in browser

Open `landing_page_v2.html` in browser. Confirm:
- [ ] GIF loads and plays
- [ ] Terminal chrome (traffic lights) looks correct
- [ ] Section sits naturally in the page flow
- [ ] `pip install` one-liner is visible below

### Step 3: Commit

```bash
git add landing_page_v2.html examples/demo.gif
git commit -m "feat: embed terminal demo GIF on landing page"
```

---

## Task 4: Update README with GIF

**Files:**
- Modify: `README.md` — add GIF to the demo section

### Step 1: Add GIF to README demo section

Find the "See the full demo" section we added earlier and add the GIF reference:

**Find:**
```markdown
### See the full demo (no credentials needed)

```bash
python examples/demo.py
```
```

**Replace with:**
```markdown
### See the full demo (no credentials needed)

```bash
python examples/demo.py
```

![Enact demo — BLOCK, PASS, and ROLLBACK](examples/demo.gif)
```

### Step 2: Commit

```bash
git add README.md
git commit -m "docs: add demo GIF to README"
```

---

## Edge Cases & Error Handling

| Scenario | Handling |
|---|---|
| VHS not installable on Windows | Fall back to asciinema (`pip install asciinema`) or manual screen recording |
| GIF too large (>3MB) for GitHub | Optimize with `gifsicle --lossy=80` or reduce resolution in .tape |
| `arr_usd` key doesn't exist in demo data | The demo connector uses `arr_usd` — double-check the key name matches between the connector's `__init__` data and the evidence display code |
| Windows terminal doesn't support ANSI | Demo already handles this — colors degrade to plain text, evidence still readable |
| Demo output changes between runs (UUIDs) | VHS records a single run — UUIDs will be different each time but that's fine for a demo GIF |

---

## Success Criteria

- [ ] `python examples/demo.py` shows deleted row data (names, emails, ARR) after the delete
- [ ] `python examples/demo.py` shows verification query results after rollback
- [ ] The "how do they know?" question is answered by the output itself
- [ ] `examples/demo.gif` exists and is <3MB
- [ ] GIF is embedded on `landing_page_v2.html` in a terminal chrome frame
- [ ] GIF is referenced in `README.md`
- [ ] All 163 tests still pass
- [ ] All committed and pushed
