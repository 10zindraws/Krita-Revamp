"""Logging utilities.

Currently a no-op stub. Can be enabled for debugging by setting
_DEBUG_ENABLED = True.
"""

from .paths import get_log_file_path

_DEBUG_ENABLED = False
_LOG_FILE = get_log_file_path("log.txt")


def write_log(message: str) -> None:
    """Write a debug message to the log file (no-op if debugging disabled)."""
    if not _DEBUG_ENABLED:
        return
    
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except OSError:
        pass
