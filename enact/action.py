"""
Generic action decorator for Enact.

Wraps any Python function into Enact's policy/receipt/rollback pipeline
without requiring a full connector class or workflow definition.

Usage:
    from enact.action import action

    @action("github.create_pr")
    def create_pr(repo, branch, title):
        result = github_sdk.create_pr(repo=repo, branch=branch, title=title)
        return {"pr_url": result["url"]}, {"pr_number": result["number"], "repo": repo}

    @action("github.close_pr")
    def close_pr(repo, pr_number):
        github_sdk.close_pr(repo=repo, pr_number=pr_number)
        return {"closed": True}

    create_pr.rollback_with(close_pr)
"""
from dataclasses import dataclass, field
from typing import Any

from enact.models import ActionResult


@dataclass
class Action:
    """Metadata for a registered action."""
    name: str           # "system.action_name"
    system: str         # parsed from name or explicit override
    fn: Any             # the original callable
    rollback_fn: "Action | None" = field(default=None)


# Module-level registry — populated by @action decorator at decoration time.
# EnactClient builds its own copy from the actions= list at init.
_ACTION_REGISTRY: dict[str, Action] = {}


def get_action_registry() -> dict[str, Action]:
    """Return a copy of the global action registry."""
    return dict(_ACTION_REGISTRY)


def clear_action_registry() -> None:
    """Clear the global action registry. For test cleanup only."""
    _ACTION_REGISTRY.clear()


def execute_action(action_obj: Action, payload: dict) -> ActionResult:
    """
    Execute a registered action and normalize the return value to ActionResult.

    Handles:
        - dict return -> ActionResult(output=dict)
        - tuple(dict, dict) return -> ActionResult(output=first, rollback_data=second)
        - ActionResult return -> pass through
        - None return -> ActionResult(output={})
        - Exception -> ActionResult(success=False, output={"error": str(e)})
        - Other types -> TypeError
    """
    try:
        result = action_obj.fn(**payload)
    except Exception as e:
        return ActionResult(
            action=action_obj.name,
            system=action_obj.system,
            success=False,
            output={"error": str(e)},
        )

    # Pass through ActionResult directly
    if isinstance(result, ActionResult):
        return result

    # None -> empty dict
    if result is None:
        result = {}

    # tuple(output, rollback_data)
    if isinstance(result, tuple):
        if len(result) != 2 or not isinstance(result[0], dict) or not isinstance(result[1], dict):
            raise TypeError(
                f"Action '{action_obj.name}' must return dict, tuple(dict, dict), "
                f"or ActionResult (got tuple with {len(result)} elements)"
            )
        output, rollback_data = result
        output.setdefault("already_done", False)
        return ActionResult(
            action=action_obj.name,
            system=action_obj.system,
            success=True,
            output=output,
            rollback_data=rollback_data,
        )

    # dict -> output only
    if isinstance(result, dict):
        result.setdefault("already_done", False)
        return ActionResult(
            action=action_obj.name,
            system=action_obj.system,
            success=True,
            output=result,
        )

    raise TypeError(
        f"Action '{action_obj.name}' must return dict, tuple(dict, dict), "
        f"or ActionResult (got {type(result).__name__})"
    )


def action(name: str, *, system: str | None = None):
    """
    Decorator that registers a Python function as an Enact action.

    Args:
        name: Action name in "system.action_name" format (e.g. "github.create_pr")
        system: Override the system parsed from name (optional)

    Returns:
        The original function with _enact_action attribute and rollback_with() method added.
    """
    if "." not in name:
        raise ValueError(
            f"Action name must be 'system.action_name' format (got '{name}'). "
            "The part before the dot is the system name."
        )

    parsed_system = system or name.split(".", 1)[0]

    def decorator(fn):
        action_obj = Action(name=name, system=parsed_system, fn=fn)
        _ACTION_REGISTRY[name] = action_obj
        fn._enact_action = action_obj

        def rollback_with(target_fn):
            if not hasattr(target_fn, "_enact_action"):
                raise TypeError(
                    f"Rollback target must be decorated with @action (got {target_fn.__name__})"
                )
            action_obj.rollback_fn = target_fn._enact_action

        fn.rollback_with = rollback_with
        return fn

    return decorator
