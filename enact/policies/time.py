"""
Time-based policies — enforce maintenance windows and deploy freezes.

These policies gate actions based on the current UTC time. They are useful
for:
  - Restricting database writes to off-peak maintenance windows
  - Implementing deploy freezes around releases or incidents
  - Preventing agent actions during business hours when human oversight is higher

All time comparisons use UTC. Callers should translate their local maintenance
window times to UTC before passing them in.

Midnight-crossing windows
--------------------------
Windows that span midnight (e.g. 22:00–06:00) are handled correctly by comparing
start and end hours:

    if start <= end:  → normal window (e.g. 02:00–06:00): hour must be in [start, end)
    if start > end:   → crosses midnight: hour >= start OR hour < end

This covers the full 24-hour clock without needing date arithmetic.
"""
import os
from datetime import datetime, timezone
from enact.models import WorkflowContext, PolicyResult


def within_maintenance_window(start_hour_utc: int, end_hour_utc: int):
    """
    Factory: return a policy that only allows actions during a UTC time window.

    The window is defined by hour boundaries (0–23). The end hour is exclusive
    (start=2, end=6 allows hours 2, 3, 4, 5 but not 6).

    Midnight-crossing windows (start > end) are supported:
      within_maintenance_window(22, 6) allows 22, 23, 0, 1, 2, 3, 4, 5

    Example — restrict to a 2am–6am UTC maintenance window:

        EnactClient(policies=[within_maintenance_window(2, 6)])

    Args:
        start_hour_utc — window start hour in UTC (inclusive), 0–23
        end_hour_utc   — window end hour in UTC (exclusive), 0–23

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        # Always use UTC — never local time, which varies by server location.
        now = datetime.now(timezone.utc)
        current_hour = now.hour

        if start_hour_utc <= end_hour_utc:
            # Normal window — does not cross midnight
            # e.g. start=2, end=6: allow if 2 <= hour < 6
            in_window = start_hour_utc <= current_hour < end_hour_utc
        else:
            # Window crosses midnight (start > end)
            # e.g. start=22, end=6: allow if hour >= 22 OR hour < 6
            in_window = current_hour >= start_hour_utc or current_hour < end_hour_utc

        return PolicyResult(
            policy="within_maintenance_window",
            passed=in_window,
            reason=(
                f"Current hour {current_hour} UTC is "
                f"{'inside' if in_window else 'outside'} window "
                f"{start_hour_utc:02d}:00-{end_hour_utc:02d}:00 UTC"
            ),
        )

    return _policy


# Values of ENACT_FREEZE that mean "yes, freeze is on"
_FREEZE_ON_VALUES = frozenset(("1", "true", "yes"))


def code_freeze_active(context: WorkflowContext) -> PolicyResult:
    """
    Block all operations when a code freeze is declared via environment variable.

    Set ENACT_FREEZE=1 (or "true" / "yes") in your environment to freeze all
    agent actions through this client. Unset or set to "0" / "" to lift the freeze.

    This directly addresses the Replit incident pattern: an agent that ignores an
    explicit "do not make changes" instruction. With this policy registered, the
    freeze is enforced at the action layer — the agent cannot override it.

    The check is case-insensitive. Only "1", "true", and "yes" trigger a block;
    "0" and empty string pass through. This avoids the Python string truthy trap
    where "0" would block if evaluated as bool("0").

    Args:
        context — WorkflowContext (not inspected)

    Returns:
        PolicyResult — passed=False if ENACT_FREEZE is set to a truthy value
    """
    freeze_value = os.environ.get("ENACT_FREEZE", "").strip().lower()
    if freeze_value in _FREEZE_ON_VALUES:
        return PolicyResult(
            policy="code_freeze_active",
            passed=False,
            reason=f"Code freeze is active (ENACT_FREEZE={os.environ.get('ENACT_FREEZE')}). No agent actions permitted.",
        )
    return PolicyResult(
        policy="code_freeze_active",
        passed=True,
        reason="No code freeze active",
    )
