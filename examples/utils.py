import os
from pathlib import Path

from python_bosch_ebike_connect import RideCache

CACHE_DIR = Path(__file__).parent.parent / ".ride_cache"
OUTPUT_DIR = Path(__file__).parent.parent
RIDE_CACHE = RideCache(CACHE_DIR)


def get_credentials() -> tuple[str, str] | None:
    username, password = os.getenv("EBIKE_USERNAME"), os.getenv("EBIKE_PASSWORD")
    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return None
    return username, password
