# SPDX-License-Identifier: GPL-3.0-or-later
"""
Quick Brush Size Docker for Krita

Provides a dockable settings panel for configuring timing thresholds
and speed parameters for the Quick Brush Size plugin.
"""

from krita import DockWidget, DockWidgetFactory, DockWidgetFactoryBase
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSlider, QDoubleSpinBox, QSpinBox,
    QPushButton, QGroupBox, QScrollArea, QSizePolicy,
    QSpacerItem, QFrame, QApplication, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor

from .settings_manager import SettingsManager


DOCKER_STYLESHEET = """
/* Main container */
QWidget#dockerMain {
    background-color: palette(window);
}

/* Scroll area */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* Group boxes - clean, minimal headers */
QGroupBox {
    font-weight: bold;
    font-size: 11px;
    border: 1px solid palette(mid);
    border-radius: 4px;
    margin-top: 12px;
    padding: 8px 6px 6px 6px;
    background-color: palette(base);
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: palette(text);
    background-color: palette(base);
}

/* Labels */
QLabel {
    color: palette(text);
    font-size: 10px;
}

/* Sliders - thin track */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: palette(dark);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: palette(highlight);
    border: 1px solid palette(mid);
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover {
    background: palette(light);
    border: 1px solid palette(highlight);
}

QSlider::handle:horizontal:pressed {
    background: palette(highlight);
}

QSlider::sub-page:horizontal {
    background: palette(highlight);
    border-radius: 2px;
}

/* Spin boxes - compact and clean */
QDoubleSpinBox, QSpinBox {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 2px 4px;
    color: palette(text);
    font-size: 10px;
    selection-background-color: palette(highlight);
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid palette(highlight);
}

QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {
    width: 14px;
    border: none;
    background: palette(button);
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background: palette(mid);
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid palette(text);
    width: 0;
    height: 0;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid palette(text);
    width: 0;
    height: 0;
}

/* Buttons - modern flat style */
QPushButton {
    background-color: palette(button);
    border: 1px solid palette(mid);
    border-radius: 4px;
    padding: 5px 12px;
    color: palette(button-text);
    font-size: 10px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: palette(mid);
    border: 1px solid palette(dark);
}

QPushButton:pressed {
    background-color: palette(dark);
}

QPushButton#saveBtn {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
}

QPushButton#saveBtn:hover {
    background-color: palette(light);
}

QPushButton#resetBtn {
    color: palette(text);
    background-color: transparent;
    border: 1px solid palette(mid);
}

QPushButton#resetBtn:hover {
    background-color: palette(mid);
}

/* Scrollbar styling */
QScrollBar:vertical {
    background: palette(base);
    width: 8px;
    border: none;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: palette(mid);
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: palette(dark);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* Checkbox styling for threshold toggles */
QCheckBox {
    spacing: 4px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid palette(mid);
    border-radius: 3px;
    background-color: palette(base);
}

QCheckBox::indicator:checked {
    background-color: palette(highlight);
    border: 1px solid palette(highlight);
}

QCheckBox::indicator:hover {
    border: 1px solid palette(highlight);
}

QCheckBox::indicator:disabled {
    background-color: palette(mid);
    border: 1px solid palette(dark);
}
"""


