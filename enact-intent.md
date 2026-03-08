# ENACT

Action firewall for AI agents. Policy gate -> workflow -> signed receipt -> optional rollback.
SDK library (not a UI app). "State" = client config + runtime context per run.

---

## Invariants

Promises the SDK always keeps. If any of these break, it's a bug.

1. A signed receipt is **ALWAYS** written to disk — on PASS, BLOCK, and PARTIAL. No code path skips receipt creation. Even failed runs produce audit evidence.
2. All policies run on every call. Never short-circuits. A BLOCK receipt shows ALL failures, not just the first. Audit completeness > performance.
3. No LLMs in the decision path. Policy engine is pure Python. Always.
4. Signature covers ALL receipt fields. Tampering with any field (payload, policy_results, actions_taken) invalidates the signature.
5. Rollback verifies signature BEFORE executing. Tampered receipts are rejected. Prevents TOCTOU attacks via modified receipt files on disk.
6. Connectors never raise — they return `ActionResult(success=False, output={"error": ...})`. The receipt always records how far a workflow got, even on failure.
7. `run_id` is always UUID v4. Path traversal via crafted run_ids is impossible.
8. Secret is required. No default, no fallback. 32+ chars or `allow_insecure_secret`.
9. Zero-knowledge encryption: when `encryption_key` is set, the cloud CANNOT read payload, user_email, policy_results, or actions_taken. Only metadata.

---

## Error Contracts

What each public method raises and when. Callers catch these.

### `EnactClient.__init__`
- raises `ValueError` — no secret provided (or `ENACT_SECRET` unset)
- raises `ValueError` — secret < 32 chars (unless `allow_insecure_secret=True`)

### `EnactClient.run()`
- raises `ValueError` — workflow name not in registered workflows

### `EnactClient.rollback()`
- raises `PermissionError` — `rollback_enabled=False`
- raises `FileNotFoundError` — no receipt on disk for run_id
- raises `ValueError` — receipt signature invalid (tampered)
- raises `ValueError` — original run was BLOCK (nothing to undo)

### `EnactClient.push_receipt_to_cloud()`
- raises `PermissionError` — no `cloud_api_key` set
- raises `ConnectionError` — cloud unreachable AND `queue_on_failure=False`

### `EnactClient.run_with_hitl()`
- raises `PermissionError` — no `cloud_api_key` set

### `receipt.write_receipt()` / `load_receipt()`
- raises `ValueError` — run_id is not UUID v4 (path traversal protection)
- raises `FileNotFoundError` — no receipt file for run_id (load only)

### encryption
- raises `ValueError` — key is not exactly 32 bytes
- raises `ImportError` — no AES-GCM lib (cryptography or pycryptodome)

---

## Shapes

Pydantic v2 models in `enact/models.py`. Immutable after creation.

```
shape WorkflowContext {
  workflow        : str              # registered workflow name
  user_email      : str              # identity of the caller
  payload         : dict             # arbitrary inputs the workflow needs
  systems         : dict = {}        # connector instances keyed by name
  user_attributes : dict = {}        # ABAC context (role, clearance, dept)
}
```

```
shape PolicyResult {
  policy : str                       # machine-readable name (matches fn name)
  passed : bool                      # true = allow, false = block
  reason : str                       # human-readable explanation
}
```

```
shape ActionResult {
  action        : str                # operation name (e.g. "create_branch")
  system        : str                # connector name (e.g. "github")
  success       : bool               # completed without error?
  output        : dict = {}          # raw connector response
  rollback_data : dict = {}          # pre-mutation state for reversal
}
```

```
shape Receipt {
  run_id         : str = uuid4()     # unique ID, also filename
  workflow       : str
  user_email     : str
  payload        : dict
  policy_results : List<PolicyResult>
  decision       : Enum(PASS | BLOCK | PARTIAL)
  actions_taken  : List<ActionResult> = []
  timestamp      : str               # ISO8601 UTC, set at build time
  signature      : str               # HMAC-SHA256 hex digest
}
```

```
shape RunResult {
  success  : bool                    # all policies passed AND workflow ran
  workflow : str
  output   : dict = {}              # {action_name: action_output} for successes
}
```

---

## Connector Shapes

Runtime classes in `enact/connectors/*.py`. All mutating methods return `ActionResult`.
Convention: `output["already_done"]` = `False` (fresh) or descriptive string (noop).

```
shape GitHubConnector {
  token : str
  # actions: create_branch, delete_branch, create_branch_from_sha,
  #          create_pr, close_pr, merge_pr, revert_commit,
  #          create_issue, close_issue, push_commit
}
```

