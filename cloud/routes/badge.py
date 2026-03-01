"""
GET /badge/{team_id}/{workflow}.svg

Returns a Shields.io-style SVG badge showing the last run decision for a
given team + workflow. No auth required — the team_id in the URL is the
public identifier (not a secret).

Badge states:
  PASS  → green  (#16a34a)
  BLOCK → red    (#dc2626)
  none  → grey   (#6b7280) "no data"

Embed in README:
  ![Enact](https://enact.cloud/badge/myteam/agent_pr_workflow.svg)
"""
from fastapi import APIRouter
from fastapi.responses import Response
from cloud.db import db

router = APIRouter()

_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="180" height="20">
  <rect rx="3" width="60"  height="20" fill="#555"/>
  <rect rx="3" x="57" width="123" height="20" fill="{color}"/>
  <rect       x="57" width="6"   height="20" fill="{color}"/>
  <text x="6"  y="14" fill="#fff" font-family="DejaVu Sans,sans-serif" font-size="11">enact</text>
  <text x="66" y="14" fill="#fff" font-family="DejaVu Sans,sans-serif" font-size="11">{label}</text>
</svg>"""

_COLORS = {"PASS": "#16a34a", "BLOCK": "#dc2626", "none": "#6b7280"}


@router.get("/badge/{team_id}/{workflow}.svg", response_class=Response)
def get_badge(team_id: str, workflow: str):
    with db() as conn:
        row = conn.execute(
            """SELECT decision, created_at FROM receipts
               WHERE team_id = ? AND workflow = ?
               ORDER BY rowid DESC LIMIT 1""",
            (team_id, workflow),
        ).fetchone()

    if not row:
        decision, ts = "none", ""
    else:
        decision = row["decision"]
        ts = row["created_at"][:16].replace("T", " ") + " UTC"

    label = f"{decision}  {ts}".strip() if ts else "no data"
    svg = _SVG.format(color=_COLORS.get(decision, _COLORS["none"]), label=label)

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache, max-age=0"},
    )
