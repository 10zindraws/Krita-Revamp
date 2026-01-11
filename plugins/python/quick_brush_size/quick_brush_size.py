# SPDX-License-Identifier: GPL-3.0-or-later
"""
Brush Size Acceleration Extension for Krita

Provides accelerating keyboard shortcuts for brush size adjustment with
two distinct input modes detected in real-time:

1. HOLD: Immediate exponential acceleration - key held down triggers
   near-instantaneous rapid size changes with exponential speed curve.

2. TAP: Individual taps trigger a burst of keypresses per tap for 
   blocky, discrete increments. When taps occur in quick succession 
   (within multiplier threshold), the burst count is multiplied and
   a faster burst interval is used.

No adaptive learning - behavior is determined purely by real-time input pattern.
Modes can be individually enabled/disabled via thresholds in the docker.
"""

from krita import Extension, Krita
from PyQt5.QtCore import QTimer
from math import exp
import time
from enum import Enum

from .settings_manager import SettingsManager


class InputMode(Enum):
    """Input modes detected in real-time based on user behavior."""
    HOLD = "hold"            # Key held down - exponential acceleration
    SLOW_TAP = "slow_tap"    # Taps - burst of presses per tap


class AcceleratingKeyHandler:
    """
    Handles brush size changes with two distinct input modes:
    
    1. HOLD: Near-instantaneous exponential acceleration while key held.
    2. TAP: Taps → burst of presses per tap. When taps are in quick
       succession (within multiplier threshold), burst count is multiplied
       and a faster burst interval is used.
    
    Mode is detected in real-time based on timing patterns.
    Settings are managed by SettingsManager for live updates.
    Modes can be individually enabled/disabled via threshold toggles.
    """
    
    # === Safety Limits (not configurable) ===
    MAX_PRESS_DURATION = 10.0    # Maximum seconds a press can be active (safety timeout)
    STALE_STATE_TIMEOUT = 0.5    # If no timer activity for this long, consider state stale
    MAX_UNCHANGED_TRIGGERS = 15  # Stop if brush size unchanged after this many triggers
    MIN_BRUSH_SIZE = 1.0         # Minimum brush size in pixels
    
    def __init__(self, action_name: str):
        self.action_name = action_name
        
        # === Configurable Settings (set by SettingsManager) ===
        # Timing Thresholds
        self.HOLD_DETECT_TIME = 0.035
        self.SLOW_TAP_THRESHOLD = 0.30
        self.MULTIPLIER_THRESHOLD = 0.15
        
        # Mode Enabled States
        self.HOLD_ENABLED = True
        self.SLOW_TAP_ENABLED = True
        self.MULTIPLIER_ENABLED = True
        
        # HOLD Mode Parameters
        self.HOLD_BASE_INTERVAL = 0.10
        self.HOLD_MIN_INTERVAL = 0.008
        self.HOLD_EXP_K = 8.0
        self.HOLD_TAU = 0.15
        
        # TAP Mode Parameters (burst-based)
        self.SLOW_BURST_COUNT = 3
        self.SLOW_BURST_INTERVAL = 0.015
        
        # MULTIPLIER Parameters
        self.MULTIPLIER_BURST_COUNT = 2      # Multiplier for burst count
        self.MULTIPLIER_BURST_INTERVAL = 0.010  # Faster interval when multiplied
        
        # === State Tracking ===
        self.is_pressed = False
        self.press_start_time = 0
        self.last_trigger_time = 0
        self.last_release_time = 0
        self.trigger_count = 0
        
        # Current detected mode
        self.current_mode = InputMode.SLOW_TAP
        
        # Burst mode state
        self.burst_remaining = 0
        self.burst_active = False  # True while a burst is in progress
        self.burst_timer = QTimer()
        self.burst_timer.timeout.connect(self._on_burst_timer)
        self.burst_timer.setSingleShot(True)
        
        # Current burst settings (set per burst based on mode)
        self._current_burst_interval = 0.015
        
        # Hold mode timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer_interval = 5  # 5ms polling for responsiveness
        
        # === Safety Tracking ===
        self.last_brush_size = None           # Track brush size to detect when it stops changing
        self.unchanged_trigger_count = 0      # Count triggers with no size change
        self.last_timer_activity = 0          # Track timer activity for stale state detection
        
        # Reference to paired handler (set by extension for mutual exclusion)
        self.paired_handler = None
    
    def start_press(self):
        """Called when the key is initially pressed."""
        if self.is_pressed:
            return  # Already pressed, ignore
        
        # === Mutual Exclusion: Stop the paired handler if it's running ===
        # This prevents both handlers from running simultaneously
        if self.paired_handler and self.paired_handler.is_pressed:
            self.paired_handler.force_stop("paired handler starting")
        
        self.is_pressed = True
        self.press_start_time = time.time()
        self.last_trigger_time = self.press_start_time
        self.trigger_count = 0
        
        # === Reset safety counters ===
        self.last_brush_size = self._get_current_brush_size()
        self.unchanged_trigger_count = 0
        self.last_timer_activity = self.press_start_time
        
        # Classify tap type based on time since last release
        time_since_release = self.press_start_time - self.last_release_time
        
        # Determine if this is a tap (possibly with multiplier)
        if self.SLOW_TAP_ENABLED and (self.last_release_time == 0 or time_since_release < self.SLOW_TAP_THRESHOLD):
            # Check if multiplier should be applied (quick succession)
            use_multiplier = (
                self.MULTIPLIER_ENABLED and 
                self.last_release_time > 0 and 
                time_since_release < self.MULTIPLIER_THRESHOLD
            )
            self._handle_slow_tap(use_multiplier)
        else:
            # Fallback: just do a single trigger
            self._handle_slow_tap(False)
        
        # Start timer to detect if this becomes a HOLD (only if hold is enabled)
        # NOTE: If a burst is active, we defer starting the hold timer until
        # the burst completes (see _on_burst_timer). This prevents hold detection
        # from cancelling the burst prematurely.
        if self.HOLD_ENABLED and not self.burst_active:
            self.timer.start(self.timer_interval)
    
    def _handle_slow_tap(self, use_multiplier: bool):
        """Handle tap with optional multiplier."""
        self.current_mode = InputMode.SLOW_TAP
        
        if use_multiplier:
            # Apply multiplier: multiply burst count and use faster interval
            burst_count = self.SLOW_BURST_COUNT * self.MULTIPLIER_BURST_COUNT
            burst_interval = self.MULTIPLIER_BURST_INTERVAL
        else:
            # Normal tap
            burst_count = self.SLOW_BURST_COUNT
            burst_interval = self.SLOW_BURST_INTERVAL
        
        self._start_burst(burst_count, burst_interval)
    
    def _start_burst(self, burst_count, burst_interval):
        """Start a burst of rapid presses for tapping modes."""
        self.burst_remaining = burst_count
        self.burst_active = True
        self._current_burst_interval = burst_interval
        self._trigger_action()
        self.burst_remaining -= 1
        
        if self.burst_remaining > 0:
            self.burst_timer.start(int(self._current_burst_interval * 1000))
        else:
            # Burst finished immediately (single press)
            self._finish_burst()
    
    def _on_burst_timer(self):
        """Timer for burst mode - fire additional presses."""
        if self.burst_remaining > 0 and self.is_pressed:
            self._trigger_action()
            self.burst_remaining -= 1
            
            if self.burst_remaining > 0:
                self.burst_timer.start(int(self._current_burst_interval * 1000))
            else:
                # Burst complete
                self._finish_burst()
        else:
            # Key was released during burst or no remaining
            self._finish_burst()
    
    def _finish_burst(self):
        """
        Called when a burst completes or is cancelled.
        Clears burst state and optionally starts hold detection.
        """
        self.burst_active = False
        self.burst_remaining = 0
        
        # If key is still held and hold mode is enabled, start hold detection now
        # The hold timer will detect the transition to HOLD mode
        if self.is_pressed and self.HOLD_ENABLED:
            # Reset timing for hold detection starting from now
            self.press_start_time = time.time()
            self.last_trigger_time = self.press_start_time
            self.timer.start(self.timer_interval)
    
    def end_press(self):
        """Called when the key is released."""
        if not self.is_pressed:
            return
        
        self._cleanup_state()
        self.last_release_time = time.time()
        self.is_pressed = False
    
    def force_stop(self, reason: str = ""):
        """
        Force stop this handler regardless of current state.
        Used for safety timeouts and mutual exclusion.
        """
        self._cleanup_state()
        self.is_pressed = False
        # Don't update last_release_time on force stop to preserve tap timing logic
    
    def _cleanup_state(self):
        """Clean up all timers and state."""
        self.timer.stop()
        self.burst_timer.stop()
        self.burst_remaining = 0
        self.burst_active = False
        self.unchanged_trigger_count = 0
    
    def _on_timer(self):
        """Timer callback - handle hold mode and acceleration."""
        if not self.is_pressed:
            self.timer.stop()
            return
        
        current_time = time.time()
        elapsed_since_start = current_time - self.press_start_time
        elapsed_since_trigger = current_time - self.last_trigger_time
        
        # === Safety Check 1: Maximum press duration timeout ===
        if elapsed_since_start > self.MAX_PRESS_DURATION:
            self.force_stop("max press duration exceeded")
            return
        
        # Update timer activity tracking
        self.last_timer_activity = current_time
        
        # Detect transition to HOLD mode (only if hold is enabled)
        # Don't transition if a burst is still active - let the burst complete first
        if self.HOLD_ENABLED and elapsed_since_start >= self.HOLD_DETECT_TIME and self.current_mode != InputMode.HOLD and not self.burst_active:
            # Switch to HOLD mode with exponential acceleration
            self.current_mode = InputMode.HOLD
        
        # Only continue timer processing if in HOLD mode
        if self.current_mode != InputMode.HOLD:
            return
        
        # Calculate interval based on current mode
        interval = self._get_current_interval(elapsed_since_start)
        
        if elapsed_since_trigger >= interval:
            self._trigger_action_with_safety_check()
            self.last_trigger_time = current_time
    
    def is_stale_state(self) -> bool:
        """
        Check if the handler is in a stale state (pressed but not receiving events).
        This can happen if key release events are missed.
        """
        if not self.is_pressed:
            return False
        
        current_time = time.time()
        time_since_activity = current_time - self.last_timer_activity
        
        # If we're supposedly pressed but haven't had timer activity in a while,
        # the state is stale
        return time_since_activity > self.STALE_STATE_TIMEOUT
    
    def check_and_fix_stale_state(self):
        """
        Check for and fix stale state. Call this periodically or before
        starting a new press to ensure clean state.
        """
        if self.is_stale_state():
            self.force_stop("stale state detected")
            return True
        return False
    
    def _get_current_interval(self, elapsed_time: float) -> float:
        """Get the repeat interval based on current mode and elapsed time."""
        
        if self.current_mode == InputMode.HOLD:
            # HOLD: Exponential acceleration - very fast
            # interval = base * e^(-k * t / tau)
            t = elapsed_time - self.HOLD_DETECT_TIME
            t = max(0, t)
            decay = exp(-self.HOLD_EXP_K * t / self.HOLD_TAU)
            interval = self.HOLD_BASE_INTERVAL * decay
            return max(self.HOLD_MIN_INTERVAL, interval)
        
        else:  # SLOW_TAP
            # TAP: Burst already handled, this is for if they keep holding
            # after burst - transition to gentle acceleration
            t = elapsed_time
            accel = 1.0 + 1.5 * t
            interval = 0.15 / accel
            return max(0.03, interval)
    
    def _get_current_brush_size(self):
        """
        Get the current brush size from Krita.
        Returns None if unable to get the size.
        """
        try:
            app = Krita.instance()
            if app:
                view = app.activeWindow().activeView() if app.activeWindow() else None
                if view:
                    return view.brushSize()
        except Exception:
            pass
        return None
    
    def _trigger_action_with_safety_check(self):
        """
        Trigger the action with safety checks to prevent getting stuck.
        Stops if brush size is no longer changing (hit min/max limit).
        """
        # Get brush size before triggering
        size_before = self._get_current_brush_size()
        
        # Trigger the actual action
        self._trigger_action()
        
        # Check if brush size changed (with small delay for Krita to process)
        size_after = self._get_current_brush_size()
        
        if size_before is not None and size_after is not None:
            # Check if size actually changed
            if abs(size_before - size_after) < 0.001:  # Essentially unchanged
                self.unchanged_trigger_count += 1
                
                # === Safety Check 2: Stop if brush size isn't changing ===
                # This prevents getting stuck at min (1px) or max size
                if self.unchanged_trigger_count >= self.MAX_UNCHANGED_TRIGGERS:
                    self.force_stop("brush size not changing")
                    return
            else:
                # Size changed, reset counter
                self.unchanged_trigger_count = 0
                self.last_brush_size = size_after
    
    def _trigger_action(self):
        """Trigger the actual brush size action in Krita."""
        self.trigger_count += 1
        
        app = Krita.instance()
        if app:
            action = app.action(self.action_name)
            if action:
                action.trigger()