```
shape PostgresConnector {
  dsn : str
  allowed_actions : List<str>
  # actions: select_rows, insert_row, update_row, delete_row
}
```

```
shape FilesystemConnector {
  base_dir : str                     # path confinement boundary
  # actions: read_file, write_file, delete_file, list_dir
}
```

```
shape SlackConnector {
  token : str
  # actions: post_message, delete_message
}
```

```
shape CloudClient {
  api_key        : str
  base_url       : str = "https://enact.cloud"
  encryption_key : bytes?            # 32-byte AES-256 key, never leaves machine
  receipt_dir    : str = "receipts"
}
```

---

## State

`EnactClient` holds all state. Configured at init, immutable after.
File: `enact/client.py`

```
state systems          : dict = {}                  # connector instances
state policies         : List<callable> = []        # policy fns
state workflows        : dict = {}                  # {fn.__name__: fn}
state secret           : str                        # HMAC key (required, 32+ chars)
state receipt_dir      : str = "receipts"
state rollback_enabled : bool = false
state cloud            : CloudClient? = null        # lazy-loaded if cloud_api_key set
```

---

## Derives

Computed during a run, not stored on client.

```
derive all_passed       = all(r.passed for r in policy_results)
derive run_output       = {a.action: a.output for a in actions_taken if a.success}
derive reversible       = [a for a in reversed(actions_taken) if a.success and not a.output.get("already_done")]
derive signature_valid  = hmac.compare_digest(receipt.signature, expected_hmac)
derive signature_msg    = f"{run_id}:{workflow}:{user_email}:{decision}:{timestamp}:{canon(payload)}:{canon(policy_results)}:{canon(actions_taken)}"
```

---

## Actions

Public API of `EnactClient`. These are the only entry points.

### `run(workflow, user_email, payload)`

`enact/client.py :: EnactClient.run()`

```
action run(workflow: str, user_email: str, payload: dict) {
  guard workflow in self.workflows          # ValueError if unknown
  context = WorkflowContext(workflow, user_email, payload, systems)
  policy_results = evaluate_all(context, policies)    # never short-circuits
  if not all_passed:
    receipt = build -> sign -> write (decision=BLOCK, actions=[])
    return (RunResult(success=false), receipt)
  actions_taken = workflow_fn(context)
  receipt = build -> sign -> write (decision=PASS, actions=actions_taken)
  return (RunResult(success=true, output=run_output), receipt)
}
```

### `rollback(run_id)`

`enact/client.py :: EnactClient.rollback()`

```
action rollback(run_id: str) {
  guard rollback_enabled                    # PermissionError if false
  original = load_receipt(run_id)
  guard signature_valid(original)           # ValueError if tampered
  guard original.decision != BLOCK          # ValueError — nothing to undo
  for action in reversible:
    result = execute_rollback_action(action, systems)
  receipt = build -> sign -> write (decision=PASS|PARTIAL)
  return (RunResult, receipt)
}
```

### `push_receipt_to_cloud(receipt)`

`enact/client.py :: EnactClient.push_receipt_to_cloud()`

```
action push_receipt_to_cloud(receipt: Receipt) {
  guard cloud is not null                   # PermissionError if no cloud_api_key
  if encryption_key:
    split receipt -> metadata (clear) + payload (AES-256-GCM encrypted)
  cloud.push_receipt(receipt)
  cloud.drain_queue()                       # retry any previously queued
}
```

### `run_with_hitl(workflow, user_email, payload, notify_email, ...)`

`enact/client.py :: EnactClient.run_with_hitl()`

```
action run_with_hitl(workflow, user_email, payload, notify_email, ...) {
  guard cloud is not null                   # PermissionError
  hitl = cloud.request_hitl(workflow, payload, notify_email)
  status = cloud.poll_until_decided(hitl_id)
  if status != APPROVED:
    receipt = build -> sign -> write (decision=BLOCK, reason=f"Human approval {status}")
    return (RunResult(success=false), receipt)
  return run(workflow, user_email, payload)  # delegates to normal run
}
```

---

## Policy Engine

`enact/policy.py` — pure functions, no state.

```
action evaluate_all(context: WorkflowContext, policies: List<callable>) {
  # Runs EVERY policy. Never bails early. Returns List<PolicyResult>.
  # Design: audit completeness > performance. Show ALL failures, not just first.
  for policy_fn in policies:
    results += policy_fn(context)
  return results
}
```

---

## Rollback Dispatch

