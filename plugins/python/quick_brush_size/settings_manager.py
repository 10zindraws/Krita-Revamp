# SPDX-License-Identifier: GPL-3.0-or-later
"""
Settings Manager for Quick Brush Size Plugin

Manages all configurable timing thresholds and speeds with support for:
- Default values (hardcoded original presets)
- Persistence via Krita's settings system
- Live updates to handlers
- Threshold toggle states (enable/disable modes)
"""

from krita import Krita


class SettingsManager:
    """
    Centralized settings manager for Quick Brush Size plugin.
    
    Handles loading, saving, and providing access to all configurable
    timing thresholds and speed parameters.
    """
    
    # Settings group name for Krita's settings system
    SETTINGS_GROUP = "QuickBrushSize"
    
    # === DEFAULT VALUES (Original Plugin Presets) ===
    DEFAULTS = {
        # Timing Thresholds
        "hold_detect_time": 0.200,        # 200ms - Hold detection threshold
        "slow_tap_threshold": 0.100,       # 100ms - Tap detection
        "multiplier_threshold": 0.150,     # 150ms - Multiplier activation threshold
        
        # Threshold Enabled States (True = mode enabled)
        "hold_enabled": True,
        "slow_tap_enabled": True,
        "multiplier_enabled": True,
        
        # HOLD Mode Parameters
        "hold_base_interval": 0.10,       # Starting interval when hold begins
        "hold_min_interval": 0.008,       # Minimum interval (max speed)
        "hold_exp_k": 8.0,                # Exponential decay rate
        "hold_tau": 0.15,                 # Time constant for exponential
        
        # TAP Mode Parameters
        "slow_burst_count": 3,            # Number of presses per tap
        "slow_burst_interval": 0.015,     # Time between burst presses
        
        # MULTIPLIER Parameters (applied when taps are in quick succession)
        "multiplier_burst_count": 3,      # Multiplier for burst count (2x to 10x)
        "multiplier_burst_interval": 0.001,  # Burst interval when multiplier is active
    }
    
    # === SETTING METADATA (for UI) ===
    # Format: (display_name, min_value, max_value, decimals, step, tooltip)
    SETTING_META = {
        # Timing Thresholds
        "hold_detect_time": (
            "Hold Detection Time (s)",
            0.010, 0.300, 3, 0.005,
            "Time a key must be held before switching to Hold mode"
        ),
        "slow_tap_threshold": (
            "Tap Threshold (s)",
            0.010, 0.300, 3, 0.005,
            "Time threshold for tap detection"
        ),
        "multiplier_threshold": (
            "Double Tap Threshold (s)",
            0.010, 0.300, 3, 0.005,
            "Time between taps to activate multiplier (quick succession)"
        ),
        
        # HOLD Mode
        "hold_base_interval": (
            "Base Interval (s)",
            0.02, 0.30, 3, 0.01,
            "Starting repeat interval when hold begins"
        ),
        "hold_min_interval": (
            "Min Interval (s)",
            0.001, 0.05, 3, 0.001,
            "Fastest repeat interval (maximum speed)"
        ),
        "hold_exp_k": (
            "Exponential Rate",
            1.0, 20.0, 1, 0.5,
            "How quickly acceleration ramps up (higher = faster)"
        ),
        "hold_tau": (
            "Time Constant (s)",
            0.05, 0.50, 2, 0.01,
            "Time constant for exponential acceleration curve"
        ),
        
        # TAP Mode
        "slow_burst_count": (
            "Burst Count",
            1, 20, 0, 1,
            "Number of size changes per tap"
        ),
        "slow_burst_interval": (
            "Burst Interval (s)",
            0.005, 0.10, 3, 0.005,
            "Time between burst presses"
        ),
        
        # MULTIPLIER Amount
        "multiplier_burst_count": (
            "Burst Count Multiplier",
            2, 10, 0, 1,
            "Multiply burst count by this when tapping in quick succession"
        ),
        "multiplier_burst_interval": (
            "New Burst Interval (s)",
            0.001, 0.050, 3, 0.001,
            "Burst interval to use when multiplier is active"
        ),
    }
    
    # Threshold keys that can be toggled (map to their enabled setting key)
    THRESHOLD_TOGGLE_MAP = {
        "hold_detect_time": "hold_enabled",
        "slow_tap_threshold": "slow_tap_enabled",
        "multiplier_threshold": "multiplier_enabled",
    }
    
    # Group settings by mode for UI organization
    SETTING_GROUPS = {
        "Timing Thresholds": [
            "hold_detect_time",
            "slow_tap_threshold",
            "multiplier_threshold",
        ],
        "Holding Mode": [
            "hold_base_interval",
            "hold_min_interval",
            "hold_exp_k",
            "hold_tau",
        ],
        "Tapping Mode": [
            "slow_burst_count",
            "slow_burst_interval",
        ],
        "Double Tap Multiplier": [
            "multiplier_burst_count",
            "multiplier_burst_interval",
        ],
    }
    
    # Singleton instance
    _instance = None
    
    @classmethod
    def instance(cls):
        """Get the singleton instance of SettingsManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize settings manager with current values."""
        # Current settings (in memory)
        self._current = dict(self.DEFAULTS)
        
        # Last saved settings (for Cancel functionality)
        self._saved = dict(self.DEFAULTS)
        
        # State before Reset to Default (for Cancel after Reset)
        self._before_reset = None
        
        # Registered handlers to update when settings change
        self._handlers = []
        
        # Load saved settings from Krita
        self._load_from_krita()
    
    def _load_from_krita(self):
        """Load settings from Krita's persistent storage."""
        app = Krita.instance()
        if not app:
            return
        
        for key, default in self.DEFAULTS.items():
            try:
                value_str = app.readSetting(
                    self.SETTINGS_GROUP,
                    key,
                    str(default)
                )
                # Convert to appropriate type
                if isinstance(default, bool):
                    self._current[key] = value_str.lower() in ('true', '1', 'yes')
                elif isinstance(default, int):
                    self._current[key] = int(float(value_str))
                else:
                    self._current[key] = float(value_str)
            except (ValueError, TypeError):
                self._current[key] = default
        
        # Update saved state to match loaded settings
        self._saved = dict(self._current)
    
    def _save_to_krita(self):
        """Save current settings to Krita's persistent storage."""
        app = Krita.instance()
        if not app:
            return False
        
        for key, value in self._current.items():
            app.writeSetting(
                self.SETTINGS_GROUP,
                key,
                str(value)
            )
        return True
    
    def get(self, key):
        """Get the current value for a setting."""
        return self._current.get(key, self.DEFAULTS.get(key))
    
    def set(self, key, value):
        """
        Set a setting value (live update, not persisted yet).
        
        Updates all registered handlers immediately.
        """
        if key in self._current:
            # Convert to appropriate type based on default
            default = self.DEFAULTS.get(key)
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(value)
            else:
                value = float(value)
            
            self._current[key] = value
            self._update_handlers()
    
    def is_threshold_enabled(self, threshold_key):
        """Check if a threshold/mode is enabled."""
        enabled_key = self.THRESHOLD_TOGGLE_MAP.get(threshold_key)
        if enabled_key:
            return self._current.get(enabled_key, True)
        return True
    
    def set_threshold_enabled(self, threshold_key, enabled):
        """Set whether a threshold/mode is enabled."""
        enabled_key = self.THRESHOLD_TOGGLE_MAP.get(threshold_key)
        if enabled_key:
            self._current[enabled_key] = bool(enabled)
            self._update_handlers()
    
    def get_enabled_threshold_count(self):
        """Get the count of currently enabled thresholds."""
        count = 0
        for enabled_key in self.THRESHOLD_TOGGLE_MAP.values():
            if self._current.get(enabled_key, True):
                count += 1
        return count
    
    def get_all(self):
        """Get a copy of all current settings."""
        return dict(self._current)
    
    def save(self):
        """
        Save current settings to persistent storage.
        
        Returns True if successful.
        """
        if self._save_to_krita():
            self._saved = dict(self._current)
            self._before_reset = None  # Clear reset state on save
            return True
        return False
    
    def cancel(self):
        """
        Revert to last saved settings.
        
        If Reset to Default was clicked, this also reverts the reset.
        """
        if self._before_reset is not None:
            # Revert the Reset to Default operation
            self._current = dict(self._before_reset)
            self._before_reset = None
        else:
            # Just revert to last saved
            self._current = dict(self._saved)
        
        self._update_handlers()
    
    def reset_to_defaults(self):
        """
        Reset all settings to their default values.
        
        Saves the current state so Cancel can undo this.
        """
        # Store current state before reset (for Cancel)
        self._before_reset = dict(self._current)
        
        # Apply defaults
        self._current = dict(self.DEFAULTS)
        
        self._update_handlers()
    
    def get_default(self, key):
        """Get the default value for a setting."""
        return self.DEFAULTS.get(key)
    
    def register_handler(self, handler):
        """Register a handler to receive setting updates."""
        if handler not in self._handlers:
            self._handlers.append(handler)
            self._apply_to_handler(handler)
    
    def unregister_handler(self, handler):
        """Unregister a handler from setting updates."""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def _update_handlers(self):
        """Update all registered handlers with current settings."""
        for handler in self._handlers:
            self._apply_to_handler(handler)
    
    def _apply_to_handler(self, handler):
        """Apply current settings to a specific handler."""
        # Map setting keys to handler attributes
        handler.HOLD_DETECT_TIME = self._current["hold_detect_time"]
        handler.SLOW_TAP_THRESHOLD = self._current["slow_tap_threshold"]
        handler.MULTIPLIER_THRESHOLD = self._current["multiplier_threshold"]
        
        # Enabled states for modes
        handler.HOLD_ENABLED = self._current["hold_enabled"]
        handler.SLOW_TAP_ENABLED = self._current["slow_tap_enabled"]
        handler.MULTIPLIER_ENABLED = self._current["multiplier_enabled"]
        
        handler.HOLD_BASE_INTERVAL = self._current["hold_base_interval"]
        handler.HOLD_MIN_INTERVAL = self._current["hold_min_interval"]
        handler.HOLD_EXP_K = self._current["hold_exp_k"]
        handler.HOLD_TAU = self._current["hold_tau"]
        
        handler.SLOW_BURST_COUNT = int(self._current["slow_burst_count"])
        handler.SLOW_BURST_INTERVAL = self._current["slow_burst_interval"]
        
        handler.MULTIPLIER_BURST_COUNT = int(self._current["multiplier_burst_count"])
        handler.MULTIPLIER_BURST_INTERVAL = self._current["multiplier_burst_interval"]
