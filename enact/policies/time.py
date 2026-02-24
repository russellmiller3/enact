"""
Time policies — enforce maintenance windows.
"""
from datetime import datetime, timezone
from enact.models import WorkflowContext, PolicyResult


def within_maintenance_window(start_hour_utc: int, end_hour_utc: int):
    """Factory: returns a policy that only allows actions during a UTC time window."""

    def _policy(context: WorkflowContext) -> PolicyResult:
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        if start_hour_utc <= end_hour_utc:
            in_window = start_hour_utc <= current_hour < end_hour_utc
        else:
            # Window crosses midnight (e.g., 22-06)
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