class SettingRow(QWidget):
    """
    A single setting row with label, slider, and spin box.
    
    Supports both float (QDoubleSpinBox) and int (QSpinBox) values.
    """
    
    def __init__(self, key, meta, settings_manager, parent=None):
        super().__init__(parent)
        
        self.key = key
        self.settings_manager = settings_manager
        
        # Unpack metadata
        self.display_name, self.min_val, self.max_val, self.decimals, self.step, self.tooltip = meta
        
        # Determine if this is an integer setting
        self.is_integer = (self.decimals == 0)
        
        # Build UI
        self._setup_ui()
        
        # Load initial value
        self._load_value()
    
    def _setup_ui(self):
        """Set up the UI elements for this setting row."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)
        
        # Label - compact width
        self.label = QLabel(self.display_name)
        self.label.setToolTip(self.tooltip)
        self.label.setMinimumWidth(120)
        self.label.setMaximumWidth(140)
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.label)
        
        # Slider - thin track
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setToolTip(self.tooltip)
        self.slider.setMinimumWidth(80)
        self.slider.setMinimumHeight(16)
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Configure slider range (use integer steps for slider)
        if self.is_integer:
            self.slider.setMinimum(int(self.min_val))
            self.slider.setMaximum(int(self.max_val))
            self.slider.setSingleStep(int(self.step))
        else:
            # For floats, use scaled integer range
            self.slider_scale = 10 ** self.decimals
            self.slider.setMinimum(int(self.min_val * self.slider_scale))
            self.slider.setMaximum(int(self.max_val * self.slider_scale))
            self.slider.setSingleStep(int(self.step * self.slider_scale))
        
        layout.addWidget(self.slider)
        
        # Spin box (double or int)
        if self.is_integer:
            self.spinbox = QSpinBox()
            self.spinbox.setMinimum(int(self.min_val))
            self.spinbox.setMaximum(int(self.max_val))
            self.spinbox.setSingleStep(int(self.step))
        else:
            self.spinbox = QDoubleSpinBox()
            self.spinbox.setMinimum(self.min_val)
            self.spinbox.setMaximum(self.max_val)
            self.spinbox.setSingleStep(self.step)
            self.spinbox.setDecimals(self.decimals)
        
        self.spinbox.setToolTip(self.tooltip)
        self.spinbox.setMinimumWidth(60)
        self.spinbox.setMaximumWidth(75)
        self.spinbox.setFixedHeight(22)
        layout.addWidget(self.spinbox)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        
        # Flag to prevent circular updates
        self._updating = False
    
    def _load_value(self):
        """Load the current value from settings."""
        value = self.settings_manager.get(self.key)
        self.set_value(value)
    
    def set_value(self, value):
        """Set the displayed value without triggering settings update."""
        self._updating = True
        try:
            if self.is_integer:
                self.slider.setValue(int(value))
                self.spinbox.setValue(int(value))
            else:
                self.slider.setValue(int(value * self.slider_scale))
                self.spinbox.setValue(float(value))
        finally:
            self._updating = False
    
    def get_value(self):
        """Get the current value."""
        if self.is_integer:
            return self.spinbox.value()
        else:
            return self.spinbox.value()
    
    def _on_slider_changed(self, value):
        """Handle slider value change."""
        if self._updating:
            return
        
        self._updating = True
        try:
            if self.is_integer:
                actual_value = value
                self.spinbox.setValue(value)
            else:
                actual_value = value / self.slider_scale
                self.spinbox.setValue(actual_value)
            
            # Update settings (live)
            self.settings_manager.set(self.key, actual_value)
        finally:
            self._updating = False
    
    def _on_spinbox_changed(self, value):
        """Handle spinbox value change."""
        if self._updating:
            return
        
        self._updating = True
        try:
            if self.is_integer:
                self.slider.setValue(int(value))
            else:
                self.slider.setValue(int(value * self.slider_scale))
            
            # Update settings (live)
            self.settings_manager.set(self.key, value)
        finally:
            self._updating = False


class ThresholdSettingRow(QWidget):
    """
    A threshold setting row with checkbox toggle, label, slider, and spin box.
    
    The checkbox enables/disables the threshold (and its corresponding mode).
    At least one threshold must remain enabled at all times.
    """
    
    def __init__(self, key, meta, settings_manager, docker, parent=None):
        super().__init__(parent)
        
        self.key = key
        self.settings_manager = settings_manager
        self.docker = docker  # Reference to docker for coordination
        
        # Unpack metadata
        self.display_name, self.min_val, self.max_val, self.decimals, self.step, self.tooltip = meta
        
        # Always float for thresholds
        self.is_integer = False
        
        # Build UI
        self._setup_ui()
        
        # Load initial value
        self._load_value()
    
    def _setup_ui(self):
        """Set up the UI elements for this threshold row."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)
        
        # Checkbox - enables/disables this threshold
        self.checkbox = QCheckBox()
        self.checkbox.setToolTip("Enable or disable this mode")
        self.checkbox.setFixedWidth(18)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)
        
        # Label - compact width
        self.label = QLabel(self.display_name)
        self.label.setToolTip(self.tooltip)
        self.label.setMinimumWidth(120)
        self.label.setMaximumWidth(140)
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.label)
        
        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setToolTip(self.tooltip)
        self.slider.setMinimumWidth(80)
        self.slider.setMinimumHeight(16)
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # For floats, use scaled integer range
        self.slider_scale = 10 ** self.decimals
        self.slider.setMinimum(int(self.min_val * self.slider_scale))
        self.slider.setMaximum(int(self.max_val * self.slider_scale))
        self.slider.setSingleStep(int(self.step * self.slider_scale))
        
        layout.addWidget(self.slider)
        
        # Spin box (double for thresholds)
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setMinimum(self.min_val)
        self.spinbox.setMaximum(self.max_val)
        self.spinbox.setSingleStep(self.step)
        self.spinbox.setDecimals(self.decimals)
        
        self.spinbox.setToolTip(self.tooltip)
        self.spinbox.setMinimumWidth(60)
        self.spinbox.setMaximumWidth(75)
        self.spinbox.setFixedHeight(22)
        layout.addWidget(self.spinbox)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        
        # Flag to prevent circular updates
        self._updating = False
    
    def _load_value(self):
        """Load the current value from settings."""
        value = self.settings_manager.get(self.key)
        enabled = self.settings_manager.is_threshold_enabled(self.key)
        self.set_value(value)
        self.set_enabled_state(enabled)
    
    def set_value(self, value):
        """Set the displayed value without triggering settings update."""
        self._updating = True
        try:
            self.slider.setValue(int(value * self.slider_scale))
            self.spinbox.setValue(float(value))
        finally:
            self._updating = False
    
    def get_value(self):
        """Get the current value."""
        return self.spinbox.value()
    
    def is_checked(self):
        """Return whether the checkbox is checked."""
        return self.checkbox.isChecked()
    
    def set_enabled_state(self, enabled):
        """Set the enabled/checked state of this threshold."""
        self._updating = True
        try:
            self.checkbox.setChecked(enabled)
            self._update_controls_enabled(enabled)
        finally:
            self._updating = False
    
    def _update_controls_enabled(self, enabled):
        """Enable or disable the slider and spinbox based on checkbox state."""
        self.slider.setEnabled(enabled)
        self.spinbox.setEnabled(enabled)
        self.label.setEnabled(enabled)
    
    def _on_checkbox_changed(self, state):
        """Handle checkbox state change."""
        if self._updating:
            return
        
        is_checked = state == Qt.Checked
        
        # Check if this would leave no thresholds enabled
        if not is_checked:
            enabled_count = self.settings_manager.get_enabled_threshold_count()
            if enabled_count <= 1:
                # Can't uncheck the last one - revert
                self._updating = True
                self.checkbox.setChecked(True)
                self._updating = False
                return
        
        # Update the enabled state
        self._update_controls_enabled(is_checked)
        self.settings_manager.set_threshold_enabled(self.key, is_checked)
    
    def _on_slider_changed(self, value):
        """Handle slider value change."""
        if self._updating:
            return
        
        self._updating = True
        try:
            actual_value = value / self.slider_scale
            self.spinbox.setValue(actual_value)
            
            # Update settings (live)
            self.settings_manager.set(self.key, actual_value)
        finally:
            self._updating = False
    
    def _on_spinbox_changed(self, value):
        """Handle spinbox value change."""
        if self._updating:
            return
        
        self._updating = True
        try:
            self.slider.setValue(int(value * self.slider_scale))
            
            # Update settings (live)
            self.settings_manager.set(self.key, value)
        finally:
            self._updating = False


