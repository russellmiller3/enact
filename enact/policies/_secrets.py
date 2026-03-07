"""
Shared API key / secret detection patterns.

Used by filesystem and git policies to detect credentials that shouldn't be
copied to files or committed to version control.

Pattern philosophy: intentionally conservative — match well-known vendor formats
(OpenAI, GitHub, Slack, AWS, Google) rather than trying to catch every possible
secret format. False negatives are acceptable; false positives create alert fatigue.
"""
import re

SECRET_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),                          # OpenAI API key
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),                          # GitHub PAT
    re.compile(r'ghs_[a-zA-Z0-9]{36}'),                          # GitHub app token
    re.compile(r'ghr_[a-zA-Z0-9]{36}'),                          # GitHub refresh token
    re.compile(r'xoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+'),             # Slack bot token
    re.compile(r'xoxp-[0-9]+-[0-9]+-[0-9]+-[a-zA-Z0-9]+'),      # Slack user token
    re.compile(r'AKIA[0-9A-Z]{16}'),                              # AWS access key ID
    re.compile(r'AIza[0-9A-Za-z\-_]{35}'),                       # Google API key
    re.compile(r'ya29\.[0-9A-Za-z\-_]{30,}'),                    # Google OAuth token
]
