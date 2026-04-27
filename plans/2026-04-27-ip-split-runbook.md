# IP Split — GitHub push runbook (manual step for Russell)

**Status as of session 15 close:** local IP split is COMPLETE.

- Public repo (`enact-fresh`) has `cloud/`, `tests/cloud/`, `fly.toml`, `Dockerfile` removed. 536 SDK tests pass.
- LICENSE updated with proprietary-notice for cloud + pro repos.
- Two staging repos sit ready to push at:
  - `C:/Users/rmill/Desktop/programming/enact-cloud-staging` — main branch, 1 commit, 36 files (cloud + tests/cloud + fly.toml + Dockerfile + README + LICENSE + .gitignore)
  - `C:/Users/rmill/Desktop/programming/enact-pro-staging` — main branch, 1 commit, 3 files (README + LICENSE + .gitignore)

The session-15 CC instance had `GH_TOKEN` set but the value returned 401 Bad Credentials, so the GitHub-side repo creation could not be automated. Russell needs to do steps 1–4 below in a fresh shell once.

---

## Step 1 — Create the two private repos on GitHub

Two ways:

**Option A — UI (no extra tools needed):**
1. Go to https://github.com/new
2. Owner: russellmiller3 · Name: `enact-cloud` · **Private** · do NOT add README/.gitignore/LICENSE (the staging dir already has them) · Create
3. Repeat for `enact-pro` (same settings)

**Option B — gh CLI** (if you install `gh` later):
```bash
gh repo create russellmiller3/enact-cloud --private --description "Enact Cloud — private FastAPI backend"
gh repo create russellmiller3/enact-pro   --private --description "Enact Pro — chaos telemetry + premium policy packs"
```

---

## Step 2 — Push enact-cloud-staging

```bash
cd C:/Users/rmill/Desktop/programming/enact-cloud-staging
git remote add origin https://github.com/russellmiller3/enact-cloud.git
git push -u origin main
```

If push asks for credentials and `GH_TOKEN` isn't honored, use a personal-access-token in the URL:
```bash
git push -u "https://russellmiller3:<your-PAT>@github.com/russellmiller3/enact-cloud.git" main
```

---

## Step 3 — Push enact-pro-staging

```bash
cd C:/Users/rmill/Desktop/programming/enact-pro-staging
git remote add origin https://github.com/russellmiller3/enact-pro.git
git push -u origin main
```

---

## Step 4 — Update Fly deployment to point at the new private repo

The live `enact.fly.dev` keeps running unchanged from its existing image — only the source-of-truth moves.

```bash
cd C:/Users/rmill/Desktop/programming/enact-cloud-staging
flyctl deploy   # builds + deploys from the new repo
```

Vercel deploys for the public landing page are unaffected — they pull from `enact-fresh` (public) → `enact` repo, which still has `index.html`, `agents.html`, `static/`, etc.

---

## Step 5 — Cleanup local staging dirs (optional)

Once both pushes succeed and you've verified the repos look right on github.com:

```bash
rm -rf C:/Users/rmill/Desktop/programming/enact-cloud-staging
rm -rf C:/Users/rmill/Desktop/programming/enact-pro-staging
```

You can re-clone fresh from GitHub when you need to work on either repo:
```bash
git clone https://github.com/russellmiller3/enact-cloud.git
git clone https://github.com/russellmiller3/enact-pro.git
```

---

## Verification checklist

- [ ] enact-cloud appears as a PRIVATE repo on github.com/russellmiller3
- [ ] enact-pro appears as a PRIVATE repo on github.com/russellmiller3
- [ ] enact-fresh master after merge does NOT show cloud/, tests/cloud/, fly.toml, Dockerfile
- [ ] Vercel deploy of enact.cloud still works (public landing pages)
- [ ] Fly deploy of enact.fly.dev still works (cloud backend, now sourced from enact-cloud)
- [ ] `pip install enact-sdk` from PyPI still works for fresh users (test in clean venv)
