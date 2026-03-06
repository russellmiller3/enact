"""
Quick dev seed: creates a team + API key in the local SQLite DB.

Run ONCE before starting the server:
    python -m cloud.seed_dev

Then start the server:
    CLOUD_SECRET=changeme ENACT_EMAIL_DRY_RUN=1 uvicorn cloud.main:app --reload
"""
from cloud.db import init_db, db
from cloud.auth import create_api_key

RAW_KEY = "enact_live_devkey_russell"
TEAM_ID = "team-russell"

init_db()

with db() as conn:
    exists = conn.execute(
        "SELECT team_id FROM teams WHERE team_id = %s", (TEAM_ID,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO teams (team_id, name, plan) VALUES (%s, %s, %s)",
            (TEAM_ID, "Russell Dev Team", "free"),
        )
        print(f"[OK] Created team: {TEAM_ID}")
    else:
        print(f"[--] Team already exists: {TEAM_ID}")

try:
    create_api_key(TEAM_ID, RAW_KEY, label="dev-key")
    print(f"[OK] API key created: {RAW_KEY}")
except Exception as e:
    print(f"[--] Key may already exist: {e}")

print()
print("Start the server (PowerShell):")
print('  $env:CLOUD_SECRET="changeme"; $env:ENACT_EMAIL_DRY_RUN="1"; uvicorn cloud.main:app --reload')
print()
print("Then open: http://localhost:8000/docs")
print(f"Your API key: {RAW_KEY}")
