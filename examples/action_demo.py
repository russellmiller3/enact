"""
Enact @action demo — wrap any function in policy + receipt + rollback.

THE SCENARIO:
A CLI "agent" manages a task tracker. It can create tasks, complete them,
and delete them. Policies prevent dangerous operations:
  - Can't delete tasks without confirmation (simulated)
  - Can't create tasks with banned words in the title

Run it:
    python examples/action_demo.py

WHAT YOU'LL SEE:
  1. PASS  — create a task (policy allows it, receipt signed)
  2. BLOCK — create a task with banned word (policy blocks it)
  3. PASS  — complete a task (works fine)
  4. PASS  — delete a task (allowed because it's confirmed)
  5. ROLLBACK — undo the delete (task comes back!)

NO REAL APIS. No connectors. No workflow definitions.
Just plain Python functions wrapped with @action.
"""
from enact import EnactClient
from enact.action import action
from enact.models import PolicyResult


# ── Fake database ────────────────────────────────────────────────────────────

db: dict[int, dict] = {}
next_id = 1


# ── Actions — plain Python functions, decorated ──────────────────────────────

@action("tasks.create")
def create_task(title, assignee="unassigned"):
    global next_id
    task_id = next_id
    next_id += 1
    db[task_id] = {"title": title, "assignee": assignee, "status": "open"}
    return {"task_id": task_id, "title": title}, {"task_id": task_id}


@action("tasks.complete")
def complete_task(task_id):
    task = db.get(task_id)
    if not task:
        return {"error": f"Task {task_id} not found", "already_done": True}
    old_status = task["status"]
    task["status"] = "done"
    return {"task_id": task_id, "old_status": old_status}, {"task_id": task_id, "old_status": old_status}


@action("tasks.delete")
def delete_task(task_id):
    task = db.pop(task_id, None)
    if not task:
        return {"already_done": "deleted"}
    return {"deleted": True, "was": task}, {"task_id": task_id, "was": task}


@action("tasks.restore")
def restore_task(task_id, was):
    db[task_id] = was
    return {"restored": True, "task_id": task_id}


# Pair delete <-> restore for rollback
delete_task.rollback_with(restore_task)


# ── Policies — pure Python, no LLMs ─────────────────────────────────────────

BANNED_WORDS = ["hack", "drop", "destroy", "yolo"]


def no_banned_words(context):
    """Block tasks with dangerous words in the title."""
    title = context.payload.get("title", "")
    has_banned = any(w in title.lower() for w in BANNED_WORDS)
    return PolicyResult(
        policy="no_banned_words",
        passed=not has_banned,
        reason="clean" if not has_banned else f"Title contains banned word",
    )


# ── The Demo ─────────────────────────────────────────────────────────────────

def show_db():
    if not db:
        print("  Tasks: (empty)")
        return
    for tid, task in db.items():
        print(f"  [{tid}] {task['title']} ({task['status']}) -> {task['assignee']}")


def main():
    print("\n" + "=" * 60)
    print("  ENACT @action DEMO — Plain functions, full pipeline")
    print("=" * 60)

    client = EnactClient(
        actions=[create_task, complete_task, delete_task, restore_task],
        policies=[no_banned_words],
        secret="demo-secret-for-action-example!!",
        receipt_dir="receipts",
        rollback_enabled=True,
    )

    # 1. Create a task (should PASS)
    print("\n1) Creating task 'Fix login bug'...\n")
    result, receipt = client.run_action(
        action="tasks.create",
        user_email="agent@company.com",
        payload={"title": "Fix login bug", "assignee": "alice"},
    )
    print(f"  Decision: {receipt.decision}")
    print(f"  Success:  {result.success}")
    print(f"  Output:   {result.output}")
    show_db()

    # 2. Try to create with banned word (should BLOCK)
    print("\n2) Creating task 'YOLO deploy to prod'... (should BLOCK)\n")
    result, receipt = client.run_action(
        action="tasks.create",
        user_email="agent@company.com",
        payload={"title": "YOLO deploy to prod"},
    )
    print(f"  Decision: {receipt.decision}")
    print(f"  Success:  {result.success}")
    for pr in receipt.policy_results:
        status = "PASS" if pr.passed else "FAIL"
        print(f"  [{status}] {pr.policy}: {pr.reason}")
    show_db()
    print("  ^ Task was NOT created — policy blocked it before the function ran.")

    # 3. Complete the task
    print("\n3) Completing task #1...\n")
    result, receipt = client.run_action(
        action="tasks.complete",
        user_email="agent@company.com",
        payload={"task_id": 1},
    )
    print(f"  Decision: {receipt.decision}")
    show_db()

    # 4. Delete the task
    print("\n4) Deleting task #1...\n")
    result, receipt = client.run_action(
        action="tasks.delete",
        user_email="agent@company.com",
        payload={"task_id": 1},
    )
    delete_receipt = receipt
    print(f"  Decision: {receipt.decision}")
    print(f"  Success:  {result.success}")
    show_db()

    # 5. Rollback the delete — task comes back!
    print("\n5) Rolling back the delete (task should reappear)...\n")
    rb_result, rb_receipt = client.rollback(delete_receipt.run_id)
    print(f"  Rollback Decision: {rb_receipt.decision}")
    print(f"  Rollback Success:  {rb_result.success}")
    show_db()

    print("\n" + "=" * 60)
    print("  That's @action: decorate, policy-gate, receipt, rollback.")
    print("  No connectors. No workflows. Just functions.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