class QuickBrushSizeDocker(DockWidget):
    """
    Docker panel for Quick Brush Size settings.
    
    Displays all timing thresholds and speed parameters organized
    by mode (Holding, Tapping, Multiplier) as adjustable
    sliders with numerical displays.
    
    Timing thresholds have toggle checkboxes to enable/disable modes.
    At least one threshold must remain enabled.

    """
    
    DOCKER_TITLE = "Quick Brush Size"
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(self.DOCKER_TITLE)
        
        # Get settings manager
        self.settings_manager = SettingsManager.instance()
        
        # Store setting rows for bulk updates
        self.setting_rows = {}
        
        # Store threshold rows separately for toggle handling
        self.threshold_rows = {}
        
        # Build the UI
        self._setup_ui()
    
    def _setup_ui(self):
        # Main container widget
        main_widget = QWidget()
        main_widget.setObjectName("dockerMain")
        self.setWidget(main_widget)
        
        # Apply the sleek stylesheet
        main_widget.setStyleSheet(DOCKER_STYLESHEET)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(8)
        
        # Create groups for each category
        for group_name, setting_keys in SettingsManager.SETTING_GROUPS.items():
            group = self._create_setting_group(group_name, setting_keys)
            content_layout.addWidget(group)
        
        # Add stretch to push groups to top
        content_layout.addStretch()
        
        # Create button row
        button_row = self._create_button_row()
        content_layout.addWidget(button_row)
        
        scroll.setWidget(content_widget)
        
        # Main layout
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_setting_group(self, group_name, setting_keys):
        """Create a group box with settings for a specific mode."""
        group = QGroupBox(group_name)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(2)
        
        # Check if this is the Timing Thresholds group (uses ThresholdSettingRow)
        is_threshold_group = (group_name == "Timing Thresholds")
        
        for key in setting_keys:
            if key in SettingsManager.SETTING_META:
                meta = SettingsManager.SETTING_META[key]
                
                if is_threshold_group:
                    # Use ThresholdSettingRow with checkbox for thresholds
                    row = ThresholdSettingRow(key, meta, self.settings_manager, self)
                    self.threshold_rows[key] = row
                else:
                    # Use regular SettingRow for other settings
                    row = SettingRow(key, meta, self.settings_manager)
                
                self.setting_rows[key] = row
                layout.addWidget(row)
        
        return group
    
    def _create_button_row(self):
        """Create the bottom button row with styled buttons."""
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setContentsMargins(0, 12, 0, 4)
        layout.setSpacing(6)
        
        # Reset to Default button (subtle styling)
        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.setToolTip("Reset all settings to their original default values")
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self.reset_btn)
        
        # Expanding spacer
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Save button (primary action styling)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setToolTip("Save current settings permanently")
        self.save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.save_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setToolTip("Revert to last saved settings")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.cancel_btn)
        
        return button_widget
    
    def _on_reset_clicked(self):
        """Handle Reset to Default button click."""
        self.settings_manager.reset_to_defaults()
        self._update_all_rows()
    
    def _on_save_clicked(self):
        """Handle Save button click."""
        self.settings_manager.save()
    
    def _on_cancel_clicked(self):
        """Handle Cancel button click."""
        self.settings_manager.cancel()
        self._update_all_rows()
    
    def _update_all_rows(self):
        """Update all setting rows to reflect current settings."""
        for key, row in self.setting_rows.items():
            value = self.settings_manager.get(key)
            row.set_value(value)
        
        # Also update threshold enabled states
        for key, row in self.threshold_rows.items():
            enabled = self.settings_manager.is_threshold_enabled(key)
            row.set_enabled_state(enabled)
    
    def canvasChanged(self, canvas):
        """Called when the canvas changes. Required by DockWidget."""
        pass


# Docker ID for registration
DOCKER_ID = "quick_brush_size_docker"


def registerDocker():
    """
    Register the Quick Brush Size docker with Krita.
    
    This function creates and registers the dock widget factory
    using the correct Krita API signature.
    """
    app = __import__('krita').Krita.instance()
    dock_factory = DockWidgetFactory(
        DOCKER_ID,
        DockWidgetFactoryBase.DockRight,
        QuickBrushSizeDocker
    )
    app.addDockWidgetFactory(dock_factory)
