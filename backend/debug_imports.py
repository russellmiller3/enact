"""
Debug script to trace exactly where imports hang.
Run: python debug_imports.py
"""

print("=== STARTING IMPORT DEBUG ===")

print("[1/8] Testing basic Python...")
import json
print("    OK: json imported")

print("[2/8] Testing pathlib...")
from pathlib import Path
print(f"    OK: pathlib imported, cwd = {Path.cwd()}")

print("[3/8] Testing models.py...")
import models
print("    OK: models.py imported")

print("[4/8] Testing utils.py BEFORE it loads config...")
print("    WARNING: utils.py line 88 calls reload_config() at module level!")
print("    This will load JSON files and compute SHA256...")
import utils
print("    OK: utils.py imported (config loaded)")

print("[5/8] Testing agents/__init__.py...")
from agents import discovery
print("    OK: discovery agent imported")

print("[6/8] Testing policy agent import...")
from agents import policy
print("    OK: policy agent imported")

print("[7/8] Testing policy.run_policy function...")
from agents.policy import run_policy
print("    OK: run_policy imported")

print("[8/8] Testing Anthropic client (doesn't create connection yet)...")
from anthropic import Anthropic
print("    OK: Anthropic imported")

print("\n=== ALL IMPORTS SUCCESSFUL ===")
print("If you see this, no import is hanging.")
print("The issue is likely in test collection or pytest config.")