`enact/rollback.py` — maps original action -> inverse action.

```
action execute_rollback_action(action: ActionResult, systems: dict) {
  # Irreversible: github.push_commit -> recorded failure
  # Read-only: postgres.select_rows, filesystem.read_file, filesystem.list_dir -> skip
  # GitHub: create_branch->delete, create_pr->close, merge_pr->revert_commit, etc.
  # Postgres: insert->delete, update->restore old_rows, delete->re-insert
  # Filesystem: write->restore previous_content or delete, delete->recreate
  # Slack: post_message->delete_message
}
```

---

## Receipt Operations

`enact/receipt.py` — build, sign, verify, read/write disk.

- **`build_receipt(...)`** — Creates unsigned Receipt with `timestamp=now(UTC)`, `signature=""`
- **`sign_receipt(receipt, secret)`** — HMAC-SHA256 over ALL fields (JSON canonicalized). Returns new Receipt.
- **`verify_signature(receipt, secret)`** — Recompute HMAC, compare with `hmac.compare_digest` (constant-time).
- **`write_receipt(receipt, directory)`** — Validate run_id is UUID (path traversal protection). Resolve path, verify inside target dir. Write JSON.
- **`load_receipt(run_id, directory)`** — Validate UUID. Load JSON. Return Receipt.

---

## Effects

I/O boundaries. Disk, HTTP, and connector calls.

### `write_receipt_to_disk`
```
WRITE receipts/{run_id}.json
on success => receipt persisted
on error   => OSError (dir creation, permissions)
```

### `cloud_push_receipt`
```
POST /receipts                           # cloud/routes/receipts.py
on success => {"status": "ok", "run_id": ...}
on error   => queue locally (enact/local_queue.py), retry on next successful push
```

### `cloud_request_hitl`
```
POST /hitl/request                       # cloud/routes/hitl.py
on success => {"hitl_id": ..., "status": "PENDING"}
# Cloud sends approval email via smtplib
```

### `cloud_poll_hitl`
```
GET /hitl/{hitl_id}                      # cloud/routes/hitl.py
on success => {"status": APPROVED | DENIED | EXPIRED | PENDING}
# Blocks in poll loop until non-PENDING
```

### Connectors
- **GitHub** — PyGithub SDK calls. Every mutating method returns ActionResult with rollback_data. `already_done` convention on all methods.
- **Postgres** — psycopg2 with `Identifier`/`Placeholder` SQL safety. Pre-SELECT captures state for rollback on update/delete.
- **Filesystem** — stdlib file I/O, confined to `base_dir`. Captures `previous_content` before write/delete for rollback.
- **Slack** — slack-sdk API calls. `post_message` captures `ts` for `delete_message` rollback.

---

## Encryption

`enact/encryption.py` — zero-knowledge receipt encryption.

- **`encrypt_payload(payload, key)`** — AES-256-GCM. Returns `base64(nonce + ciphertext + tag)`. Tries cryptography lib first, falls back to PyCryptodome. Guard: `len(key) == 32`.
- **`decrypt_payload(encrypted_b64, key)`** — Guard: `len(key) == 32`.
- **`split_receipt_for_cloud(receipt_dict)`** — metadata (clear): run_id, workflow, decision, timestamp, policy_names. payload (encrypted): user_email, payload, policy_results, actions_taken, signature.

---

## Built-in Policies

30 policies across 9 files in `enact/policies/`. Each is a callable: `(WorkflowContext) -> PolicyResult`. Factory policies return closures (e.g. `max_files_per_commit(10)`).

| File | Policies |
|------|----------|
| `git.py` | `dont_push_to_main`, `dont_merge_to_main`, `dont_delete_branch`, `max_files_per_commit(n)`, `require_branch_prefix(prefix)`, `dont_force_push`, `require_meaningful_commit_message`, `dont_commit_api_keys` |
| `filesystem.py` | `dont_delete_file`, `restrict_paths(allowed)`, `block_extensions(exts)`, `dont_edit_gitignore`, `dont_read_env`, `dont_touch_ci_cd`, `dont_access_home_dir`, `dont_copy_api_keys` |
| `db.py` | `dont_delete_row`, `dont_delete_without_where`, `dont_update_without_where`, `protect_tables(names)`, `block_ddl` |
| `access.py` | `contractor_cannot_write_pii`, `require_actor_role(roles)`, `dont_read_sensitive_tables`, `dont_read_sensitive_paths`, `require_clearance_for_path`, `require_user_role(roles)` |
| `crm.py` | `dont_duplicate_contacts`, `limit_tasks_per_contact(max, window_days)` |
| `time.py` | `within_maintenance_window(start, end)`, `code_freeze_active` |
| `slack.py` | `require_channel_allowlist`, `block_dms` |
| `email.py` | `no_mass_emails`, `no_repeat_emails` |
| `cloud_storage.py` | `dont_delete_without_human_ok` |