class BrushSizeAccelerationExtension(Extension):
    """
    Main extension class that registers the accelerating brush size shortcuts.
    
    No adaptive learning - behavior is determined by real-time input patterns:
    - Hold key → exponential acceleration
    - Taps → burst of presses per tap
    - Quick succession taps → multiplied burst count with faster interval
    
    Modes can be individually enabled/disabled via threshold toggles.
    """
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # Handlers for each direction (per-window)
        self.window_handlers = {}
        self.window_filters = {}
        
        # Get settings manager singleton
        self.settings_manager = SettingsManager.instance()
    
    def setup(self):
        """Called once when Krita starts."""
        pass
    
    def createActions(self, window):
        """Create the accelerating brush size actions for a window."""
        
        # Initialize handlers (no shared parameters needed)
        decrease_handler = AcceleratingKeyHandler("decrease_brush_size")
        increase_handler = AcceleratingKeyHandler("increase_brush_size")
        
        # Register handlers with settings manager for live updates
        self.settings_manager.register_handler(decrease_handler)
        self.settings_manager.register_handler(increase_handler)
        
        # === Set up mutual exclusion between handlers ===
        # Each handler knows about its pair to prevent simultaneous operation
        decrease_handler.paired_handler = increase_handler
        increase_handler.paired_handler = decrease_handler
        
        # Store handlers per window
        window_id = id(window)
        self.window_handlers[window_id] = (decrease_handler, increase_handler)
        
        # Create the decrease action
        decrease_action = window.createAction(
            "accel_decrease_brush_size",
            "Quick Decrease Brush Size",
            ""
        )
        decrease_action.setAutoRepeat(False)
        decrease_action.triggered.connect(
            lambda checked=False, h=decrease_handler: self._on_action_triggered(h)
        )
        
        # Create the increase action  
        increase_action = window.createAction(
            "accel_increase_brush_size",
            "Quick Increase Brush Size",
            ""
        )
        increase_action.setAutoRepeat(False)
        increase_action.triggered.connect(
            lambda checked=False, h=increase_handler: self._on_action_triggered(h)
        )
        
        # We need to handle key press/release separately
        # Since Krita actions only get triggered (not pressed/released),
        # we'll use an alternative approach with key event filtering
        self._setup_key_event_handling(window, decrease_handler, increase_handler)
    
    def _setup_key_event_handling(self, window, decrease_handler, increase_handler):
        """
        Set up key event handling to detect press and release.
        
        Since Krita actions don't distinguish between press and release,
        we need to install an event filter to catch the actual key events.
        """
        # Get the window's QWidget to install event filter
        qwindow = window.qwindow()
        if qwindow:
            event_filter = BrushSizeKeyEventFilter(
                decrease_handler,
                increase_handler,
                qwindow
            )
            qwindow.installEventFilter(event_filter)
            self.window_filters[id(window)] = event_filter
    
    def _on_action_triggered(self, handler):
        """
        Handle the action triggered signal.
        
        This is the PRIMARY way we detect key press, since Qt's shortcut system
        consumes KeyPress events before they reach our window event filter.
        The event filter is still needed for KeyRelease detection.
        """
        if handler:
            # Check for and fix stale state before starting
            handler.check_and_fix_stale_state()
            
            if not handler.is_pressed:
                # Start the accelerating repeat mechanism
                handler.start_press()


