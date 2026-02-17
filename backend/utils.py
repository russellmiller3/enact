"""
Config loaders with in-memory cache + version hash for hot-reload
"""
import json
import hashlib
import os
from pathlib import Path
from threading import RLock  # Changed: RLock is re-entrant (fixes deadlock)

# Config cache
_config_cache = {}
_config_lock = RLock()  # Changed: was Lock() - caused deadlock in reload_config()
_config_version = None
_initialized = False  # Track if we've loaded config yet

CONFIG_DIR = Path(__file__).parent / "config"

def load_users():
    """Load users.json"""
    with _config_lock:
        if "users" in _config_cache:
            return _config_cache["users"]
        
        users_path = CONFIG_DIR / "users.json"
        with open(users_path, "r") as f:
            users = json.load(f)
        
        _config_cache["users"] = users
        return users

def load_datasets():
    """Load datasets.json"""
    with _config_lock:
        if "datasets" in _config_cache:
            return _config_cache["datasets"]
        
        datasets_path = CONFIG_DIR / "datasets.json"
        with open(datasets_path, "r") as f:
            datasets = json.load(f)
        
        _config_cache["datasets"] = datasets
        return datasets

def reload_config():
    """Force reload config and recompute version hash"""
    global _config_version, _initialized
    
    with _config_lock:
        # Clear cache
        _config_cache.clear()
        
        # Reload files (these call load_users/load_datasets which acquire the SAME lock)
        # But now RLock allows re-entry, so no deadlock
        users = load_users()
        datasets = load_datasets()
        
        # Compute version hash
        users_json = json.dumps(users, sort_keys=True)
        datasets_json = json.dumps(datasets, sort_keys=True)
        combined = users_json + datasets_json
        
        _config_version = hashlib.sha256(combined.encode()).hexdigest()[:12]
        _initialized = True
        
        print(f"[OK] Config reloaded (version: {_config_version})")  # Changed: no emoji for Windows
        return _config_version

def ensure_initialized():
    """Lazy initialization - only load config when actually needed"""
    global _initialized
    if not _initialized:
        reload_config()

def get_config_version():
    """Get current config version hash"""
    ensure_initialized()
    return _config_version

def get_user(email: str):
    """Get user by email"""
    ensure_initialized()
    users = load_users()
    return users.get(email)

def get_dataset(dataset_name: str):
    """Get dataset by name"""
    ensure_initialized()
    datasets = load_datasets()
    return datasets.get(dataset_name)

# REMOVED: reload_config() - was causing import-time blocking
# Config is now loaded lazily on first use via ensure_initialized()
