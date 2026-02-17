"""
Multi-agent system for data access automation
"""
from .discovery import run_discovery
from .intake import run_intake
from .policy import run_policy
from .provision import run_provision
from .notify import run_notify

__all__ = [
    "run_discovery",
    "run_intake", 
    "run_policy",
    "run_provision",
    "run_notify"
]