Shared: `enact/policies/_secrets.py` — 9 vendor API key regex patterns.

---

## Workflows

Reference implementations in `enact/workflows/`. Each is a function: `(WorkflowContext) -> List<ActionResult>`.

- **`agent_pr_workflow`** — create_branch -> open PR (never to main)
- **`db_safe_insert`** — duplicate check -> insert_row
- **`post_slack_message`** — policy-gated Slack post with delete rollback

---

## Cloud Backend

Separate FastAPI app in `cloud/`. Deployed to Fly.io. Not part of the SDK package — proprietary revenue engine.

| File | Purpose |
|------|---------|
| `cloud/main.py` | FastAPI app, lifespan startup |
| `cloud/auth.py` | `X-Enact-Api-Key` header, SHA-256 hash stored |
| `cloud/db.py` | Dual-mode: SQLite for dev/tests, Postgres in prod |
| `cloud/token.py` | HMAC-signed approve/deny tokens |
| `cloud/approval_email.py` | smtplib, `ENACT_EMAIL_DRY_RUN=1` for dev |
| `cloud/routes/receipts.py` | `POST /receipts` (idempotent upsert), `GET /receipts/{run_id}` |
| `cloud/routes/hitl.py` | `POST /hitl/request`, approve/deny endpoints, callback webhook |
| `cloud/routes/badge.py` | `GET /badge/{team_id}/{workflow}.svg` |

---

## Receipt Browser

`enact/ui.py` — local web UI for browsing audit receipts. Stdlib only (`http.server`), zero extra deps. CLI: `enact-ui`.

```
state ui_receipts  : List<Receipt> = []              # loaded from receipt_dir/*.json
state ui_filter    : Enum(all | PASS | BLOCK | PARTIAL) = all
state ui_search    : str = ""                        # filters workflow + user_email
state ui_selected  : str? = null                     # run_id of selected receipt
state ui_theme     : Enum(light | dark) = system     # persisted in localStorage
```

```
derive ui_filtered = ui_receipts
  .where(r => ui_filter == all || r.decision == ui_filter)
  .where(r => r.workflow.includes(ui_search) || r.user_email.includes(ui_search))

derive ui_stats = {
  total:   ui_receipts.length,
  pass:    ui_receipts.where(r => r.decision == PASS).length,
  block:   ui_receipts.where(r => r.decision == BLOCK).length,
  partial: ui_receipts.where(r => r.decision == PARTIAL).length,
  shown:   ui_filtered.length,
}
```

### UI Actions
- **`ui_load_receipts`** — `GET /api/receipts` -> JSON list of summaries (newest first). Auto-refreshes every 5 seconds.
- **`ui_select_receipt(run_id)`** — `GET /api/receipts/{run_id}` -> full receipt + `signature_valid`.
- **`ui_toggle_filter(filter)`** — Sets `ui_filter`.
- **`ui_toggle_theme`** — Toggles dark/light, persists to `localStorage`.

### UI Effects
```
HTTPServer on 127.0.0.1:{port}
GET /              -> embedded HTML (single-file, no template deps)
GET /api/receipts  -> JSON list of receipt summaries
GET /api/receipts/{run_id} -> full receipt detail + signature_valid
```

---

## Local Queue

`enact/local_queue.py` — offline resilience for cloud push. When cloud is unreachable, receipts queue locally and drain on next success.

```
state queue_dir : Path = receipt_dir / "queue"       # auto-created
```

- **`enqueue_receipt(receipt_dir, metadata, payload_blob?, full_receipt?)`** — Writes `<timestamp>_<run_id>.json` to `queue_dir`. Stores encrypted or full receipt depending on `encryption_key`.
- **`drain_queue(receipt_dir, push_fn, max_retries=10)`** — Pushes queued receipts oldest-first via `push_fn`. Removes file on success, leaves in queue on failure. Returns `(success_count, failure_count)`.

---

## Open Questions

- Stripe integration for $199/mo Cloud plan — in progress (see `plans/2026-03-07-stripe-integration.md`)
- HubSpot connector — planned, not yet implemented
- Anomaly detection — rule-based first, ML later. No code yet.
- Multi-agent arbitration (soft locks) — designed in SPEC, not built
