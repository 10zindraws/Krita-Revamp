"""
    Plugin for Krita UI Redesign, Copyright (C) 2020 Kapyia, Pedro Reis
    Updated for Krita 5.2+ compatibility (2024)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


from PyQt5.QtWidgets import QToolButton, QSizePolicy
from PyQt5.QtCore import Qt, QSize, QTimer, QEvent
from .. import variables

# Button sizes - slightly larger for better usability
BUTTON_ICON_SIZE_EXPANDED = 16
BUTTON_MIN_HEIGHT_EXPANDED = 26
BUTTON_ICON_SIZE_COLLAPSED = 24
BUTTON_MIN_SIZE_COLLAPSED = 38


class ntToggleVisibleButton(QToolButton):
    """
    Toggle button for showing/hiding the widget pad content.
    Updated for Krita 5.2+ with hover activation feature.
    """
    
    def __init__(self, parent=None):
        super(ntToggleVisibleButton, self).__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setIconSize(QSize(BUTTON_ICON_SIZE_EXPANDED, BUTTON_ICON_SIZE_EXPANDED))
        self.setMinimumHeight(BUTTON_MIN_HEIGHT_EXPANDED)
        self._updateStyle()
        
        # Hover activation timer (300ms)
        self._hoverTimer = QTimer(self)
        self._hoverTimer.setSingleShot(True)
        self._hoverTimer.setInterval(300)
        self._hoverTimer.timeout.connect(self._onHoverActivate)
        self._hoverActivated = False  # Tracks if hover has already activated
        
        # Track if widget content is visible (for sizing)
        self._contentVisible = True
    
    def _updateStyle(self):
        """Update the button stylesheet."""
        try:
            self.setStyleSheet(variables.nu_toggle_button_style)
        except Exception:
            # Fallback style if variables not yet initialized
            pass
        
    def setArrow(self, alignment):
        if alignment == "right":
            self.setArrowType(Qt.ArrowType.RightArrow)
        else:
            self.setArrowType(Qt.ArrowType.LeftArrow)
    
    def setContentVisible(self, visible):
        """Update button size based on whether content is visible (expanded) or not (collapsed)."""
        self._contentVisible = visible
        if visible:
            # Expanded state - normal button
            self.setIconSize(QSize(BUTTON_ICON_SIZE_EXPANDED, BUTTON_ICON_SIZE_EXPANDED))
            self.setMinimumHeight(BUTTON_MIN_HEIGHT_EXPANDED)
            self.setMinimumWidth(0)  # Let it expand naturally
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        else:
            # Collapsed state - bigger square button
            self.setIconSize(QSize(BUTTON_ICON_SIZE_COLLAPSED, BUTTON_ICON_SIZE_COLLAPSED))
            self.setMinimumHeight(BUTTON_MIN_SIZE_COLLAPSED)
            self.setMinimumWidth(BUTTON_MIN_SIZE_COLLAPSED)
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    
    def enterEvent(self, event):
        """Start hover timer when mouse enters the button."""
        self._hoverActivated = False
        self._hoverTimer.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Stop hover timer and reset activation flag when mouse leaves."""
        self._hoverTimer.stop()
        self._hoverActivated = False
        super().leaveEvent(event)
    
    def _onHoverActivate(self):
        """Called when hover timer expires - activate the button once."""
        if not self._hoverActivated:
            self._hoverActivated = True
            self.click()  # Trigger button activation
        