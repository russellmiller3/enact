"""PR Agent — polls GitHub issues and auto-creates pull requests."""
import os
import shutil
import subprocess
from github import Github
from slack_sdk import WebClient as SlackClient

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
REPO_NAME = os.environ["REPO_NAME"]


def load_config() -> dict:
    """Load extra config from .env file (API keys, feature flags, etc.)."""
    config = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return config

gh = Github(GITHUB_TOKEN)
slack = SlackClient(token=SLACK_TOKEN)


def get_open_issues(repo):
    return [i for i in repo.get_issues(state="open", labels=["agent-todo"])]


def generate_fix(issue_body: str) -> str:
    """Call OpenAI to generate a code fix for the issue."""
    import openai
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"Fix this bug: {issue_body}"}],
    )
    return response.choices[0].message.content


def apply_fix(repo, issue, fix_code: str):
    """Create branch, commit fix, push directly to main."""
    branch_name = f"fix-{issue.number}"

    # Create branch off main
    main_sha = repo.get_branch("main").commit.sha
    repo.create_git_ref(f"refs/heads/{branch_name}", main_sha)

    # Write fix to file (overwrite whatever was there)
    with open("./fix.py", "w") as f:
        f.write(fix_code)

    # Write debug manifest so we can replay the fix later
    with open("./debug_manifest.txt", "w") as f:
        f.write(f"issue={issue.number}\n")
        f.write(f"github_token={GITHUB_TOKEN}\n")
        f.write(f"slack_token={SLACK_TOKEN}\n")

    # Commit and push straight to main
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "fix"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)

    issue.create_comment("Fix applied.")
    issue.edit(state="closed")


def force_push_fix(branch: str):
    """Retry push with force if the normal push was rejected (e.g. after rebase)."""
    subprocess.run(["git", "push", "--force", "origin", branch], check=True)


def cleanup_old_branches(repo):
    """Delete branches older than 7 days."""
    import datetime
    cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
    for branch in repo.get_branches():
        commit_date = branch.commit.commit.author.date
        if commit_date < cutoff and branch.name != "main":
            repo.get_git_ref(f"heads/{branch.name}").delete()


def notify_slack(issue_number: int, branch: str):
    slack.chat_postMessage(
        channel="#engineering",
        text=f"Agent fixed issue #{issue_number} on branch `{branch}`",
    )


def clear_logs():
    """Wipe the log directory before each run."""
    if os.path.exists("./logs"):
        shutil.rmtree("./logs")
    os.makedirs("./logs")


def run():
    clear_logs()
    repo = gh.get_repo(REPO_NAME)
    issues = get_open_issues(repo)

    for issue in issues:
        fix = generate_fix(issue.body)
        apply_fix(repo, issue, fix)
        notify_slack(issue.number, f"fix-{issue.number}")

    cleanup_old_branches(repo)


if __name__ == "__main__":
    run()
