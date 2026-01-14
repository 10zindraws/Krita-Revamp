"""Path management for Preset Groups plugin.

Provides user-writable directory paths for plugin configuration and data files.
Uses Krita's AppDataLocation to ensure files are stored in the user's app data
directory (e.g., %APPDATA%/krita on Windows) rather than the installation directory,
which may require administrator privileges to write to.
"""

import os
from typing import Optional

# Cache for the config directory path
_config_dir_cache: Optional[str] = None
_log_dir_cache: Optional[str] = None

# Plugin identifier for creating plugin-specific subdirectory
PLUGIN_NAME = "preset_groups"


def get_app_data_location() -> str:
    """Get Krita's user-writable app data location.
    
    Returns the path to Krita's app data directory, typically:
    - Windows: %APPDATA%/krita
    - macOS: ~/Library/Application Support/krita
    - Linux: ~/.local/share/krita
    
    Returns:
        Path to Krita's app data location.
    """
    try:
        from krita import Krita
        app_data = Krita.instance().getAppDataLocation()
        if app_data:
            return app_data
    except (ImportError, AttributeError):
        pass
    
    # Fallback for testing or when Krita is not available
    # Use APPDATA environment variable on Windows
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "krita")
    
    # Fallback to user home directory
    return os.path.join(os.path.expanduser("~"), ".local", "share", "krita")


def get_config_dir() -> str:
    """Get the user-writable configuration directory for this plugin.
    
    Creates the directory if it doesn't exist. The directory is located
    within Krita's app data location under pykrita/<plugin_name>/config.
    
    Returns:
        Path to the plugin's configuration directory.
    """
    global _config_dir_cache
    
    if _config_dir_cache is not None:
        return _config_dir_cache
    
    app_data = get_app_data_location()
    config_dir = os.path.join(app_data, "pykrita", PLUGIN_NAME, "config")
    
    try:
        os.makedirs(config_dir, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create config directory {config_dir}: {e}")
        # Fall back to plugin installation directory (may fail on Windows in Program Files)
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        try:
            os.makedirs(config_dir, exist_ok=True)
        except OSError:
            pass
    
    _config_dir_cache = config_dir
    return config_dir


def get_log_dir() -> str:
    """Get the user-writable log directory for this plugin.
    
    Creates the directory if it doesn't exist. The directory is located
    within Krita's app data location under pykrita/<plugin_name>/logs.
    
    Returns:
        Path to the plugin's log directory.
    """
    global _log_dir_cache
    
    if _log_dir_cache is not None:
        return _log_dir_cache
    
    app_data = get_app_data_location()
    log_dir = os.path.join(app_data, "pykrita", PLUGIN_NAME, "logs")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create log directory {log_dir}: {e}")
        # Fall back to plugin installation directory
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            pass
    
    _log_dir_cache = log_dir
    return log_dir


def get_plugin_install_dir() -> str:
    """Get the plugin's installation directory (read-only).
    
    This is the directory where the plugin's Python files are installed.
    Use this for reading bundled resources, NOT for writing config files.
    
    Returns:
        Path to the plugin's installation directory.
    """
    return os.path.dirname(os.path.dirname(__file__))


def get_config_file_path(filename: str) -> str:
    """Get the full path to a config file.
    
    Args:
        filename: The name of the config file (e.g., "common.json").
        
    Returns:
        Full path to the config file in the user-writable config directory.
    """
    return os.path.join(get_config_dir(), filename)


def get_log_file_path(filename: str) -> str:
    """Get the full path to a log file.
    
    Args:
        filename: The name of the log file (e.g., "debug.log").
        
    Returns:
        Full path to the log file in the user-writable log directory.
    """
    return os.path.join(get_log_dir(), filename)


def clear_path_cache():
    """Clear cached paths. Useful for testing or after environment changes."""
    global _config_dir_cache, _log_dir_cache
    _config_dir_cache = None
    _log_dir_cache = None
