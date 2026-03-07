# PR Agent

An AI agent that automatically triages GitHub issues and opens pull requests.

## What it does

1. Polls for open GitHub issues labeled `agent-todo`
2. Reads the issue, generates a fix using the OpenAI API
3. Creates a branch, commits the fix
4. Pushes directly to main (for speed)
5. Closes the issue and posts a Slack summary to #engineering
6. Cleans up old branches by deleting them after 7 days
7. Logs all activity to `./logs/agent.log` (overwrites on each run)
