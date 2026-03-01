"""
Rollback execution logic for EnactClient.rollback().

execute_rollback_action() takes a single ActionResult and the systems dict,
and dispatches to the appropriate connector inverse method using rollback_data.

Inverse map:
    github.create_branch        -> github.delete_branch
    github.delete_branch        -> github.create_branch_from_sha
    github.create_pr            -> github.close_pr
    github.create_issue         -> github.close_issue
    github.merge_pr             -> github.revert_commit  (git revert -m 1 <sha>; adds new commit, safe on protected branches)
    github.push_commit          -> (irreversible — cannot un-push without destructive force)
    postgres.insert_row         -> postgres.delete_row  (using id or first col as PK)
    postgres.update_row         -> postgres.update_row  (with old_rows from rollback_data)
    postgres.delete_row         -> postgres.insert_row  (for each deleted row)
    postgres.select_rows        -> (read-only, skipped)
    filesystem.write_file       -> filesystem.write_file (restore previous_content)
                                   OR filesystem.delete_file (if previous_content is None)
    filesystem.delete_file      -> filesystem.write_file (recreate with stored content)
    filesystem.read_file        -> (read-only, skipped)
    filesystem.list_dir         -> (read-only, skipped)
    slack.post_message          -> slack.delete_message (using channel + ts from rollback_data)
"""
from enact.models import ActionResult

# Actions that cannot be reversed — rollback returns a recorded failure.
# These are NOT errors — they are documented contracts. The rollback receipt
# records success=False for each so the caller knows what needs manual cleanup.
_IRREVERSIBLE = {
    ("github", "push_commit"),  # Can't un-push without destructive force-push
    # NOTE: Add future irreversible actions here (email sends, etc.)
    # Pattern: ("system_name", "action_name")
    # merge_pr is handled via revert_commit — removed from irreversible
}

# Read-only actions — nothing to undo, rollback skips them gracefully
_READ_ONLY = {
    ("postgres", "select_rows"),
    ("filesystem", "read_file"),
    ("filesystem", "list_dir"),
}


def execute_rollback_action(action_result: ActionResult, systems: dict) -> ActionResult:
    """
    Reverse a single action using its rollback_data.

    Args:
        action_result — the original ActionResult from the run receipt
        systems       — dict of connector instances (same as EnactClient._systems)

    Returns:
        ActionResult describing the rollback attempt:
          - success=True if the inverse operation succeeded
          - success=True, already_done="skipped" for read-only actions
          - success=False, output["error"] for irreversible or failed rollbacks
    """
    key = (action_result.system, action_result.action)

    if key in _READ_ONLY:
        return ActionResult(
            action=f"rollback_{action_result.action}",
            system=action_result.system,
            success=True,
            output={"already_done": "skipped", "reason": "read-only action"},
        )

    if key in _IRREVERSIBLE:
        return ActionResult(
            action=f"rollback_{action_result.action}",
            system=action_result.system,
            success=False,
            output={"error": f"{action_result.action} cannot be reversed"},
        )

    connector = systems.get(action_result.system)
    if connector is None:
        return ActionResult(
            action=f"rollback_{action_result.action}",
            system=action_result.system,
            success=False,
            output={"error": f"System '{action_result.system}' not available for rollback"},
        )

    rd = action_result.rollback_data

    if action_result.system == "github":
        return _rollback_github(action_result.action, rd, connector)
    elif action_result.system == "postgres":
        return _rollback_postgres(action_result.action, rd, connector)
    elif action_result.system == "filesystem":
        return _rollback_filesystem(action_result.action, rd, connector)
    elif action_result.system == "slack":
        return _rollback_slack(action_result.action, rd, connector)
    else:
        return ActionResult(
            action=f"rollback_{action_result.action}",
            system=action_result.system,
            success=False,
            output={"error": f"No rollback handler for system '{action_result.system}'"},
        )


def _rollback_github(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "create_branch":
            return connector.delete_branch(repo=rd["repo"], branch=rd["branch"])
        elif action == "delete_branch":
            return connector.create_branch_from_sha(
                repo=rd["repo"], branch=rd["branch"], sha=rd["sha"]
            )
        elif action == "create_pr":
            return connector.close_pr(repo=rd["repo"], pr_number=rd["pr_number"])
        elif action == "create_issue":
            return connector.close_issue(repo=rd["repo"], issue_number=rd["issue_number"])
        elif action == "merge_pr":
            return connector.revert_commit(
                repo=rd["repo"],
                merge_sha=rd["merge_sha"],
                base_branch=rd.get("base_branch", "main"),
            )
        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="github",
                success=False,
                output={"error": f"No rollback handler for github.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="github",
            success=False,
            output={"error": f"Rollback failed for github.{action}: {str(e)}"},
        )


def _rollback_postgres(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "insert_row":
            inserted_row = rd["inserted_row"]
            # Use "id" as PK if present, otherwise fall back to first column
            pk_col = "id" if "id" in inserted_row else list(inserted_row.keys())[0]
            pk_val = inserted_row[pk_col]
            return connector.delete_row(table=rd["table"], where={pk_col: pk_val})

        elif action == "update_row":
            old_rows = rd.get("old_rows", [])
            if not old_rows:
                return ActionResult(
                    action="rollback_update_row",
                    system="postgres",
                    success=True,
                    output={"already_done": "skipped", "reason": "no rows matched original update"},
                )
            # Restore original values using the same WHERE clause
            return connector.update_row(
                table=rd["table"],
                data=old_rows[0],
                where=rd["where"],
            )

        elif action == "delete_row":
            deleted_rows = rd.get("deleted_rows", [])
            if not deleted_rows:
                return ActionResult(
                    action="rollback_delete_row",
                    system="postgres",
                    success=True,
                    output={"already_done": "skipped", "reason": "no rows were deleted"},
                )
            results = [
                connector.insert_row(table=rd["table"], data=row)
                for row in deleted_rows
            ]
            all_success = all(r.success for r in results)
            return ActionResult(
                action="rollback_delete_row",
                system="postgres",
                success=all_success,
                output={"rows_restored": sum(1 for r in results if r.success)},
            )

        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="postgres",
                success=False,
                output={"error": f"No rollback handler for postgres.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="postgres",
            success=False,
            output={"error": f"Rollback failed for postgres.{action}: {str(e)}"},
        )


def _rollback_filesystem(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "write_file":
            previous_content = rd.get("previous_content")
            if previous_content is None:
                # File was new — delete it to undo the creation
                return connector.delete_file(rd["path"])
            else:
                # File existed — restore its previous content
                return connector.write_file(rd["path"], previous_content)

        elif action == "delete_file":
            # Recreate the file with the content that was stored before deletion
            return connector.write_file(rd["path"], rd["content"])

        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="filesystem",
                success=False,
                output={"error": f"No rollback handler for filesystem.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="filesystem",
            success=False,
            output={"error": f"Rollback failed for filesystem.{action}: {str(e)}"},
        )


def _rollback_slack(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "post_message":
            return connector.delete_message(channel=rd["channel"], ts=rd["ts"])
        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="slack",
                success=False,
                output={"error": f"No rollback handler for slack.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="slack",
            success=False,
            output={"error": f"Rollback failed for slack.{action}: {str(e)}"},
        )
