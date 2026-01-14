"""Shared utilities for eBike Connect scripts."""

import json
import os
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".ride_cache"
OUTPUT_DIR = Path(__file__).parent


def get_credentials() -> tuple[str, str] | None:
    """Get credentials from environment, or None if not set."""
    username, password = os.getenv("EBIKE_USERNAME"), os.getenv("EBIKE_PASSWORD")
    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return None
    return username, password


def load_json_cache(pattern: str, exclude_suffix: str | None = None) -> dict[str, list]:
    """Load cached JSON files matching pattern."""
    if not CACHE_DIR.exists():
        return {}
    return {
        f.stem.replace(exclude_suffix or "", ""): json.loads(f.read_text())
        for f in CACHE_DIR.glob(pattern)
        if not exclude_suffix or not f.stem.endswith(exclude_suffix.replace("*", ""))
    }


def save_json_cache(filename: str, data) -> None:
    """Save data to cache as JSON."""
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / filename).write_text(json.dumps(data))