from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtGui import QKeyEvent, QKeySequence


class BrushSizeKeyEventFilter(QObject):
    """
    Event filter to capture key press and release events for the
    accelerating brush size shortcuts.
    """
    
    def __init__(self, decrease_handler, increase_handler, parent=None):
        super().__init__(parent)
        self.decrease_handler = decrease_handler
        self.increase_handler = increase_handler
        
        # Track which keys are mapped to our actions
        # These will be detected dynamically from the action shortcuts
        self.decrease_keys = set()
        self.increase_keys = set()
        
        # Track currently pressed keys to avoid auto-repeat
        self.pressed_keys = set()
        
        # Delay initial shortcut detection
        self._shortcuts_loaded = False
    
    def _update_shortcut_keys(self):
        """Update the tracked shortcut keys from Krita's action system."""
        app = Krita.instance()
        if not app:
            return False
        
        try:
            # Get decrease action shortcuts
            decrease_action = app.action("accel_decrease_brush_size")
            if decrease_action:
                shortcuts = decrease_action.shortcuts()
                self.decrease_keys = set()
                for shortcut in shortcuts:
                    if not shortcut.isEmpty():
                        # Convert QKeySequence to comparable key+modifiers
                        # QKeySequence[0] gives us the combined key+modifiers as int
                        key_combo = int(shortcut[0]) if len(shortcut) > 0 else 0
                        if key_combo:
                            self.decrease_keys.add(key_combo)
            
            # Get increase action shortcuts
            increase_action = app.action("accel_increase_brush_size")
            if increase_action:
                shortcuts = increase_action.shortcuts()
                self.increase_keys = set()
                for shortcut in shortcuts:
                    if not shortcut.isEmpty():
                        key_combo = int(shortcut[0]) if len(shortcut) > 0 else 0
                        if key_combo:
                            self.increase_keys.add(key_combo)
            
            self._shortcuts_loaded = bool(self.decrease_keys or self.increase_keys)
            return self._shortcuts_loaded
            
        except Exception as e:
            # Silently fail - shortcuts might not be assigned yet
            return False
    
    def _get_key_combo(self, key_event):
        """Get a comparable key combination from a key event."""
        key = key_event.key()
        modifiers = key_event.modifiers()
        
        # Filter out just the modifier keys themselves
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            return None
        
        # Combine key with modifiers for comparison
        # Need to convert Qt.KeyboardModifiers to int and mask properly
        mod_int = int(modifiers)
        
        # Qt uses different bits for modifiers in QKeySequence vs QKeyEvent
        # Map the modifier flags appropriately
        combo = key
        if mod_int & Qt.ShiftModifier:
            combo |= Qt.ShiftModifier
        if mod_int & Qt.ControlModifier:
            combo |= Qt.ControlModifier
        if mod_int & Qt.AltModifier:
            combo |= Qt.AltModifier
        if mod_int & Qt.MetaModifier:
            combo |= Qt.MetaModifier
        
        return combo
    
    def eventFilter(self, obj, event):
        """Filter key events to handle press/release for our shortcuts."""
        
        # Lazy load shortcuts on first key event
        if not self._shortcuts_loaded:
            self._update_shortcut_keys()
        
        # === Periodic stale state check on any key event ===
        # This helps catch and fix stale states that might have been missed
        self._check_stale_handlers()
        
        if event.type() == QEvent.KeyPress:
            key_event = event
            
            # Get comparable key combination
            key_combo = self._get_key_combo(key_event)
            if key_combo is None:
                return False
            
            # Ignore auto-repeat events
            if key_event.isAutoRepeat():
                if key_combo in self.decrease_keys or key_combo in self.increase_keys:
                    return True  # Consume the auto-repeat
                return False
            
            # Check if this matches our shortcuts
            if key_combo in self.decrease_keys and key_combo not in self.pressed_keys:
                self.pressed_keys.add(key_combo)
                self.decrease_handler.start_press()
                return True  # Consume the event
            
            elif key_combo in self.increase_keys and key_combo not in self.pressed_keys:
                self.pressed_keys.add(key_combo)
                self.increase_handler.start_press()
                return True  # Consume the event
        
        elif event.type() == QEvent.KeyRelease:
            key_event = event
            
            # Ignore auto-repeat events
            if key_event.isAutoRepeat():
                return False
            
            key_combo = self._get_key_combo(key_event)
            if key_combo is None:
                return False
            
            # Check if this key matches our shortcuts and the handler is active.
            # We check handler.is_pressed instead of pressed_keys because
            # Qt's shortcut system consumes KeyPress events before they reach us,
            # so pressed_keys tracking via KeyPress doesn't work for bound shortcuts.
            # The handler.is_pressed flag is set by triggered() signal instead.
            if key_combo in self.decrease_keys and self.decrease_handler.is_pressed:
                self.pressed_keys.discard(key_combo)
                self.decrease_handler.end_press()
                return True
            
            elif key_combo in self.increase_keys and self.increase_handler.is_pressed:
                self.pressed_keys.discard(key_combo)
                self.increase_handler.end_press()
                return True
            
            # === Fallback: If a handler is pressed but key doesn't match exactly ===
            # This catches cases where modifier state changed between press and release
            key_only = key_event.key()
            if self._key_in_set_ignoring_modifiers(key_only, self.decrease_keys) and self.decrease_handler.is_pressed:
                self.pressed_keys.discard(key_combo)
                self.decrease_handler.end_press()
                return True
            
            elif self._key_in_set_ignoring_modifiers(key_only, self.increase_keys) and self.increase_handler.is_pressed:
                self.pressed_keys.discard(key_combo)
                self.increase_handler.end_press()
                return True
        
        # Handle focus loss - release all keys
        elif event.type() == QEvent.FocusOut:
            self._release_all_keys()
        
        # Handle window deactivation
        elif event.type() == QEvent.WindowDeactivate:
            self._release_all_keys()
        
        return False  # Don't consume other events
    
    def _release_all_keys(self):
        """Release all currently pressed keys on focus loss or window deactivation."""
        # Use handler state instead of pressed_keys, since pressed_keys tracking
        # may be incomplete when shortcuts consume KeyPress events
        if self.decrease_handler.is_pressed:
            self.decrease_handler.end_press()
        if self.increase_handler.is_pressed:
            self.increase_handler.end_press()
        self.pressed_keys.clear()
    
    def _check_stale_handlers(self):
        """Check for and fix any stale handler states."""
        self.decrease_handler.check_and_fix_stale_state()
        self.increase_handler.check_and_fix_stale_state()
    
    def _key_in_set_ignoring_modifiers(self, key: int, key_set: set) -> bool:
        """
        Check if a key (without modifiers) matches any key in the set.
        This is a fallback for when modifier state changes between press and release.
        """
        # Mask to extract just the key code without modifiers
        key_mask = 0x01FFFFFF  # Qt key codes are in the lower bits
        
        for combo in key_set:
            if (combo & key_mask) == key:
                return True
        return False
