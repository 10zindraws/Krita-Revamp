# SPDX-License-Identifier: CC0-1.0

from .pyqt import (
    QWIDGETSIZE_MAX,
    pyqtSignal,
    QApplication,
    QResizeEvent,
    QPaintEvent,
    QPixmap,
    QAction,
    QMainWindow,
    QMouseEvent,
    QWheelEvent,
    QMenu,
    Qt,
    QPainter,
    QPen,
    QColor,
    QTabBar,
    QObject,
    QMdiSubWindow,
    QWidget,
    QEvent,
    QMdiArea,
    QRect,
    QTimer,
    QPoint,
    QIcon,
    QFont,
    QToolButton,
    QImage,
    QSize,
    QCursor,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QDockWidget,
    getEventGlobalPos,
    getEventPos,
    toPoint,
)

from krita import Window, View, Document
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Any
from types import SimpleNamespace

from .component import Component
from .options import getOpt
from .helper import Helper
from .i18n import i18n

try:
    from PyQt6 import QtGui
    QFontMetrics = QtGui.QFontMetrics
    QFontDatabase = QtGui.QFontDatabase
    PYQT_VERSION = 6
except ImportError:
    from PyQt5 import QtGui
    QFontMetrics = QtGui.QFontMetrics
    QFontDatabase = QtGui.QFontDatabase
    PYQT_VERSION = 5

import typing
import re
import math

TAB_BAR_HEIGHT = 34
TAB_TEXT_MAX_LEN = 30
TAB_SEPARATOR_COLOR = "#383838"  # Match krita-redesign ps_separator for 2px top tab line

# Browser Tabs Configuration
TAB_MAX_WIDTH = 200         # Maximum tab width in pixels (like browser tabs)
TAB_MIN_WIDTH = 50            # Minimum tab width before scrolling
TAB_PADDING = 24             # Padding between document name and close button, anly value 
                                             # <24 truncates the currently selected document's long name instead 
                                             # of expanding the tab to accomodate it for some reason
HIDE_TAB_ICON = True          # Hide the Krita logo/icon on tabs
EXPAND_SELECTED_TAB = True    # Expand selected tab to show full name

# Custom font settings
CUSTOM_FONT_FAMILY = "Adobe Clean"  # Font family name
CUSTOM_FONT_SIZE = 11               # Font size in points
CUSTOM_FONT_BOLD = True             # Use bold font

# Close button configuration - easy to adjust positioning and size
CLOSE_BUTTON_SIZE = 20              # Width and height of the close button in pixels
CLOSE_BUTTON_ICON_SIZE = 10         # Size of the X icon inside the button
CLOSE_BUTTON_MARGIN_TOP = 0         # Margin from top (positive = down)
CLOSE_BUTTON_MARGIN_RIGHT = 7       # Margin from right edge (positive = left)
CLOSE_BUTTON_MARGIN_BOTTOM = 10      # Margin from bottom (positive = up)
CLOSE_BUTTON_MARGIN_LEFT = 0        # Margin from left (positive = right)

# Left-click directional drag configuration
# Drag detection: left/right cones = normal tab reorder, top/bottom cones = split mode (like middle-click)
DRAG_DEADZONE = 10                  # Pixels to move before direction is detected (prevents accidental activation)
DRAG_VERTICAL_THRESHOLD = 40        # Vertical drag distance to activate split mode
DRAG_ANGLE_THRESHOLD = 45           # Angle in degrees from vertical axis for vertical detection cone

@dataclass
class MenuAction:
    text: str
    callback: typing.Callable[..., Any]
    separator: bool = False
    enabled: bool = True
    visible: bool = True


@dataclass
class ViewData:
    view: View
    win: QMdiSubWindow
    toolbar: "SplitToolbar | None"
    watcher: "SubWindowInterceptor | None"
    watcherCallback: typing.Callable[[object, Any], None] | None
    realignTick: int | None


class SubWindowInterceptor(QObject):
    def __init__(self, callback: typing.Callable[..., Any]):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            obj.destroyed.connect(self._callback)
        return False


class DockTabEventFilter(QObject):
    def __init__(self, callback: typing.Callable[[QTabBar], None]):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            widget = obj if isinstance(obj, QWidget) else None
            if not widget:
                return False
            tab_bar = widget if isinstance(widget, QTabBar) else None
            while not tab_bar and widget:
                widget = widget.parentWidget()
                if isinstance(widget, QTabBar):
                    tab_bar = widget
                    break
            if tab_bar:
                self._callback(tab_bar)
        return False


class TabDragRect(QWidget):
    def __init__(
        self,
        parent: QWidget | QMainWindow,
        color: QColor | None = None,
        altColor: QColor | None = None,
        text: str | None = None,
        textColor: QColor | None = None,
    ):
        super().__init__(parent)

        self._color = QColor(10, 10, 100, 100) if color is None else color
        self._altColor = altColor
        self._text = text
        self._textColor = textColor if textColor else Qt.GlobalColor.white

    def setText(self, text: str | None):
        self._text = text
        self.update()

    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        rect = self.rect()
        p.fillRect(rect, self._color)

        if self._altColor:
            stripe_width = 5
            pen = QPen(self._altColor, stripe_width * 2)
            p.setPen(pen)

            w, h = rect.width(), rect.height()
            for x in range(-h, w, stripe_width * 2):
                p.drawLine(x, 0, x + h, h)

        if self._text:
            p.setPen(self._textColor)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine,
                self._text,
            )


# Windowed Document Tab Configuration
WINDOWED_TAB_MIN_WIDTH = 200
WINDOWED_TAB_MIN_HEIGHT = 150
WINDOWED_TAB_TITLE_HEIGHT = 28
WINDOWED_TAB_RESIZE_MARGIN = 8  # Visual resize indicator zone inside content
WINDOWED_TAB_OUTER_MARGIN = 15   # Invisible resize border OUTSIDE the visual content
CORNER_SNAP_SIZE = 70  # Size of corner snap zones in pixels
CORNER_SNAP_HOVER_TIME = 1000  # Milliseconds to hover before snapping
CORNER_UNSNAP_DISTANCE = 40  # Pixels to drag before unsnapping


class CornerSnapZone(QWidget):
    """Visual indicator for corner snap zones - 70x70px striped squares."""
    
    def __init__(self, parent: QWidget, corner: str):
        super().__init__(parent)
        self._corner = corner  # "top-left", "top-right", "bottom-left", "bottom-right"
        self.setFixedSize(CORNER_SNAP_SIZE, CORNER_SNAP_SIZE)
        self.hide()
    
    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        rect = self.rect()
        
        # Background with transparency
        bg_color = QColor(10, 10, 100, 80)
        p.fillRect(rect, bg_color)
        
        # Diagonal blue stripes
        stripe_width = 5
        stripe_color = QColor(30, 100, 200, 150)
        pen = QPen(stripe_color, stripe_width * 2)
        p.setPen(pen)
        
        w, h = rect.width(), rect.height()
        for x in range(-h, w, stripe_width * 2):
            p.drawLine(x, 0, x + h, h)
        
        # Border
        border_pen = QPen(QColor(50, 120, 220), 2)
        p.setPen(border_pen)
        p.drawRect(rect.adjusted(1, 1, -1, -1))


class WindowedDocumentTab(QWidget):
    """
    A floating, resizable document window that stays on top of regular split panes.
    Created when a tab is dragged to an empty area.
    Can be:
    - Resized (canvas size)
    - Zoomed inside (like a subwindow)
    - Dragged (document moves visually with the drag)
    - Snapped to corners (70x70 zones at corners)
    - Reintegrated to tab bar by dropping on document tabs
    """
    
    closed = pyqtSignal(object)  # Emits self when closed
    reintegrated = pyqtSignal(object)  # Emits self when dropped on tab bar
    
    def __init__(
        self,
        parent: QWidget,
        controller: "SplitPane",
        view: View,
        subwindow: QMdiSubWindow,
        uid: int,
        title: str = "",
    ):
        super().__init__(parent)
        
        self._controller = controller
        self._helper = controller.helper()
        self._view = view
        self._subwindow = subwindow
        self._uid = uid
        self._title = title
        
        # Original subwindow state (stored when setting up, restored when reintegrating)
        self._originalSubwindowGeometry: QRect | None = None
        self._originalMinSize: QSize | None = None
        self._originalMaxSize: QSize | None = None
        self._originalWindowFlags: Qt.WindowType | None = None
        
        # State
        self._dragging = False
        self._resizing = False
        self._resizeEdge: str | None = None  # "left", "right", "top", "bottom", "topleft", etc.
        self._dragStart = QPoint()
        self._dragStartPos = QPoint()
        self._dragStartGeometry = QRect()
        
        # Corner snap state
        self._cornerSnapped: str | None = None  # "top-left", "top-right", "bottom-left", "bottom-right"
        self._cornerSnapTimer: QTimer | None = None
        self._hoveringCorner: str | None = None
        self._cornerSnapZones: dict[str, CornerSnapZone] = {}
        
        # Drag mode state
        self._inDragMode = False
        self._dragPlaceHolder: TabDragRect | None = None
        self._tabBarDropZone: TabDragRect | None = None
        
        # Setup appearance
        # Minimum size includes the invisible outer margin on all sides
        self.setMinimumSize(
            WINDOWED_TAB_MIN_WIDTH + WINDOWED_TAB_OUTER_MARGIN * 2,
            WINDOWED_TAB_MIN_HEIGHT + WINDOWED_TAB_OUTER_MARGIN * 2
        )
        self.setMouseTracking(True)
        
        # Make widget transparent so only the visual content area is visible
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set initial size (includes outer margin)
        self.resize(400 + WINDOWED_TAB_OUTER_MARGIN * 2, 300 + WINDOWED_TAB_OUTER_MARGIN * 2)
        
        # Always on top by raising
        self.raise_()
        self.show()
        
        # Reparent the subwindow's content
        self._setupSubwindow()
    
    def _setupSubwindow(self):
        """Setup the subwindow to be displayed within this windowed tab."""
        if self._subwindow:
            # Store original state before modifying
            self._originalSubwindowGeometry = self._subwindow.geometry()
            self._originalMinSize = self._subwindow.minimumSize()
            self._originalMaxSize = self._subwindow.maximumSize()
            self._originalWindowFlags = self._subwindow.windowFlags()
            
            # Configure subwindow for display in our container
            self._subwindow.setParent(self)
            
            # CRITICAL: Use FramelessWindowHint to completely hide the QMdiSubWindow's
            # title bar (Krita icon, document name, min/max/close buttons).
            # This prevents the subwindow's frame from conflicting with our custom
            # WindowedDocumentTab title bar and resize handles.
            self._subwindow.setWindowFlags(
                Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint
            )
            
            # Install event filter to intercept mouse events near edges
            # so our resize handles take precedence over the subwindow
            self._subwindow.installEventFilter(self)
            
            # Position subwindow in content area (accounting for outer margin)
            m = WINDOWED_TAB_OUTER_MARGIN
            content_width = self.width() - m * 2
            content_height = self.height() - m * 2 - WINDOWED_TAB_TITLE_HEIGHT
            self._subwindow.setFixedWidth(content_width)
            self._subwindow.setFixedHeight(content_height)
            self._subwindow.move(m, m + WINDOWED_TAB_TITLE_HEIGHT)
            self._subwindow.show()
    
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Event filter for the subwindow to intercept mouse events near edges.
        This ensures our resize handles take precedence over the subwindow's content.
        """
        if obj == self._subwindow:
            event_type = event.type()
            
            # Intercept mouse events that might be near our resize edges
            if event_type in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseMove,
            ):
                # Get position relative to this WindowedDocumentTab
                try:
                    local_pos = self._subwindow.mapToParent(getEventPos(event))
                except Exception:
                    return False
                
                # Check if near any resize edge
                edge = self._getEdgeAtPos(local_pos)
                if edge is not None:
                    # Forward the event to ourselves for resize handling
                    # Create a new mouse event with proper coordinates
                    new_event = QMouseEvent(
                        event_type,
                        local_pos,
                        getEventGlobalPos(event),
                        event.button(),
                        event.buttons(),
                        event.modifiers(),
                    )
                    # Handle it ourselves
                    if event_type == QEvent.Type.MouseButtonPress:
                        self.mousePressEvent(new_event)
                    elif event_type == QEvent.Type.MouseButtonRelease:
                        self.mouseReleaseEvent(new_event)
                    elif event_type == QEvent.Type.MouseMove:
                        self.mouseMoveEvent(new_event)
                    return True  # Event handled, don't pass to subwindow
        
        return False  # Let the event pass through normally
    
    def view(self) -> View:
        return self._view
    
    def subwindow(self) -> QMdiSubWindow:
        return self._subwindow
    
    def uid(self) -> int:
        return self._uid
    
    def title(self) -> str:
        return self._title
    
    def setTitle(self, title: str):
        self._title = title
        self.update()
    
    def isCornerSnapped(self) -> bool:
        return self._cornerSnapped is not None
    
    def cornerSnap(self) -> str | None:
        return self._cornerSnapped
    
    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        m = WINDOWED_TAB_OUTER_MARGIN
        
        # Content rect is inset by the invisible outer margin
        content_rect = self.rect().adjusted(m, m, -m, -m)
        
        # Background (only in content area)
        p.fillRect(content_rect, QColor("#2a2a2a"))
        
        # Title bar
        title_rect = QRect(content_rect.x(), content_rect.y(), content_rect.width(), WINDOWED_TAB_TITLE_HEIGHT)
        p.fillRect(title_rect, QColor("#3a3a3a"))
        
        # Title text
        p.setPen(QColor("#ffffff"))
        text_rect = title_rect.adjusted(8, 0, -30, 0)
        elided_title = p.fontMetrics().elidedText(
            self._title, Qt.TextElideMode.ElideRight, text_rect.width()
        )
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_title)
        
        # Close button area (visual indicator) - positioned relative to content rect
        close_rect = QRect(content_rect.right() - 24, content_rect.y() + 4, 20, 20)
        p.setPen(QColor("#888888"))
        p.drawLine(close_rect.x() + 5, close_rect.y() + 5, close_rect.right() - 5, close_rect.bottom() - 5)
        p.drawLine(close_rect.right() - 5, close_rect.y() + 5, close_rect.x() + 5, close_rect.bottom() - 5)
        
        # Border around content area
        border_color = QColor("#555555") if not self._cornerSnapped else QColor("#4488cc")
        p.setPen(QPen(border_color, 2))
        p.drawRect(content_rect.adjusted(1, 1, -1, -1))
        
        # Resize handles visual (subtle corners) - in content area
        if not self._cornerSnapped:
            p.setPen(QPen(QColor("#666666"), 1))
            # Bottom-right corner of content
            p.drawLine(content_rect.right() - 12, content_rect.bottom() - 2, 
                       content_rect.right() - 2, content_rect.bottom() - 12)
            p.drawLine(content_rect.right() - 8, content_rect.bottom() - 2, 
                       content_rect.right() - 2, content_rect.bottom() - 8)
    
    def _getEdgeAtPos(self, pos: QPoint) -> str | None:
        """
        Determine which resize edge/corner the mouse is over.
        The resize zones are in the invisible outer margin (WINDOWED_TAB_OUTER_MARGIN)
        plus a small inner zone (WINDOWED_TAB_RESIZE_MARGIN) for easier grabbing.
        """
        rect = self.rect()
        m = WINDOWED_TAB_OUTER_MARGIN
        inner_margin = WINDOWED_TAB_RESIZE_MARGIN
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        
        # Content area bounds (where the visual content is drawn)
        content_left = m
        content_top = m
        content_right = w - m
        content_bottom = h - m
        
        # Title bar is in content area, from content_top to content_top + TITLE_HEIGHT
        title_bar_bottom = content_top + WINDOWED_TAB_TITLE_HEIGHT
        close_button_left = content_right - 30
        
        # Check if in title bar drag area (not close button, not in resize zone)
        in_title_bar = (y >= content_top and y < title_bar_bottom and 
                        x >= content_left and x < close_button_left)
        
        # Edge detection: outer margin zone + inner resize margin inside content
        # Left edge: 0 to content_left + inner_margin
        # Right edge: content_right - inner_margin to w
        # Top edge: 0 to content_top + inner_margin  
        # Bottom edge: content_bottom - inner_margin to h
        
        left = x < (content_left + inner_margin)
        right = x > (content_right - inner_margin)
        top = y < (content_top + inner_margin)
        bottom = y > (content_bottom - inner_margin)
        
        # Don't detect top edge if we're in the title bar area (for dragging)
        # But DO detect if we're in the invisible margin above the content
        if in_title_bar and y >= content_top:
            top = False
        
        # If corner snapped, only allow resizing on non-snapped sides
        if self._cornerSnapped:
            if self._cornerSnapped == "top-left":
                left = False
                top = False
            elif self._cornerSnapped == "top-right":
                right = False
                top = False
            elif self._cornerSnapped == "bottom-left":
                left = False
                bottom = False
            elif self._cornerSnapped == "bottom-right":
                right = False
                bottom = False
        
        if left and top:
            return "topleft"
        elif right and top:
            return "topright"
        elif left and bottom:
            return "bottomleft"
        elif right and bottom:
            return "bottomright"
        elif left:
            return "left"
        elif right:
            return "right"
        elif top:
            return "top"
        elif bottom:
            return "bottom"
        return None
    
    def _updateCursor(self, pos: QPoint):
        """Update cursor based on position."""
        edge = self._getEdgeAtPos(pos)
        m = WINDOWED_TAB_OUTER_MARGIN
        
        if edge in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in ("topleft", "bottomright"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ("topright", "bottomleft"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif (pos.y() >= m and pos.y() < m + WINDOWED_TAB_TITLE_HEIGHT and 
              pos.x() >= m and pos.x() < self.width() - m - 30):
            # In title bar area (excluding close button)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        
        # Activate this windowed tab's view when clicked
        self._activateView()
        
        pos = toPoint(getEventPos(event))
        m = WINDOWED_TAB_OUTER_MARGIN
        
        # Check for close button click (positioned relative to content area)
        close_rect = QRect(self.width() - m - 24, m + 4, 20, 20)
        if close_rect.contains(pos):
            self._closeAndRestore()
            return
        
        # Check for resize edge
        edge = self._getEdgeAtPos(pos)
        if edge:
            self._resizing = True
            self._resizeEdge = edge
            self._dragStart = toPoint(getEventGlobalPos(event))
            self._dragStartGeometry = self.geometry()
            return
        
        # Check for title bar drag (title bar is in content area)
        if pos.y() >= m and pos.y() < m + WINDOWED_TAB_TITLE_HEIGHT:
            # Check unsnap distance if corner snapped
            self._dragging = True
            self._dragStart = toPoint(getEventGlobalPos(event))
            self._dragStartPos = self.pos()
            self._dragStartGeometry = self.geometry()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        
        super().mousePressEvent(event)
    
    def _activateView(self):
        """Activate this windowed tab's view, triggering tool switch if needed."""
        helper = self._helper
        mdi = helper.getMdi()
        
        if mdi and self._subwindow:
            # Set this subwindow as active - this triggers view change
            mdi.setActiveSubWindow(self._subwindow)
            # Raise this windowed tab to ensure it stays on top
            self.raise_()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        pos = toPoint(getEventPos(event))
        globalPos = toPoint(getEventGlobalPos(event))
        
        if self._resizing and self._resizeEdge:
            self._handleResize(globalPos)
            return
        
        if self._dragging:
            self._handleDrag(globalPos)
            return
        
        # Update cursor
        self._updateCursor(pos)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        
        if self._resizing:
            self._resizing = False
            self._resizeEdge = None
            self._resizeSubwindow()
            self.unsetCursor()
        
        if self._dragging:
            self._finishDrag(toPoint(getEventGlobalPos(event)))
            self._dragging = False
            self.unsetCursor()
        
        super().mouseReleaseEvent(event)
    
    def _handleResize(self, globalPos: QPoint):
        """Handle resizing based on edge being dragged."""
        dx = globalPos.x() - self._dragStart.x()
        dy = globalPos.y() - self._dragStart.y()
        
        geom = QRect(self._dragStartGeometry)
        min_w = WINDOWED_TAB_MIN_WIDTH + WINDOWED_TAB_OUTER_MARGIN * 2
        min_h = WINDOWED_TAB_MIN_HEIGHT + WINDOWED_TAB_OUTER_MARGIN * 2
        
        if "left" in self._resizeEdge:
            new_x = geom.x() + dx
            new_width = geom.width() - dx
            if new_width >= min_w:
                geom.setX(new_x)
                geom.setWidth(new_width)
        
        if "right" in self._resizeEdge:
            new_width = geom.width() + dx
            if new_width >= min_w:
                geom.setWidth(new_width)
        
        if "top" in self._resizeEdge:
            new_y = geom.y() + dy
            new_height = geom.height() - dy
            if new_height >= min_h:
                geom.setY(new_y)
                geom.setHeight(new_height)
        
        if "bottom" in self._resizeEdge:
            new_height = geom.height() + dy
            if new_height >= min_h:
                geom.setHeight(new_height)
        
        self.setGeometry(geom)
        self._resizeSubwindow()
    
    def _resizeSubwindow(self):
        """Resize the contained subwindow to fit within the content area."""
        if self._subwindow:
            m = WINDOWED_TAB_OUTER_MARGIN
            # Content area dimensions (excluding outer margin)
            content_width = self.width() - m * 2
            content_height = self.height() - m * 2 - WINDOWED_TAB_TITLE_HEIGHT
            
            self._subwindow.setFixedWidth(content_width)
            self._subwindow.setFixedHeight(content_height)
            # Position at margin offset, below title bar
            self._subwindow.move(m, m + WINDOWED_TAB_TITLE_HEIGHT)
    
    def _handleDrag(self, globalPos: QPoint):
        """Handle dragging the windowed tab."""
        dx = globalPos.x() - self._dragStart.x()
        dy = globalPos.y() - self._dragStart.y()
        distance = (dx * dx + dy * dy) ** 0.5
        
        # If corner snapped, need to exceed unsnap distance before moving
        if self._cornerSnapped:
            if distance < CORNER_UNSNAP_DISTANCE:
                return
            else:
                # Unsnap
                self._cornerSnapped = None
                self._dragStart = globalPos
                self._dragStartPos = self.pos()
        
        # Move the windowed tab
        new_pos = QPoint(
            self._dragStartPos.x() + dx,
            self._dragStartPos.y() + dy
        )
        self.move(new_pos)
        
        # Show drop zones and check for snapping
        self._updateDragState(globalPos)
    
    def _updateDragState(self, globalPos: QPoint):
        """Update visual indicators during drag."""
        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        
        if not qwin or not mdi:
            return
        
        # Show corner snap zones
        self._showCornerSnapZones()
        
        # Check for tab bar hover
        self._checkTabBarHover(globalPos)
        
        # Check for corner hover
        self._checkCornerHover(globalPos)
    
    def _showCornerSnapZones(self):
        """Show the 70x70 corner snap zones."""
        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        
        if not qwin or not mdi:
            return
        
        mdi_rect = mdi.rect()
        mdi_pos = mdi.mapTo(qwin, QPoint(0, 0))
        
        corners = {
            "top-left": QPoint(mdi_pos.x(), mdi_pos.y()),
            "top-right": QPoint(mdi_pos.x() + mdi_rect.width() - CORNER_SNAP_SIZE, mdi_pos.y()),
            "bottom-left": QPoint(mdi_pos.x(), mdi_pos.y() + mdi_rect.height() - CORNER_SNAP_SIZE),
            "bottom-right": QPoint(
                mdi_pos.x() + mdi_rect.width() - CORNER_SNAP_SIZE,
                mdi_pos.y() + mdi_rect.height() - CORNER_SNAP_SIZE
            ),
        }
        
        for corner_name, corner_pos in corners.items():
            if corner_name not in self._cornerSnapZones:
                zone = CornerSnapZone(qwin, corner_name)
                zone.hide()
                self._cornerSnapZones[corner_name] = zone
            
            zone = self._cornerSnapZones[corner_name]
            zone.move(corner_pos)
    
    def _hideCornerSnapZones(self):
        """Hide all corner snap zones."""
        for zone in self._cornerSnapZones.values():
            zone.hide()
    
    def _checkTabBarHover(self, globalPos: QPoint):
        """Check if hovering over any tab bar for reintegration."""
        helper = self._helper
        qwin = helper.getQwin()
        
        if not qwin:
            return
        
        # Find all SplitToolbar tab bars
        topSplit = self._controller.topSplit()
        if not topSplit:
            return
        
        localPos = qwin.mapFromGlobal(globalPos)
        
        # Check each split's toolbar
        target_toolbar = self._findToolbarAt(topSplit, localPos)
        
        if target_toolbar:
            # Show tab bar drop indicator
            if self._tabBarDropZone is None:
                palette = self._controller.colors()
                if palette:
                    color = QColor(palette.tabActive)
                    color.setAlpha(100)
                    self._tabBarDropZone = TabDragRect(qwin, color=color)
            
            toolbar_rect = target_toolbar.globalRect()
            self._tabBarDropZone.setGeometry(toolbar_rect)
            self._tabBarDropZone.show()
            self._tabBarDropZone.raise_()
        else:
            if self._tabBarDropZone:
                self._tabBarDropZone.hide()
    
    def _findToolbarAt(self, split: "Split", pos: QPoint) -> "SplitToolbar | None":
        """Recursively find a toolbar at the given position."""
        if split.state() == Split.STATE_COLLAPSED:
            toolbar = split.toolbar()
            if toolbar and toolbar.globalRect().contains(pos):
                return toolbar
        elif split.state() == Split.STATE_SPLIT:
            first = split.first()
            second = split.second()
            if first:
                result = self._findToolbarAt(first, pos)
                if result:
                    return result
            if second:
                result = self._findToolbarAt(second, pos)
                if result:
                    return result
        return None
    
    def _checkCornerHover(self, globalPos: QPoint):
        """Check if hovering over any corner snap zone."""
        helper = self._helper
        qwin = helper.getQwin()
        
        if not qwin:
            return
        
        localPos = qwin.mapFromGlobal(globalPos)
        
        hovering_corner = None
        for corner_name, zone in self._cornerSnapZones.items():
            zone_rect = QRect(zone.pos(), zone.size())
            if zone_rect.contains(localPos):
                hovering_corner = corner_name
                break
        
        if hovering_corner != self._hoveringCorner:
            self._hoveringCorner = hovering_corner
            for corner_name, zone in self._cornerSnapZones.items():
                if corner_name == hovering_corner:
                    zone.show()
                    zone.raise_()
                else:
                    zone.hide()
            
            # Cancel existing timer
            if self._cornerSnapTimer:
                self._cornerSnapTimer.stop()
                self._cornerSnapTimer = None
            
            # Start new timer if hovering over a corner
            if hovering_corner:
                self._cornerSnapTimer = QTimer()
                self._cornerSnapTimer.setSingleShot(True)
                self._cornerSnapTimer.timeout.connect(
                    lambda c=hovering_corner: self._onCornerSnapTimeout(c)
                )
                self._cornerSnapTimer.start(CORNER_SNAP_HOVER_TIME)
    
    def _onCornerSnapTimeout(self, corner: str):
        """Called when corner hover time has elapsed."""
        if self._hoveringCorner == corner and self._dragging:
            self._snapToCorner(corner)
    
    def _snapToCorner(self, corner: str):
        """Snap the windowed tab to a corner."""
        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        
        if not qwin or not mdi:
            return
        
        self._cornerSnapped = corner
        
        mdi_rect = mdi.rect()
        mdi_pos = mdi.mapTo(qwin, QPoint(0, 0))
        
        # Account for outer margin so the VISUAL content aligns with the corner
        # The widget is larger than its visual content by OUTER_MARGIN on each side
        m = WINDOWED_TAB_OUTER_MARGIN
        
        # Determine position based on corner
        # Offset by -m so the visual content (not the invisible margin) touches the edge
        if corner == "top-left":
            new_pos = QPoint(mdi_pos.x() - m, mdi_pos.y() - m)
        elif corner == "top-right":
            new_pos = QPoint(mdi_pos.x() + mdi_rect.width() - self.width() + m, mdi_pos.y() - m)
        elif corner == "bottom-left":
            new_pos = QPoint(mdi_pos.x() - m, mdi_pos.y() + mdi_rect.height() - self.height() + m)
        elif corner == "bottom-right":
            new_pos = QPoint(
                mdi_pos.x() + mdi_rect.width() - self.width() + m,
                mdi_pos.y() + mdi_rect.height() - self.height() + m
            )
        else:
            return
        
        self.move(new_pos)
        self.update()
    
    def _finishDrag(self, globalPos: QPoint):
        """Handle end of drag - check for reintegration or corner snap."""
        helper = self._helper
        qwin = helper.getQwin()
        
        # Hide corner snap zones
        self._hideCornerSnapZones()
        
        # Cancel corner snap timer
        if self._cornerSnapTimer:
            self._cornerSnapTimer.stop()
            self._cornerSnapTimer = None
        
        if not qwin:
            return
        
        localPos = qwin.mapFromGlobal(globalPos)
        
        # Check for tab bar drop (reintegration)
        topSplit = self._controller.topSplit()
        if topSplit:
            target_toolbar = self._findToolbarAt(topSplit, localPos)
            if target_toolbar:
                self._reintegrate(target_toolbar.split())
                return
        
        # Check for corner snap
        if self._hoveringCorner:
            self._snapToCorner(self._hoveringCorner)
        
        # Hide tab bar drop zone
        if self._tabBarDropZone:
            self._tabBarDropZone.deleteLater()
            self._tabBarDropZone = None
        
        self._hoveringCorner = None
    
    def _reintegrate(self, split: "Split"):
        """Convert this windowed tab back into a regular tabbed document."""
        helper = self._helper
        mdi = helper.getMdi()
        
        if not mdi:
            return
        
        # Hide indicators
        if self._tabBarDropZone:
            self._tabBarDropZone.deleteLater()
            self._tabBarDropZone = None
        
        self._hideCornerSnapZones()
        
        # Restore subwindow to MDI area properly
        if self._subwindow:
            # Remove our event filter before restoring
            self._subwindow.removeEventFilter(self)
            
            # Clear the fixed size constraints that were set for windowed display
            self._subwindow.setMinimumSize(0, 0)
            self._subwindow.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
            
            # Set proper window flags before adding to MDI
            self._subwindow.setWindowFlags(Qt.WindowType.SubWindow)
            
            # CRITICAL: Use addSubWindow to properly re-add to MDI's subwindow list
            # Simply setting parent doesn't add it back to mdi.subWindowList()
            mdi.addSubWindow(self._subwindow)
            
            # Show maximized (normal state for tabbed view)
            self._subwindow.showMaximized()
            self._subwindow.raise_()
        
        # Signal reintegration (so controller can remove from windowed tabs list)
        self.reintegrated.emit(self)
        
        # Trigger sync to the target split - this will create the tab
        # NOTE: Do NOT update viewData.toolbar here - syncView needs to detect
        # that the tab is missing from the toolbar and add it
        self._controller.syncView(view=self._view, split=split)
        
        # Clean up this windowed tab widget
        self.deleteLater()
    
    def _closeAndRestore(self):
        """Close and restore the document to its original split."""
        helper = self._helper
        mdi = helper.getMdi()
        topSplit = self._controller.topSplit()
        
        if mdi and self._subwindow:
            # Remove our event filter before restoring
            self._subwindow.removeEventFilter(self)
            
            # Clear the fixed size constraints that were set for windowed display
            self._subwindow.setMinimumSize(0, 0)
            self._subwindow.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
            
            # Set proper window flags before adding to MDI
            self._subwindow.setWindowFlags(Qt.WindowType.SubWindow)
            
            # CRITICAL: Use addSubWindow to properly re-add to MDI's subwindow list
            mdi.addSubWindow(self._subwindow)
            
            # Show maximized
            self._subwindow.showMaximized()
            self._subwindow.raise_()
        
        # Signal closed
        self.closed.emit(self)
        
        # Sync to default split - let syncView handle toolbar update and tab creation
        if topSplit:
            defaultSplit = topSplit.firstMostSplit()
            if defaultSplit:
                self._controller.syncView(view=self._view, split=defaultSplit)
        
        self.deleteLater()

    def closeDocument(self) -> bool:
        """Close the document backing this windowed tab."""
        if not self._subwindow:
            return False
        if not self._subwindow.close():
            return False
        self.closed.emit(self)
        self.deleteLater()
        return True
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._resizeSubwindow()


class SplitTabs(QTabBar):
    tabPress = pyqtSignal(QMouseEvent, int)
    tabRelease = pyqtSignal(QMouseEvent, int)
    
    # Class-level cached close icon (desaturated)
    CloseIcon: QIcon | None = None

    def __init__(self, parent: "SplitToolbar", controller: "SplitPane"):
        super().__init__(parent)
        self._wheelAccumulator = 0

        self._controller = controller
        self._helper = controller.helper()
        self._dragIndex = -1
        self._dragTimer: QTimer | None = None
        self._dragPos: QPoint | None = None
        self._dragStart = QPoint()
        self._dragPlaceHolder = None
        self._dropPlaceHolder = None
        self._dropAction: (
            typing.Literal[
                "makeSplitAtEdge",
                "makeSplitBetween",
                "makeSplitLeft",
                "makeSplitRight",
                "makeSplitAbove",
                "makeSplitBelow",
                "transferTab",
            ]
            | None
        ) = None
        self._dropSplit: Split | None = None
        self._dropEdge: Qt.AnchorPoint | None = None
        
        # Browser tabs state
        self._custom_font: QFont | None = None
        self._last_width = 0
        self._last_count = 0
        self._last_current_index = -1
        self._applying_style = False
        
        # Left-click directional drag state
        self._leftDragStart: QPoint | None = None  # Starting position of left-click drag
        self._leftDragIndex: int = -1              # Tab index being dragged with left-click
        self._leftDragMode: typing.Literal["detecting", "horizontal", "vertical"] | None = None
        
        # Initialize the desaturated close icon if not already done
        if SplitTabs.CloseIcon is None:
            SplitTabs.CloseIcon = self._createDesaturatedCloseIcon()

        self.setExpanding(False)
        self.setMouseTracking(True)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setUsesScrollButtons(True)
        self.tabCloseRequested.connect(self.purgeTab)
        self.setMinimumHeight(0)
        self.setMinimumWidth(0)
        
        # Set elide mode for text truncation
        elide_mode = Qt.TextElideMode.ElideRight if PYQT_VERSION == 6 else Qt.ElideRight
        self.setElideMode(elide_mode)
        
        # Setup custom font
        self._setupCustomFont()

        self.currentChanged.connect(self.onCurrentChange)
    
    def _createDesaturatedCloseIcon(self) -> QIcon:
        """
        Create a desaturated (grayscale) close icon using Krita's window-close icon.
        Falls back to the built-in close-tab icon if window-close is not available.
        """
        try:
            # Try to get the window-close icon from Krita's theme
            useDarkIcons = self._helper.useDarkIcons()
            
            # Try different icon sources
            icon_paths = [
                ":/dark_window-close.svg" if useDarkIcons else ":/light_window-close.svg",
                ":/dark_close-tab.svg" if useDarkIcons else ":/light_close-tab.svg",
            ]
            
            pixmap = None
            for path in icon_paths:
                pix = QPixmap(path)
                if not pix.isNull():
                    pixmap = pix
                    break
            
            if pixmap is None or pixmap.isNull():
                # Fallback: create a simple X icon
                return self._createSimpleCloseIcon()
            
            # Scale to desired size
            pixmap = pixmap.scaled(
                CLOSE_BUTTON_ICON_SIZE, CLOSE_BUTTON_ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio if PYQT_VERSION == 6 else Qt.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation if PYQT_VERSION == 6 else Qt.SmoothTransformation
            )
            
            # Convert to image for desaturation
            image = pixmap.toImage()
               
            brightness_mul = 100   # >1.0 = brighter (try 1.1–1.6)
            brightness_add = 40     # adds a constant lift (try 0–40)
            
            # Desaturate the image (convert to grayscale while preserving alpha)
            for y in range(image.height()):
                for x in range(image.width()):
                    pixel = image.pixelColor(x, y)
                    # Calculate grayscale value using luminance formula
                    gray = int(0.299 * pixel.red() + 0.587 * pixel.green() + 0.114 * pixel.blue())
                    
                    # brighten while staying grayscale
                    gray = int(gray * brightness_mul + brightness_add)
                    gray = max(0, min(255, gray))  # clamp
                    
                    # Set the pixel to grayscale while preserving alpha
                    pixel.setRed(gray)
                    pixel.setGreen(gray)
                    pixel.setBlue(gray)
                    image.setPixelColor(x, y, pixel)
            
            # Convert back to pixmap and create icon
            desaturated_pixmap = QPixmap.fromImage(image)
            return QIcon(desaturated_pixmap)
            
        except Exception as e:
            print(f"[SplitTabs] Error creating desaturated close icon: {e}")
            return self._createSimpleCloseIcon()
    
    def _createSimpleCloseIcon(self) -> QIcon:
        """Create a simple X close icon as fallback."""
        size = CLOSE_BUTTON_ICON_SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent if PYQT_VERSION == 6 else Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing if PYQT_VERSION == 6 else QPainter.Antialiasing)
        
        # Draw X with gray color
        pen = QPen(QColor(128, 128, 128))
        pen.setWidth(2)
        painter.setPen(pen)
        
        margin = 2
        painter.drawLine(margin, margin, size - margin, size - margin)
        painter.drawLine(size - margin, margin, margin, size - margin)
        
        painter.end()
        return QIcon(pixmap)

    def _setupCustomFont(self):
        """Set up the custom font for tab text."""
        if not CUSTOM_FONT_FAMILY:
            return
        
        try:
            font = QFont(CUSTOM_FONT_FAMILY)
            font_db = QFontDatabase()
            available_families = font_db.families()
            
            matched_family = None
            for family in available_families:
                if family.lower() == CUSTOM_FONT_FAMILY.lower():
                    matched_family = family
                    break
                if CUSTOM_FONT_FAMILY.lower().replace(" ", "") == family.lower().replace(" ", ""):
                    matched_family = family
                    break
            
            if matched_family:
                font = QFont(matched_family)
            
            if CUSTOM_FONT_SIZE:
                font.setPointSize(CUSTOM_FONT_SIZE)
            
            if CUSTOM_FONT_BOLD:
                font_weight = QFont.Weight.Bold if PYQT_VERSION == 6 else QFont.Bold
                font.setWeight(font_weight)
            
            self._custom_font = font
            self.setFont(font)
            
        except Exception as e:
            print(f"[SplitTabs] Error setting up custom font: {e}")
    
    def _calculateTabTextWidth(self, index: int) -> int:
        """Calculate the width needed to display a tab's full text."""
        if index < 0 or index >= self.count():
            return TAB_MAX_WIDTH
        
        text = self.tabText(index)
        if not text:
            return TAB_MIN_WIDTH
        
        font = self._custom_font if self._custom_font else self.font()
        fm = QFontMetrics(font)
        
        text_width = fm.horizontalAdvance(text) if hasattr(fm, 'horizontalAdvance') else fm.width(text)
        total_width = text_width + TAB_PADDING
        
        return total_width
    
    def _calculateTabWidth(self, exclude_selected_extra: int = 0) -> int:
        """Calculate optimal tab width based on available space and tab count."""
        tab_count = self.count()
        if tab_count == 0:
            return TAB_MAX_WIDTH
        
        available_width = self.width() - exclude_selected_extra
        tabs_to_distribute = tab_count - 1 if exclude_selected_extra > 0 and tab_count > 1 else tab_count
        
        ideal_total = tabs_to_distribute * TAB_MAX_WIDTH
        
        if ideal_total <= available_width:
            return TAB_MAX_WIDTH
        else:
            calculated_width = available_width // tabs_to_distribute if tabs_to_distribute > 0 else TAB_MAX_WIDTH
            
            if calculated_width < TAB_MIN_WIDTH:
                return TAB_MIN_WIDTH
            elif calculated_width > TAB_MAX_WIDTH:
                return TAB_MAX_WIDTH
            else:
                return calculated_width
    
    def updateTabWidths(self):
        """Apply the calculated tab width using stylesheets."""
        if self._applying_style:
            return
        
        current_width = self.width()
        current_count = self.count()
        current_index = self.currentIndex()
        
        # Only update if something changed
        if (current_width == self._last_width and 
            current_count == self._last_count and 
            current_index == self._last_current_index):
            return
        
        self._last_width = current_width
        self._last_count = current_count
        self._last_current_index = current_index
        
        if current_count == 0:
            return
        
        self._applying_style = True
        
        try:
            selected_tab_width = 0
            selected_extra_width = 0
            
            # Calculate selected tab width if expansion is enabled
            if EXPAND_SELECTED_TAB and current_index >= 0:
                selected_tab_width = self._calculateTabTextWidth(current_index)
                if selected_tab_width > TAB_MAX_WIDTH:
                    selected_extra_width = selected_tab_width - TAB_MAX_WIDTH
                else:
                    selected_tab_width = 0  # No expansion needed
            
            tab_width = self._calculateTabWidth(selected_extra_width)
            
            # Get existing style and remove our previous width styling
            existing_style = self.styleSheet() or ""
            marker = "/* BrowserTabsWidths */"
            if marker in existing_style:
                start = existing_style.find(marker)
                end = existing_style.find(marker, start + len(marker))
                if end > start:
                    existing_style = existing_style[:start] + existing_style[end + len(marker):]
            
            # Build selected tab expansion style
            ps_separator = TAB_SEPARATOR_COLOR
            
            selected_style = ""
            if selected_tab_width > 0:
                selected_style = f"""
SplitTabs::tab:selected {{
    min-width: {selected_tab_width}px;
    max-width: {selected_tab_width}px;
    border-top: 3px solid {ps_separator};
}}
"""
            
            width_style = f"""
{marker}
SplitTabs::tab {{
    min-width: {TAB_MIN_WIDTH}px;
    max-width: {tab_width}px;
    border-top: 3px solid {ps_separator};
}}
{selected_style}
{marker}
"""
            self.setStyleSheet(existing_style + width_style)
            
        finally:
            self._applying_style = False
    
    def resizeEvent(self, event: QResizeEvent):
        """Handle resize to update tab widths."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self.updateTabWidths)
    
    def _createCloseButton(self, index: int) -> QToolButton:
        """
        Create a custom close button with the desaturated icon.
        The button is properly sized and centered.
        """
        btn = QToolButton(self)
        btn.setFixedSize(CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE)
        btn.setIconSize(QSize(CLOSE_BUTTON_ICON_SIZE, CLOSE_BUTTON_ICON_SIZE))
        
        if SplitTabs.CloseIcon is not None:
            btn.setIcon(SplitTabs.CloseIcon)
        
        # Style the button to be flat with no background
        btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                padding: 0px;
                margin: {CLOSE_BUTTON_MARGIN_TOP}px {CLOSE_BUTTON_MARGIN_RIGHT}px {CLOSE_BUTTON_MARGIN_BOTTOM}px {CLOSE_BUTTON_MARGIN_LEFT}px;
            }}
            QToolButton:hover {{
                background: transparent;
            }}
            QToolButton:pressed {{
                background: transparent;
            }}
        """)
        
        # Connect click to close the tab
        btn.clicked.connect(lambda checked=False, idx=index: self._onCloseButtonClicked(idx))
        
        return btn
    
    def _onCloseButtonClicked(self, index: int):
        """Handle close button click - find the correct tab index and close it."""
        # The index might have changed if tabs were removed, so we need to find 
        # the actual index based on the button that was clicked
        sender = self.sender()
        if sender:
            for i in range(self.count()):
                if self.tabButton(i, QTabBar.ButtonPosition.RightSide) == sender:
                    self.tabCloseRequested.emit(i)
                    return
        # Fallback to original index
        self.tabCloseRequested.emit(index)
    
    def tabInserted(self, index: int):
        """Called when a tab is inserted - create custom close button and update widths."""
        super().tabInserted(index)
        
        # Create and set a custom close button with our desaturated icon
        close_btn = self._createCloseButton(index)
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)
        
        # Install event filter for hover effects
        close_btn.installEventFilter(self)
        
        QTimer.singleShot(0, self.updateTabWidths)
    
    def tabRemoved(self, index: int):
        """Called when a tab is removed - update widths."""
        super().tabRemoved(index)
        self._last_count = 0  # Force width recalculation
        QTimer.singleShot(0, self.updateTabWidths)

    def _sync(self, index: int):
        helper = self._helper
        uid = self.getUid(index)
        data = self._controller.getViewData(uid)
        mdi = helper.getMdi()
        if mdi:
            subwin = mdi.activeSubWindow()
            if data and data.win != subwin:
                self._controller.syncView(split=self.split(), view=data.view)

    def exec(
        self,
        callback: typing.Callable[[int, ViewData], Any],
        index: int | None = None,
        view: View | None = None,
        context: dict[str, Any] | None = None,
    ):
        helper = self._helper
        win = helper.getWin()
        qwin = helper.getQwin()
        tabs = helper.getTabBar()
        mdi = helper.getMdi()
        if not (win and qwin and tabs and mdi):
            return

        title = context.get("winTitle", None) if context else None
        if isinstance(title, str):
            title = qwin.windowTitle()

        if view:
            index = self.getTabByView(view)
            if index == -1:
                return

        with self._controller.syncedCall(True) as sync:
            if not sync:
                return

            kritaIndex = tabs.currentIndex()
            currIndex = self.currentIndex()

            index = currIndex if not isinstance(index, int) else index
            uid = self.getUid(index)
            data = self._controller.getViewData(uid)

            if uid is not None and data:
                # XXX helps a little with window title flashing
                winTitle = data.win.windowTitle()
                data.win.setWindowTitle(typing.cast(str, title))

                # XXX use setActiveSubWindow not setCurrentIndex
                # to make sure actions use the correct subwindow (in this cycle)
                mdi.setActiveSubWindow(data.win)
                callback(uid, data)

                self.setCurrentIndex(currIndex)
                tabs.setCurrentIndex(kritaIndex)
                data.win.setWindowTitle(winTitle)

    def onCurrentChange(self):
        self._sync(self.currentIndex())
        # Update tab widths when selection changes (for selected tab expansion)
        if EXPAND_SELECTED_TAB:
            self._last_current_index = -1  # Force update
            QTimer.singleShot(0, self.updateTabWidths)

    def split(self) -> "Split | None":
        toolbar = self._helper.isAlive(self.parent(), SplitToolbar)
        if toolbar:
            return toolbar.split()

    def topSplit(self) -> "Split | None":
        split = self._helper.isAlive(self.split(), Split)
        if split:
            return split.topSplit()

    def parentSplit(self) -> "Split | None":
        split = self.split()
        if split:
            return self._helper.isAlive(split.parent(), Split)

    def setActiveHighlight(self, active: bool = False):
        self.setProperty("class", "active" if active else "inactive")
        self._helper.refreshWidget(self)

    def prevTab(self):
        i = self.currentIndex()
        if i > 0:
            self.setCurrentIndex(i - 1)
        else:
            self.setCurrentIndex(self.count() - 1)

    def nextTab(self):
        i = self.currentIndex()
        if i < self.count() - 1:
            self.setCurrentIndex(i + 1)
        else:
            self.setCurrentIndex(0)

    def closeTabsOther(self, index: int | None = None):
        if not isinstance(index, int):
            index = self.currentIndex()

        split = self.split()
        assert split is not None

        wins: list[QMdiSubWindow] = []
        for i in range(self.count()):
            if i != index:
                sw = self._helper.isAlive(split.getTabWindow(i), QMdiSubWindow)
                if sw:
                    wins.append(sw)
        for w in wins:
            if self._helper.isAlive(w, QMdiSubWindow):
                w.close()

    def closeTabsLeft(self, index: int | None = None):
        if not isinstance(index, int):
            index = self.currentIndex()

        split = self.split()
        assert split is not None

        wins: list[QMdiSubWindow] = []
        for i in range(index):
            sw = self._helper.isAlive(split.getTabWindow(i), QMdiSubWindow)
            if sw:
                wins.append(sw)
        for w in wins:
            if self._helper.isAlive(w, QMdiSubWindow):
                w.close()

    def closeTabsRight(self, index: int | None = None):
        if not isinstance(index, int):
            index = self.currentIndex()

        split = self.split()
        assert split is not None

        wins: list[QMdiSubWindow] = []
        for i in range(index + 1, self.count()):
            sw = self._helper.isAlive(split.getTabWindow(i), QMdiSubWindow)
            if sw:
                wins.append(sw)
        for w in wins:
            if self._helper.isAlive(w, QMdiSubWindow):
                w.close()

    def purgeAllTabs(self, closeSplit: bool = True):
        for i in range(self.count()):
            self.purgeTab(i, closeSplit=False)
        if closeSplit:
            split = self.split()
            if split:
                split.checkShouldClose()

    def purgeTab(self, index: int, closeSplit: bool = True):
        helper = self._helper
        uid = self.getUid(index)
        data = self._controller.getViewData(uid)
        if data:
            toolbar = helper.isAlive(data.toolbar, SplitToolbar)
            if toolbar and toolbar == self.parent():
                win = helper.isAlive(data.win, QMdiSubWindow)
                if win:
                    win.close()
        if closeSplit:
            split = self.split()
            if split:
                split.checkShouldClose()

    def eventFilter(self, obj: QWidget, event: QEvent):
        if event.type() == QEvent.Type.Enter:
            obj.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            obj.setProperty("hover", True)
            obj.style().unpolish(obj)
            obj.style().polish(obj)
            obj.update()
            return False

        if event.type() == QEvent.Type.Leave:
            obj.setProperty("hover", False)
            obj.style().unpolish(obj)
            obj.style().polish(obj)
            return False

        return super().eventFilter(obj, event)

    def showDragPlaceHolder(self, pos: QPoint):
        helper = self._helper
        qwin = helper.getQwin()

        if not qwin:
            return

        if self._dragPlaceHolder is None:
            colors = self._controller.colors()
            assert colors is not None
            bg = QColor(colors.tabActive)
            fg = QColor(colors.tabText)
            self._dragPlaceHolder = TabDragRect(
                parent=qwin,
                color=bg,
                text=self.tabText(self._dragIndex),
                textColor=fg,
            )

        self._dragPlaceHolder.show()
        self._dragPlaceHolder.raise_()
        self._dragPlaceHolder.setGeometry(
            pos.x(),
            pos.y(),
            self.tabRect(self._dragIndex).width(),
            self.height(),
        )

    def hideDragPlaceHolder(self):
        if self._dragPlaceHolder is not None:
            self._dragPlaceHolder.deleteLater()
            self._dragPlaceHolder = None

    def showDropPlaceHolder(self, rect: QRect):
        helper = self._helper
        qwin = helper.getQwin()

        if not qwin:
            return

        if self._dropPlaceHolder is None:
            palette = self._controller.colors()
            assert palette is not None
            color = QColor(palette.tabActive)
            color.setAlpha(50)
            altColor = QColor(palette.tabActive).darker(150)
            altColor.setAlpha(100)
            self._dropPlaceHolder = TabDragRect(
                qwin, color=color, altColor=altColor
            )

        self._dropPlaceHolder.show()
        self._dropPlaceHolder.setGeometry(rect)

    def hideDropPlaceHolder(self):
        if self._dropPlaceHolder is not None:
            self._dropPlaceHolder.deleteLater()
            self._dropPlaceHolder = None

    def handleDropZone(self):
        helper = self._helper
        qwin = helper.getQwin()

        if not qwin:
            return

        if self._dragIndex != -1 and isinstance(self._dragPos, QPoint):
            globalPos = self._dragPos
            pos = qwin.mapFromGlobal(globalPos)
            self.showDragPlaceHolder(pos)
            currSplit = self.split()

            if not currSplit:
                return

            topSplit = helper.isAlive(currSplit.topSplit(), Split)
            if not topSplit:
                return

            targetSplit, el = topSplit.splitAt(pos)

            self._dropAction = None
            self._dropSplit = None
            self._dropEdge = None
            isOnlyTab = self.count() == 1

            if targetSplit is None or (
                isOnlyTab and topSplit.state() == Split.STATE_COLLAPSED
            ):
                self.hideDropPlaceHolder()
            else:
                targetRect = targetSplit.globalRect(withToolBar=False)
                rx, ry, rw, rh = targetRect.getRect()

                topRect = topSplit.globalRect(withToolBar=False)
                tx, ty, tw, th = topRect.getRect()

                x = pos.x()
                y = pos.y()
                edgeThreshold = 30

                if x > tx and x < tx + edgeThreshold and th != rh:
                    self._dropEdge = Qt.AnchorPoint.AnchorLeft
                    topRect.setWidth(edgeThreshold)
                elif x > tx + tw - edgeThreshold and x < tx + tw and th != rh:
                    self._dropEdge = Qt.AnchorPoint.AnchorRight
                    topRect.setX(tx + tw - edgeThreshold)
                elif y > ty and y < ty + edgeThreshold and tw != rw:
                    self._dropEdge = Qt.AnchorPoint.AnchorTop
                    topRect.setHeight(edgeThreshold)
                elif y > ty + th - edgeThreshold and y < ty + th and tw != rw:
                    self._dropEdge = Qt.AnchorPoint.AnchorBottom
                    topRect.setY(ty + th - edgeThreshold)
                else:
                    topRect = None

                if topRect is not None:
                    self._dropSplit = topSplit
                    self._dropAction = "makeSplitAtEdge"
                    self.showDropPlaceHolder(topRect)
                    return

                if isinstance(el, SplitHandle):
                    orient = el.orientation()
                    first = targetSplit.first()
                    second = targetSplit.second()
                    if first is not None and second is not None:
                        if (
                            first.state() == Split.STATE_SPLIT
                            and second.state() == Split.STATE_SPLIT
                        ):
                            first_handle = first.handle()
                            second_handle = second.handle()
                            if (
                                first_handle is not None
                                and second_handle is not None
                                and first_handle.orientation() != orient
                                and second_handle.orientation() != orient
                            ):
                                rect = second.globalRect()
                                if orient == Qt.Orientation.Vertical:
                                    rect.translate(-30, 0)
                                    rect.setWidth(50)
                                else:
                                    rect.translate(0, -30)
                                    rect.setHeight(50)
                                self._dropSplit = targetSplit
                                self._dropAction = "makeSplitBetween"
                                self.showDropPlaceHolder(rect)
                                return

                        targetSplit = (
                            first
                            if first.state() == Split.STATE_COLLAPSED
                            else second
                        )

                if isOnlyTab and targetSplit == currSplit:
                    self.hideDropPlaceHolder()
                    return

                edgeWidth = int(rw / 2.5)
                edgeHeight = int(rh / 2.5)
                x = pos.x()
                y = pos.y()

                hasAction = False
                actions = SimpleNamespace(
                    makeSplitLeft=False,
                    makeSplitRight=False,
                    makeSplitAbove=False,
                    makeSplitBelow=False,
                    transferTab=False,
                )

                level = targetSplit.droppableLevel()
                hasToolbar = isinstance(el, SplitToolbar)

                if hasToolbar:
                    actions.transferTab = True
                    hasAction = True
                elif level < 30:
                    if x < rx + edgeWidth and x >= rx:
                        actions.makeSplitLeft = max(0, (x - rx) / rw)
                        hasAction = True

                    if x > rx + rw - edgeWidth and x <= rx + rw:
                        actions.makeSplitRight = max(0, (rx + rw - x) / rw)
                        hasAction = True

                    if y < ry + edgeHeight and y >= ry:
                        actions.makeSplitAbove = max(0, (y - ry) / rh)
                        hasAction = True

                    if y > ry + rh - edgeHeight and y <= ry + rh:
                        actions.makeSplitBelow = max(0, (ry + rh - y) / rh)
                        hasAction = True

                if not hasAction:
                    self.hideDropPlaceHolder()
                    return

                if isOnlyTab:
                    parent = helper.isAlive(currSplit.parent(), Split)
                    targetParent = helper.isAlive(targetSplit.parent(), Split)
                    if parent and targetParent:
                        first = helper.isAlive(parent.first(), Split)
                        second = helper.isAlive(parent.second(), Split)
                        orient = parent.orientation()

                        if first and second:
                            firstMost = None
                            secondMost = None
                            nextParent = helper.isAlive(parent.parent(), Split)
                            if currSplit == first:
                                firstMost = second.firstMostSplit()
                                if (
                                    nextParent
                                    and parent == nextParent.second()
                                ):
                                    nextParentFirst = nextParent.first()
                                    assert nextParentFirst is not None
                                    secondMost = (
                                        nextParentFirst.secondMostSplit()
                                    )
                            elif currSplit == second:
                                secondMost = first.secondMostSplit()
                                if nextParent and parent == nextParent.first():
                                    nextParentSecond = nextParent.second()
                                    assert nextParentSecond is not None
                                    firstMost = (
                                        nextParentSecond.firstMostSplit()
                                    )

                            if targetParent.orientation() == orient:
                                currRect = currSplit.globalRect(
                                    withToolBar=False
                                )
                                cw = currRect.width()
                                ch = currRect.height()

                                if targetSplit == firstMost:
                                    if (
                                        orient == Qt.Orientation.Vertical
                                        and rh == ch
                                    ):
                                        actions.makeSplitLeft = False
                                    elif (
                                        orient == Qt.Orientation.Horizontal
                                        and rw == cw
                                    ):
                                        actions.makeSplitAbove = False
                                elif targetSplit == secondMost:
                                    if (
                                        orient == Qt.Orientation.Vertical
                                        and rh == ch
                                    ):
                                        actions.makeSplitRight = False
                                    elif (
                                        orient == Qt.Orientation.Horizontal
                                        and rw == cw
                                    ):
                                        actions.makeSplitBelow = False

                if (
                    actions.makeSplitLeft is not False
                    and (
                        actions.makeSplitAbove is False
                        or actions.makeSplitLeft <= actions.makeSplitAbove
                    )
                    and (
                        actions.makeSplitBelow is False
                        or actions.makeSplitLeft <= actions.makeSplitBelow
                    )
                ):
                    targetRect.setWidth(edgeWidth)
                    self._dropAction = "makeSplitLeft"
                elif (
                    actions.makeSplitRight is not False
                    and (
                        actions.makeSplitAbove is False
                        or actions.makeSplitRight <= actions.makeSplitAbove
                    )
                    and (
                        actions.makeSplitBelow is False
                        or actions.makeSplitRight <= actions.makeSplitBelow
                    )
                ):
                    targetRect.translate(rw - edgeWidth, 0)
                    targetRect.setWidth(edgeWidth)
                    self._dropAction = "makeSplitRight"
                elif actions.makeSplitAbove is not False:
                    targetRect.setHeight(edgeHeight)
                    self._dropAction = "makeSplitAbove"
                elif actions.makeSplitBelow is not False:
                    targetRect.translate(0, rh - edgeHeight)
                    targetRect.setHeight(edgeHeight)
                    self._dropAction = "makeSplitBelow"
                elif actions.transferTab:
                    targetRect = targetSplit.globalRect()
                    self._dropAction = "transferTab"

                if self._dropAction:
                    self._dropSplit = targetSplit
                    self.showDropPlaceHolder(targetRect)
                else:
                    self.hideDropPlaceHolder()
                    
    def abortTabDrag(self):
        self._dragIndex = -1
        self._dropEdge = None
        self._dropAction = None
        self._dropSplit = None
        # Reset left-click drag state
        self._leftDragStart = None
        self._leftDragIndex = -1
        self._leftDragMode = None
        if self._dragTimer:
            self._dragTimer.stop()
            self._dragTimer = None
        self.hideDragPlaceHolder()
        self.hideDropPlaceHolder()

    def mouseMoveEvent(self, event: QMouseEvent):
        # Track if we should block Qt's default tab reordering
        blockDefaultReorder = False
        
        # Handle middle-click drag (split mode)
        if self._dragIndex != -1:
            self._dragPos = toPoint(getEventGlobalPos(event))
            if self._dragTimer is None:
                self._dragTimer = QTimer()
                self._dragTimer.timeout.connect(self.handleDropZone)
                self._dragTimer.start(50)
            # Block default reordering when in split mode (middle-click or activated via left-click vertical)
            blockDefaultReorder = True
        
        # Handle left-click directional drag detection
        if self._leftDragStart is not None and self._leftDragMode is not None:
            currentPos = toPoint(getEventGlobalPos(event))
            dx = currentPos.x() - self._leftDragStart.x()
            dy = currentPos.y() - self._leftDragStart.y()
            distance = math.sqrt(dx * dx + dy * dy)
            
            if self._leftDragMode == "detecting":
                # Wait for movement past deadzone before determining direction
                if distance >= DRAG_DEADZONE:
                    # Calculate angle from vertical axis (0° = up, 90° = right, 180° = down, 270° = left)
                    # We use atan2 to get angle, then check if it's in vertical or horizontal cone
                    angle_rad = math.atan2(abs(dx), abs(dy))  # Angle from vertical axis
                    angle_deg = math.degrees(angle_rad)
                    
                    # If angle from vertical axis is less than threshold, it's a vertical drag
                    # Otherwise, it's a horizontal drag
                    if angle_deg < DRAG_ANGLE_THRESHOLD:
                        # Vertical cone (top or bottom) - will activate split mode
                        self._leftDragMode = "vertical"
                        # Block reordering immediately when vertical drag is detected
                        blockDefaultReorder = True
                    else:
                        # Horizontal cone (left or right) - normal tab reordering
                        self._leftDragMode = "horizontal"
                        # Reset tracking since Qt will handle horizontal reordering
                        self._leftDragStart = None
                        self._leftDragIndex = -1
                        self._leftDragMode = None
            
            elif self._leftDragMode == "vertical":
                # Block default reordering while in vertical drag mode
                blockDefaultReorder = True
                
                # Check if we've dragged far enough vertically to activate split mode
                vertical_distance = abs(dy)
                if vertical_distance >= DRAG_VERTICAL_THRESHOLD and self._dragIndex == -1:
                    # Activate split mode (same behavior as middle-click)
                    qwin = self._helper.getQwin()
                    if qwin:
                        self._controller.winClosed.connect(self.abortTabDrag)
                        self._dragStart = self._leftDragStart
                        self._dragIndex = self._leftDragIndex
                        globalPos = currentPos
                        pos = qwin.mapFromGlobal(globalPos)
                        self.showDragPlaceHolder(pos)
                        self.setCursor(Qt.CursorShape.SizeAllCursor)
                        # Clear left drag state since we've transitioned to split mode
                        self._leftDragStart = None
                        self._leftDragIndex = -1
                        self._leftDragMode = None
        
        # Only call super if we're not blocking default reordering
        # This prevents tabs from sliding left/right when in vertical drag or split mode
        if not blockDefaultReorder:
            super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        qwin = self._helper.getQwin()
        if not qwin:
            return
        btn = event.button()
        index = self.tabAt(toPoint(getEventPos(event)))
        self._dropEdge = None
        self._dropAction = None
        self._dropSplit = None
        if index >= 0:
            if btn == Qt.MouseButton.LeftButton:
                self._sync(index)
                # Start tracking for directional drag detection
                self._leftDragStart = toPoint(getEventGlobalPos(event))
                self._leftDragIndex = index
                self._leftDragMode = "detecting"
            elif btn == Qt.MouseButton.MiddleButton:
                self._controller.winClosed.connect(self.abortTabDrag)
                self._dragStart = getEventGlobalPos(event)
                self._dragIndex = index
                globalPos = toPoint(getEventGlobalPos(event))
                pos = qwin.mapFromGlobal(globalPos)
                self.showDragPlaceHolder(pos)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif btn == Qt.MouseButton.RightButton:
                parent = self._helper.isAlive(self.parent(), SplitToolbar)
                if parent:
                    parent.showMenu(event, tabIndex=index)
            self.tabPress.emit(event, index)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        helper = self._helper
        dropSplit = helper.isAlive(self._dropSplit, Split)
        try:
            self._controller.winClosed.disconnect(self.abortTabDrag)
        except:
            pass
        
        wasDragging = self._dragIndex != -1
        dragIndex = self._dragIndex
        
        if wasDragging and self._dropAction and dropSplit:
            if self._dropAction == "makeSplitAtEdge":
                assert self._dropEdge is not None
                dropSplit.makeSplitAtEdge(
                    tabIndex=self._dragIndex,
                    tabSplit=self.split(),
                    edge=self._dropEdge,
                )
            else:
                cb = getattr(dropSplit, self._dropAction, None)
                if cb is not None:
                    cb(tabIndex=self._dragIndex, tabSplit=self.split())

            currSplit = self.split()
            if currSplit:
                currSplit.realignCanvas()
        elif wasDragging and not self._dropAction:
            # No drop action means released on empty area - create windowed document tab
            self._createWindowedDocumentTab(dragIndex)

        if self._dragTimer:
            self._dragTimer.stop()
            self._dragTimer = None

        self._dragPos = None
        self._dragIndex = -1
        self._dropAction = None
        self._dropSplit = None
        self._dropEdge = None

        self.hideDragPlaceHolder()
        self.hideDropPlaceHolder()
        self.unsetCursor()
        
        # Reset left-click drag state
        self._leftDragStart = None
        self._leftDragIndex = -1
        self._leftDragMode = None

        i = self.tabAt(toPoint(getEventPos(event)))
        if i >= 0:
            self.tabRelease.emit(event, i)
        super().mouseReleaseEvent(event)
    
    def _createWindowedDocumentTab(self, tabIndex: int):
        """Create a windowed document tab from the dragged tab."""
        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        
        if not qwin or not mdi:
            return
        
        # Don't create windowed tab if there's only one document in all splits
        # (we need at least one document in the splits area)
        topSplit = self._controller.topSplit()
        if topSplit:
            all_subwindows = topSplit.getOpenSubWindows()
            if len(all_subwindows) <= 1 and len(self._controller.getWindowedTabs()) == 0:
                return
        
        # Get the view and subwindow for this tab
        uid = self.getUid(tabIndex)
        data = self._controller.getViewData(uid)
        
        if not data:
            return
        
        view = data.view
        subwindow = data.win
        title = self.tabText(tabIndex)
        currSplit = self.split()
        
        if not (view and subwindow and currSplit):
            return
        
        # Remove the tab from the current toolbar
        self.removeTab(tabIndex)
        
        # Create the windowed document tab
        windowedTab = WindowedDocumentTab(
            parent=qwin,
            controller=self._controller,
            view=view,
            subwindow=subwindow,
            uid=uid,
            title=title,
        )
        
        # Position it at the drag location (convert global to local coordinates)
        if self._dragPos:
            localPos = qwin.mapFromGlobal(self._dragPos)
            # Center the window roughly on the drag point
            x = max(0, localPos.x() - windowedTab.width() // 4)
            y = max(0, localPos.y() - WINDOWED_TAB_TITLE_HEIGHT // 2)
            windowedTab.move(x, y)
        
        # Track the windowed tab in the controller
        self._controller.addWindowedTab(windowedTab)
        
        # Connect signals
        windowedTab.closed.connect(lambda wt: self._controller.removeWindowedTab(wt))
        windowedTab.reintegrated.connect(lambda wt: self._controller.removeWindowedTab(wt))
        
        # Check if split should close
        currSplit.checkShouldClose()

    def wheelEvent(self, event: QWheelEvent):
        threshold = 100
        self._wheelAccumulator += event.angleDelta().y()

        if abs(self._wheelAccumulator) >= threshold:
            direction = -1 if self._wheelAccumulator > 0 else 1
            self._wheelAccumulator = 0

            new_index = self.currentIndex() + direction
            if 0 <= new_index < self.count():
                self.setCurrentIndex(new_index)

        event.accept()

    def getUid(self, index: int | None) -> int | None:
        if index is not None:
            data = self.tabData(index)
            if isinstance(data, dict):
                return typing.cast(dict[str, int], data).get(
                    "splitWindowUid", None
                )

    def setUid(self, index: int, uid: int):
        if index >= 0 and index < self.count():
            self.setTabData(index, {"splitWindowUid": uid})

    def getTabByView(self, view: View) -> int:
        data = self._helper.getViewData(view)
        uid = data.get("splitWindowUid", None) if data else None
        if uid is not None:
            for i in range(self.count()):
                if self.getUid(i) == uid:
                    return i
        return -1

    def getTabByWindow(self, win: QMdiSubWindow) -> int:
        uid = win.property("splitWindowUid")
        if uid is not None:
            for i in range(self.count()):
                if self.getUid(i) == uid:
                    return i
        return -1

    def getWindow(self, index: int | None = None) -> QMdiSubWindow | None:
        uid = self.getUid(index)
        if uid is not None:
            data = self._controller.getViewData(uid)
            if data is not None:
                return data.win

    def getView(self, index: int | None = None) -> View | None:
        uid = self.getUid(index)
        if uid is not None:
            data = self._controller.getViewData(uid)
            if data is not None:
                return data.view


class SplitToolbar(QWidget):
    def __init__(
        self, parent: QWidget, controller: "SplitPane", split: "Split"
    ):
        super().__init__(parent)
        self._split: "Split" = split
        self._controller: "SplitPane" = controller
        self._helper: Helper = controller.helper()
        self._tabs: SplitTabs = SplitTabs(self, controller=controller)
        self._menu: QMenu | None = None

    def globalRect(self) -> QRect:
        qwin = self._helper.getQwin()
        mdi = self._helper.getMdi()
        if qwin and mdi:
            rect = self.geometry()
            return QRect(
                mdi.mapTo(qwin, QPoint(rect.x(), rect.y())),
                rect.size(),
            )
        return QRect()

    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2c2c2c"))

    def setSplit(self, split: "Split"):
        self._split = split

    def split(self) -> "Split":
        return self._split

    def tabs(self) -> "SplitTabs":
        return self._tabs

    def _triggerAppAction(self, names: list[str]):
        app = self._helper.getApp()
        for name in names:
            action = app.action(name)
            if action:
                action.trigger()
                return

    def showMenu(self, event: QMouseEvent, tabIndex: int | None = None):
        topSplit = self._split.topSplit()
        assert topSplit is not None

        menuIndex = (
            tabIndex if isinstance(tabIndex, int) else self._tabs.currentIndex()
        )
        hasTabIndex = menuIndex >= 0
        hasTabs = self._tabs.count() > 0
        hasSplits = topSplit.state() == Split.STATE_SPLIT

        actions: list[MenuAction] = [
            MenuAction(
                text=i18n("Consolidate All"),
                callback=lambda: self._split.resetLayout(),
            ),
            MenuAction(
                text=i18n("Close"),
                callback=lambda: self._tabs.tabCloseRequested.emit(menuIndex),
                enabled=hasTabIndex,
                visible=hasTabIndex,
            ),
            MenuAction(
                text=i18n("Close All"),
                callback=self._controller.closeAllDocuments,
                enabled=hasTabs,
            ),
            MenuAction(
                text=i18n("Close Others"),
                callback=lambda: self._tabs.closeTabsOther(menuIndex),
                enabled=hasTabs,
                visible=hasTabIndex,
                separator=True,
            ),
            MenuAction(
                text=i18n("New Document"),
                callback=lambda: self._triggerAppAction(["file_new"]),
            ),
            MenuAction(
                text=i18n("Open Document"),
                callback=lambda: self._triggerAppAction(
                    ["file_open", "file_open_file"]
                ),
                separator=True,
            ),
        ]

        if self._menu is None:
            self._menu = QMenu(self)
            self._menu.setProperty("class", "splitPaneMenu")
        self._menu.clear()

        for a in actions:
            if a.visible:
                action = QAction(a.text, self)
                action.triggered.connect(a.callback)
                action.setEnabled(a.enabled)
                self._menu.addAction(action)
                if a.separator:
                    self._menu.addSeparator()

        self._menu.adjustSize()

        pos = self.mapToGlobal(self.rect().bottomRight())
        if tabIndex is not None:
            tabPos = toPoint(getEventGlobalPos(event))
            self._menu.exec(QPoint(tabPos.x(), pos.y()))
        else:
            pos = QPoint(pos.x() - self._menu.width() + 1, pos.y())
            self._menu.exec(pos)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._tabs.setFixedHeight(self.height())
        self._tabs.setGeometry(0, 0, self.width(), self.height())


class SplitHandle(QWidget):
    SIZE = 4

    def __init__(
        self,
        split: "Split",
        helper: Helper,
        orient: Qt.Orientation | None = None,
    ):
        super().__init__(helper.getMdi())
        self._helper: Helper = helper
        self._split: "Split" = split
        self._lastMousePos: QPoint = QPoint()
        self._dragging: bool = False
        self._dragDelta: int = 0
        self._dragTimer: QTimer | None = None
        self._orient: Qt.Orientation = (
            orient
            if isinstance(orient, Qt.Orientation)
            else Qt.Orientation.Vertical
        )
        self.setCursor(
            self._orient == Qt.Orientation.Vertical
            and Qt.CursorShape.SizeHorCursor
            or Qt.CursorShape.SizeVerCursor
        )

        self.reset()
        self.clamp()
        self.raise_()
        self.show()

    def setSplit(self, split: "Split"):
        self._split = split

    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        bg = self._helper.paletteColor("Window")
        p.fillRect(self.rect(), bg)

    def globalRect(self):
        qwin = self._helper.getQwin()
        mdi = self._helper.getMdi()
        if qwin and mdi:
            rect = self.geometry()
            return QRect(
                mdi.mapTo(qwin, QPoint(rect.x(), rect.y())),
                rect.size(),
            )
        return QRect()

    def orientation(self) -> Qt.Orientation:
        return self._orient

    def setOrientation(self, orient: Qt.Orientation, redraw: bool = True):
        if (
            orient in (Qt.Orientation.Horizontal, Qt.Orientation.Vertical)
            and orient != self._orient
        ):
            self._orient = orient
            self.setCursor(
                self._orient == Qt.Orientation.Vertical
                and Qt.CursorShape.SizeHorCursor
                or Qt.CursorShape.SizeVerCursor
            )
            if redraw:
                self.reset()
                self.clamp()
            return True

    def reset(self):
        x, y, w, h = self._split.getRect()
        if self._orient == Qt.Orientation.Vertical:
            self.setGeometry(
                x + int((w - SplitHandle.SIZE) / 2),
                y,
                SplitHandle.SIZE,
                h,
            )
        else:
            self.setGeometry(
                x,
                y + int((h - SplitHandle.SIZE) / 2),
                w,
                SplitHandle.SIZE,
            )

    def clamp(self):
        px, py, pw, ph = self._split.getRect()
        w = self.width()
        h = self.height()
        if self._orient == Qt.Orientation.Vertical:
            if pw < 100:
                self.reset()
                return
            if h != ph:
                self.resize(w, ph)
                h = ph
            x = max(px + 80, min(self.x(), px + pw - w - 80))
            y = max(py, min(self.y(), py + ph - h))
        else:
            if ph < 100:
                self.reset()
                return
            if w != pw:
                self.resize(pw, h)
                w = pw
            x = max(px, min(self.x(), px + pw - w))
            y = max(py + 80, min(self.y(), py + ph - h - 80))
        if x != self.x() or y != self.y():
            self.move(x, y)

    def event(self, event: QEvent):
        event_type = event.type()
        if event_type == QEvent.Type.ParentAboutToChange:
            pass
        elif event_type == QEvent.Type.ParentChange:
            pass
        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._dragDelta = 0
            self._lastMousePos = toPoint(getEventGlobalPos(event))
            event.accept()

    def offset(self) -> int:
        x, y, *_ = self.geometry().getRect()
        return x if self._orient == Qt.Orientation.Vertical else y

    def moveTo(self, offset: int = 0):
        if self._orient == Qt.Orientation.Vertical:
            self.move(offset, self.y())
        else:
            self.move(self.x(), offset)

        self.clamp()
        first = self._split.first()
        second = self._split.second()

        if first:
            first.resize()
        if second:
            second.resize()

    def handleMove(self):
        if self._dragDelta == 0:
            return
        if self._orient == Qt.Orientation.Vertical:
            self.moveTo(self.x() + self._dragDelta)
        else:
            self.moveTo(self.y() + self._dragDelta)
        self._dragDelta = 0

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            if self._dragTimer is None:
                self._dragTimer = QTimer()
                self._dragTimer.timeout.connect(self.handleMove)
                self._dragTimer.start(10)

            pos = toPoint(getEventGlobalPos(event))
            if self._orient == Qt.Orientation.Vertical:
                self._dragDelta += pos.x() - self._lastMousePos.x()
            else:
                self._dragDelta += pos.y() - self._lastMousePos.y()
            self._lastMousePos = pos
            event.accept()

            mdi = self._helper.getMdi()
            if mdi:
                subwin = mdi.activeSubWindow()
                for c in subwin.findChildren(QWidget):
                    cls = c.metaObject().className()
                    if "KisFloatingMessage" in cls or "FloatingMessage" in cls:
                        c.setVisible(False)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragTimer:
                self._dragTimer.stop()
                self._dragTimer = None
            first = self._split.first()
            second = self._split.second()
            if first:
                first.resize()
            if second:
                second.resize()
            self._dragging = False
            event.accept()


class Split(QObject):
    STATE_SPLIT = 0
    STATE_COLLAPSED = 1

    resized = pyqtSignal()

    def __init__(
        self,
        parent: "Split | QWidget",
        controller: "SplitPane",
        toolbar: SplitToolbar | None = None,
        state: int | None = None,
        orient: Qt.Orientation = Qt.Orientation.Vertical,
        first: "Split | None" = None,
        second: "Split | None" = None,
    ):
        super().__init__(parent)

        self._controller = controller
        self._helper = controller.helper()
        self._state: int = Split.STATE_COLLAPSED if state is None else state
        self._rect: QRect = QRect()
        self._first: "Split | None" = first
        self._second: "Split | None" = second
        self._handle: "SplitHandle | None" = None
        self._toolbar: SplitToolbar | None = None
        self._attachResizeCallback: typing.Callable[..., Any] | None = None
        self._resizing: bool = False
        self._closing: bool = False
        self._checkClosing: bool = False
        self._forceResizing: bool = False
        self._lastHandleRect: QRect = QRect()
        self._realignTick = self._helper.uid()

        mdi = self._helper.getMdi()
        assert mdi

        if self._state == Split.STATE_COLLAPSED:
            if isinstance(toolbar, SplitToolbar):
                self._toolbar = toolbar
                self._toolbar.setSplit(self)
                self._toolbar.setParent(mdi)
            else:
                self._toolbar = SplitToolbar(
                    parent=mdi,
                    split=self,
                    controller=self._controller,
                )

            self._toolbar.raise_()
            self._toolbar.show()
        else:
            self._handle = SplitHandle(
                self, helper=self._helper, orient=orient
            )
            assert self._first is not None
            assert self._second is not None
            self._first.setParent(self)
            self._second.setParent(self)

        self.attachEvents()
        self.destroyed.connect(self.clear)
        self._overlay = None

    def state(self) -> int:
        return self._state

    def showOverlay(self):
        if not self._overlay:
            qwin = self._helper.getQwin()
            rect = self.globalRect()
            if qwin:
                self._overlay = TabDragRect(qwin)
                self._overlay.show()
                self._overlay.setGeometry(rect)

    def hideOverlay(self):
        if self._overlay:
            self._overlay.deleteLater()
            self._overlay = None

    def topSplit(self) -> "Split | None":
        return self._controller.topSplit()

    def defaultSplit(self, checkToolbar: bool = True) -> "Split | None":
        return self._controller.defaultSplit(checkToolbar)

    def firstMostSplit(self):
        firstMost = self
        while firstMost.state() == Split.STATE_SPLIT:
            first = firstMost.first()
            if not first:
                break
            firstMost = first
        return firstMost

    def secondMostSplit(self):
        secondMost = self
        while secondMost.state() == Split.STATE_SPLIT:
            second = secondMost.second()
            if not second:
                break
            secondMost = second
        return secondMost

    def tabs(self):
        return getattr(self._toolbar, "_tabs", None)

    def currentIndex(self) -> int:
        tabs = self.tabs()
        if tabs is not None:
            return tabs.currentIndex()
        return -1

    def toolbar(self) -> "SplitToolbar | None":
        return self._toolbar

    def controller(self) -> "SplitPane":
        return self._controller

    def attachEvents(self):
        parent = self.parent()
        if isinstance(parent, QWidget):
            parent.installEventFilter(self)
        elif isinstance(parent, Split):
            helper = self._helper

            def cb():
                if helper.isAlive(self, Split):
                    self.resize()

            self._attachResizeCallback = lambda: cb()
            parent.resized.connect(self._attachResizeCallback)

    def detachEvents(self):
        parent = self.parent()
        if isinstance(parent, QWidget):
            parent.removeEventFilter(self)
        elif isinstance(parent, Split):
            try:
                if self._attachResizeCallback is not None:
                    parent.resized.disconnect(self._attachResizeCallback)
            except Exception:
                pass

    def eventFilter(self, obj: QObject, event: QEvent):
        if obj == self.parent():
            eventType = event.type()
            if eventType == QEvent.Type.Resize:
                self.resize()
        return super().eventFilter(obj, event)

    def setParent(self, parent: "Split"):
        self.detachEvents()
        ret = super().setParent(parent)
        self.attachEvents()
        return ret

    def first(self) -> "Split | None":
        return self._helper.isAlive(self._first, Split)

    def second(self) -> "Split | None":
        return self._helper.isAlive(self._second, Split)

    def handle(self) -> "SplitHandle | None":
        return self._helper.isAlive(self._handle, SplitHandle)

    def level(self):
        level = 0
        top = self
        while self._helper.isAlive(top, Split) and isinstance(
            top.parent(), Split
        ):
            top = top.parent()
            level += 1
        return level

    def droppableLevel(self) -> int:
        level = 0
        top = self
        while self._helper.isAlive(top, Split):
            parent = self._helper.isAlive(top.parent(), Split)
            if not parent:
                break
            if parent.orientation() != top.orientation():
                level += 1
            top = parent
        return level

    def rect(self):
        return QRect(self._rect)

    def getRect(self) -> tuple[int, int, int, int]:
        return self._rect.getRect()

    def equalize(
        self, nested: bool = True, orient: Qt.Orientation | None = None
    ):
        if self._state == Split.STATE_SPLIT and self._helper.isAlive(
            self._handle, SplitHandle
        ):
            assert self._handle is not None
            if orient is None or orient == self._handle.orientation():
                self._handle.reset()
                self.resize(force=True)
            if nested and self._first and self._second:
                self._first.equalize(nested=True)
                self._second.equalize(nested=True)

    def orientation(self) -> Qt.Orientation | None:
        if self._state == Split.STATE_SPLIT and self._helper.isAlive(
            self._handle, SplitHandle
        ):
            assert self._handle
            return self._handle.orientation()

    def setOrientation(self, orient: Qt.Orientation, redraw: bool = True):
        if self._state == Split.STATE_SPLIT and self._helper.isAlive(
            self._handle, SplitHandle
        ):
            assert self._handle
            if self._handle.setOrientation(orient, redraw=redraw) and redraw:
                self.equalize()
                return True

    def getTabWindow(self, index: int) -> QMdiSubWindow | None:
        tabs = self._helper.isAlive(self.tabs(), SplitTabs)
        if tabs:
            return tabs.getWindow(index)

    def getTabView(self, index: int) -> View | None:
        tabs = self._helper.isAlive(self.tabs(), SplitTabs)
        if tabs:
            return tabs.getView(index)

    def getActiveTabWindow(self) -> QMdiSubWindow | None:
        return self.getTabWindow(self.currentIndex())

    def getActiveTabView(self) -> View | None:
        return self.getTabView(self.currentIndex())

    def getOpenSubWindows(
        self, modified: bool = False
    ) -> list[tuple[QMdiSubWindow, View]]:
        windows: list[tuple[QMdiSubWindow, View]] = []
        if self._state == Split.STATE_COLLAPSED:
            tabs = self.tabs()
            if tabs:
                for i in range(tabs.count()):
                    view = self.getTabView(i)
                    win = self.getTabWindow(i)
                    doc = view.document() if view else None
                    if (
                        view
                        and win
                        and (
                            not modified
                            or (modified and doc and doc.modified())
                        )
                    ):
                        windows.append((win, view))
        elif self._state == Split.STATE_SPLIT:
            if self._first:
                windows.extend(self._first.getOpenSubWindows())
            if self._second:
                windows.extend(self._second.getOpenSubWindows())
        return windows

    def checkShouldClose(self):
        if self._checkClosing:
            return
        self._checkClosing = True
        helper = self._helper

        def cb():
            closeSplit = helper.isAlive(self, Split)
            if closeSplit and closeSplit.state() == Split.STATE_COLLAPSED:
                tabs = helper.isAlive(closeSplit.tabs(), SplitTabs)
                if not tabs or tabs.count() == 0:
                    if closeSplit.topSplit() != closeSplit:
                        closeSplit.close()
                    self._controller.setActiveToolbar()
            self._checkClosing = False

        QTimer.singleShot(100, cb)

    def close(self):
        helper = self._helper
        if self._closing or not helper.isAlive(self, Split) or self._state != Split.STATE_COLLAPSED:
            return

        self._closing = True

        opened = self.getOpenSubWindows()
        for o in opened:
            win = o[0]
            win.close()

        opened = self.getOpenSubWindows()
        if len(opened) > 0:
            self._closing = False
            return

        parent = self.parent()
        if isinstance(parent, Split):
            first = parent.first()
            second = parent.second()
            if not (first and second):
                return
            if (
                first
                and second
                and first._state == Split.STATE_COLLAPSED
                and second._state == Split.STATE_COLLAPSED
            ):
                keep = second if first == self else first

                assert keep._toolbar is not None
                assert parent._handle is not None

                parent._toolbar = keep._toolbar
                parent._toolbar.setSplit(parent)
                keep._toolbar = None

                first.clear(True)
                second.clear(True)

                parent._state = Split.STATE_COLLAPSED
                handle = parent._handle
                parent._handle = None
                handle.deleteLater()

                topSplit = parent.topSplit()
                if topSplit:
                    topSplit.resize(force=True)
            else:
                keep = second if first == self else first
                keep_orient = keep.orientation()

                assert parent._handle is not None
                assert keep._first is not None
                assert keep._second is not None
                assert keep_orient is not None

                parent._handle.setOrientation(keep_orient, redraw=False)
                parent._first = keep._first
                parent._second = keep._second

                parent._first.setParent(parent)
                parent._second.setParent(parent)
                keep._first = None
                keep._second = None

                first.clear(True)
                second.clear(True)

                topSplit = parent.topSplit()
                if topSplit:
                    topSplit.resize(force=True)
                parent.equalize()

        self._closing = False

    def clear(self, removeSelf: bool = False):
        helper = self._helper
        self._handle = helper.isAlive(self._handle, SplitHandle)
        self._toolbar = helper.isAlive(self._toolbar, SplitToolbar)
        self._first = helper.isAlive(self._first, Split)
        self._second = helper.isAlive(self._second, Split)
        if self._handle:
            self._handle.deleteLater()
            self._handle = None
        if self._toolbar:
            self._toolbar.tabs().purgeAllTabs(closeSplit=False)
            self._toolbar.deleteLater()
            self._toolbar = None
        if self._first:
            self._first.clear(True)
            self._first = None
        if self._second:
            self._second.clear(True)
            self._second = None
        if removeSelf and helper.isAlive(self, Split):
            parent = self.parent()
            if parent and isinstance(parent, Split):
                if self == parent._first:
                    parent._first = None
                elif self == parent._second:
                    parent._second = None
            self.detachEvents()
            self.deleteLater()

    def isForceResizing(self):
        if self._forceResizing:
            return True
        top = self._helper.isAlive(self, Split)
        while top:
            top = self._helper.isAlive(top.parent(), Split)
            if top and top._forceResizing:
                return True
        return False

    def resize(self, force: bool = True):
        if self._resizing:
            return
        self._forceResizing = force
        self._resizing = True
        parent = self.parent()
        old_rect = self._rect
        if isinstance(parent, QWidget):
            # this is the origin rect x=0,y=0
            self._rect = parent.rect()
        elif isinstance(parent, Split):
            first = parent._first
            second = parent._second
            handle = parent._handle
            if not handle:
                self._resizing = False
                return
            px, py, pw, ph = parent.getRect()
            hx, hy, hw, hh = handle.geometry().getRect()
            if first == self:
                if handle.orientation() == Qt.Orientation.Vertical:
                    self._rect = QRect(px, py, max(0, hx - px), ph)
                else:
                    self._rect = QRect(px, py, pw, max(0, hy - py))
            elif second == self:
                if handle.orientation() == Qt.Orientation.Vertical:
                    self._rect = QRect(
                        hx + hw, py, max(0, pw - ((hx - px) + hw)), ph
                    )
                else:
                    self._rect = QRect(
                        px, hy + hh, pw, max(0, ph - ((hy - py) + hh))
                    )

        if self._state == Split.STATE_SPLIT:
            if not self._handle:
                self._resizing = False
                return
            handleRect = self._handle.globalRect()
            if (
                old_rect != self._rect
                or handleRect != self._lastHandleRect
                or self.isForceResizing()
            ):
                self._handle.clamp()
                self._lastHandleRect = handleRect
                if self._first:
                    self._first.resize()
                if self._second:
                    self._second.resize()
        elif self._state == Split.STATE_COLLAPSED and (
            old_rect != self._rect or self.isForceResizing()
        ):
            if self._toolbar is not None:
                # Check if tabs are hidden for canvas-only mode
                mdi = self._helper.getMdi()
                tabsHidden = mdi.property("tabsHiddenForCanvasOnly") if mdi else False
                if tabsHidden:
                    # In canvas-only mode, hide toolbar and let subwindow fill entire area
                    self._toolbar.setFixedHeight(0)
                    self._toolbar.setVisible(False)
                else:
                    self._toolbar.setFixedHeight(TAB_BAR_HEIGHT)
                    self._toolbar.setVisible(True)
                    self._toolbar.setGeometry(
                        self._rect.x(),
                        self._rect.y(),
                        self._rect.width(),
                        TAB_BAR_HEIGHT,
                    )
                self.resizeSubWindow()
            self.resized.emit()
        self._forceResizing = False
        self._resizing = False

    def resizeSubWindow(self):
        if self._state != Split.STATE_COLLAPSED:
            return

        helper = self._helper
        win = helper.isAlive(self.getActiveTabWindow(), QMdiSubWindow)
        toolbar = helper.isAlive(self._toolbar, SplitToolbar)
        if win and toolbar:
            helper.disableToast()
            rect = self._rect
            # Check if tabs are hidden for canvas-only mode
            mdi = helper.getMdi()
            tabsHidden = mdi.property("tabsHiddenForCanvasOnly") if mdi else False
            toolbarHeight = 0 if tabsHidden else toolbar.height()
            win.setFixedWidth(rect.width())
            win.setFixedHeight(rect.height() - toolbarHeight)
            win.setGeometry(
                rect.x(),
                rect.y() + toolbarHeight,
                rect.width(),
                rect.height() - toolbarHeight,
            )
            win.raise_()
            win.show()
            helper.enableToast()

    def globalRect(self, withToolBar: bool = True):
        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        if qwin and mdi:
            rect = QRect(
                mdi.mapTo(qwin, QPoint(self._rect.x(), self._rect.y())),
                self._rect.size(),
            )
            if not withToolBar:
                rect.setY(rect.y() + TAB_BAR_HEIGHT)
            return rect
        return QRect()

    def splitAt(
        self, pos: QPoint
    ) -> tuple["Split | None", "Split | SplitToolbar | SplitHandle | None"]:
        if self.globalRect().contains(pos):
            if self._state == Split.STATE_SPLIT:
                assert self._handle is not None
                assert self._first is not None
                assert self._second is not None
                if self._handle.globalRect().contains(pos):
                    return (self, self._handle)
                split, element = self._first.splitAt(pos)
                if split is None:
                    split, element = self._second.splitAt(pos)
                return (split, element)
            elif self._state == Split.STATE_COLLAPSED:
                assert self._toolbar is not None
                if self._toolbar.globalRect().contains(pos):
                    return (self, self._toolbar)
                return (self, self)
        return (None, None)

    def transferTab(
        self,
        tabSplit: "Split",
        tabIndex: int | None = None,
        dupe: bool = False,
    ):
        helper = self._helper
        tabs = tabSplit.tabs()

        if not tabs:
            return

        if tabIndex is None:
            tabIndex = tabSplit.currentIndex()

        uid = tabs.getUid(tabIndex)
        data = self._controller.getViewData(uid)

        if not data:
            return

        if dupe:
            self.controller().syncView(
                view=data.view, split=self, addView=True
            )
        else:
            kritaTab = self.controller().getIndexByView(data.view)
            if kritaTab != -1:
                self.controller().syncView(index=kritaTab, split=self)

        tabSplit.checkShouldClose()

    def makeSplit(
        self,
        orient: Qt.Orientation,
        dupe: bool = False,
        swap: bool = False,
        empty: bool = False,
        tabIndex: int | None = None,
        tabSplit: "Split | None" = None,
    ):
        if self._state == Split.STATE_COLLAPSED:
            tabs = self.tabs()

            if not tabs:
                return

            isSelf = tabSplit == self
            toolbar = self._toolbar
            self._toolbar = None
            self._handle = SplitHandle(
                self, helper=self._helper, orient=orient
            )
            ret = (None, None)
            if swap:
                self._second = Split(
                    self, toolbar=toolbar, controller=self._controller
                )
                self._first = Split(self, controller=self._controller)
                ret = (self._first, self._second)
            else:
                self._first = Split(
                    self, toolbar=toolbar, controller=self._controller
                )
                self._second = Split(self, controller=self._controller)
                ret = (self._second, self._first)

            self._state = Split.STATE_SPLIT

            if not empty:
                # edge case tabSplit was passed in but it got split and now is first or second
                if isSelf:
                    tabSplit = self._second if swap else self._first
                elif tabSplit is None:
                    tabSplit = ret[1]

                if tabIndex is None:
                    tabIndex = tabSplit.currentIndex()

                ret[0].transferTab(
                    tabSplit=tabSplit, tabIndex=tabIndex, dupe=dupe
                )

            topSplit = self.topSplit()
            if topSplit:
                topSplit.resize(force=True)
            self._first.realignCanvas(nested=True)
            self._second.realignCanvas(nested=True)
            return ret

    def makeSplitBelow(
        self,
        dupe: bool = False,
        tabIndex: int | None = None,
        tabSplit: "Split | None" = None,
    ):
        return self.makeSplit(
            Qt.Orientation.Horizontal,
            dupe=dupe,
            tabIndex=tabIndex,
            tabSplit=tabSplit,
        )

    def makeSplitAbove(
        self,
        dupe: bool = False,
        tabIndex: int | None = None,
        tabSplit: "Split | None" = None,
    ):
        return self.makeSplit(
            Qt.Orientation.Horizontal,
            swap=True,
            dupe=dupe,
            tabIndex=tabIndex,
            tabSplit=tabSplit,
        )

    def makeSplitRight(
        self,
        dupe: bool = False,
        tabIndex: int | None = None,
        tabSplit: "Split | None" = None,
    ):
        return self.makeSplit(
            Qt.Orientation.Vertical,
            dupe=dupe,
            tabIndex=tabIndex,
            tabSplit=tabSplit,
        )

    def makeSplitLeft(
        self,
        dupe: bool = False,
        tabIndex: int | None = None,
        tabSplit: "Split | None" = None,
    ):
        return self.makeSplit(
            Qt.Orientation.Vertical,
            swap=True,
            dupe=dupe,
            tabIndex=tabIndex,
            tabSplit=tabSplit,
        )

    def makeSplitBetween(
        self,
        dupe: bool = False,
        tabSplit: "Split | None" = None,
        tabIndex: int | None = None,
    ):
        if self._state == Split.STATE_SPLIT:
            assert self._handle is not None
            assert self._first is not None
            assert self._second is not None

            second = self._second
            orient = self._handle.orientation()

            split = Split(self, controller=self._controller)
            toolbar = split._toolbar
            split._toolbar = None
            split._handle = SplitHandle(
                split, helper=self._helper, orient=orient
            )
            split._first = Split(
                split, toolbar=toolbar, controller=self._controller
            )
            split._second = second
            split._second.setParent(split)
            split._state = Split.STATE_SPLIT

            self._second = split

            if tabSplit is not None and tabIndex is not None:
                split._first.transferTab(
                    tabSplit=tabSplit, tabIndex=tabIndex, dupe=dupe
                )

            topSplit = self.topSplit()
            if topSplit:
                topSplit.resize(force=True)
            return split._first

    def makeSplitAtEdge(
        self,
        edge: Qt.AnchorPoint,
        dupe: bool = False,
        tabSplit: "Split | None" = None,
        tabIndex: int | None = None,
    ):
        topSplit = self.topSplit()
        if topSplit and topSplit.state() == Split.STATE_SPLIT:
            sizes = topSplit.saveSizes()

            first = topSplit.first()
            second = topSplit.second()
            orient = topSplit.orientation()
            assert orient is not None

            targetSplit = Split(topSplit, controller=self._controller)
            otherSplit = Split(
                topSplit,
                controller=self._controller,
                state=Split.STATE_SPLIT,
                orient=orient,
                first=first,
                second=second,
            )

            if edge in (Qt.AnchorPoint.AnchorLeft, Qt.AnchorPoint.AnchorTop):
                topSplit._first = targetSplit
                topSplit._second = otherSplit
            else:
                topSplit._second = targetSplit
                topSplit._first = otherSplit

            topSplit.setOrientation(
                Qt.Orientation.Vertical
                if edge
                in (Qt.AnchorPoint.AnchorLeft, Qt.AnchorPoint.AnchorRight)
                else Qt.Orientation.Horizontal
            )
            rect = topSplit.rect()
            h = int(rect.height() * 0.25)
            w = int(rect.width() * 0.25)
            handle = topSplit.handle()
            first = topSplit.first()
            second = topSplit.second()
            assert handle is not None
            assert first is not None
            assert second is not None

            if edge == Qt.AnchorPoint.AnchorLeft:
                handle.moveTo(w)
                second.equalize(orient=Qt.Orientation.Vertical)
            elif edge == Qt.AnchorPoint.AnchorTop:
                handle.moveTo(h)
                second.equalize(orient=Qt.Orientation.Horizontal)
            elif edge == Qt.AnchorPoint.AnchorRight:
                handle.moveTo(rect.width() - w)
                first.equalize(orient=Qt.Orientation.Vertical)
            elif edge == Qt.AnchorPoint.AnchorBottom:
                handle.moveTo(rect.height() - h)
                first.equalize(orient=Qt.Orientation.Horizontal)

            if tabSplit is not None and tabIndex is not None:
                targetSplit.transferTab(
                    tabSplit=tabSplit, tabIndex=tabIndex, dupe=dupe
                )

            second.restoreSizes(sizes, orient=second.orientation())
            second.realignCanvas(nested=True)

    def resetLayout(self):
        tabs = self._helper.getTabBar()
        split = self.defaultSplit(False)
        if tabs and split:
            for i in range(tabs.count()):
                self._controller.syncView(index=i, split=split)
            topSplit = self.topSplit()
            if topSplit:
                topSplit.closeEmpties()

    def realignCanvas(
        self,
        index: int | None = None,
        view: View | None = None,
        nested: bool = False,
        tick: bool = True,
    ):
        with self._controller.syncedCall(True) as sync:
            if not sync:
                return

            qwin = self._helper.getQwin()
            context = {"winTitle": qwin.windowTitle()} if qwin else None
            self._doRealign(
                index=index,
                view=view,
                nested=nested,
                context=context,
                tick=tick,
            )

    def _doRealign(
        self,
        index: int | None = None,
        view: View | None = None,
        nested: bool = False,
        context: dict[str, Any] | None = None,
        tick: bool = True,
    ):

        if self._state == Split.STATE_COLLAPSED:
            helper = self._helper
            tabs = self.tabs()
            if not tabs:
                return

            if tick:
                self._realignTick = helper.uid()

            def cb(_, data: ViewData):
                app = helper.getApp()
                qwin = helper.getQwin()
                if app and qwin:
                    w, h = data.win.width(), data.win.height()
                    rawZoom = helper.getZoomLevel(True)
                    data.realignTick = self._realignTick
                    data.win.setFixedHeight(h + 1)
                    data.win.setFixedWidth(w + 1)
                    fitToView = rawZoom != helper.getZoomLevel(True)
                    data.win.setFixedHeight(h)
                    data.win.setFixedWidth(w)

                    if not fitToView:
                        zoom = helper.getZoomLevel()
                        app.action("zoom_to_fit").trigger()
                        helper.setZoomLevel(zoom)

            tabs.exec(cb, index=index, view=view, context=context)
        elif self._state == Split.STATE_SPLIT and nested:
            if self._first:
                self._first._doRealign(nested=True, context=context, tick=tick)
            if self._second:
                self._second._doRealign(
                    nested=True, context=context, tick=tick
                )

    def saveSizes(self) -> list[tuple["Split", int]]:
        if self._state == Split.STATE_SPLIT:
            assert self._first is not None
            assert self._second is not None
            assert self._handle is not None
            return (
                [(self._first, self._handle.offset())]
                + self._first.saveSizes()
                + self._second.saveSizes()
            )
        return []

    def restoreSizes(
        self,
        sizes: list[tuple["Split", int]],
        orient: Qt.Orientation | None = None,
    ):
        for sz in sizes:
            split, offset = sz
            parent = self._helper.isAlive(split.parent(), Split)
            if parent:
                handle = parent.handle()
                if handle:
                    if orient is None or orient == handle.orientation():
                        handle.moveTo(offset)

    def closeEmpties(self):
        helper = self._helper
        if self._state == Split.STATE_COLLAPSED:
            tabs = self.tabs()
            if not tabs or tabs.count() == 0:
                parentSplit = helper.isAlive(self.parent(), Split)
                self.close()
                if parentSplit:
                    parentSplit.closeEmpties()
                self._controller.setActiveToolbar()
        elif self._state == Split.STATE_SPLIT:
            first = helper.isAlive(self._first, Split)
            if first:
                first.closeEmpties()
            second = helper.isAlive(self._second, Split)
            if second:
                second.closeEmpties()


class SplitPane(Component):
    winClosed = pyqtSignal()
    
    def __init__(self, window: Window):
        super().__init__(window)
        self._quit: bool = False
        self._syncing: bool = False
        self._viewData: dict[int, ViewData] = {}
        self._split: Split | None = None
        self._activeToolbar: SplitToolbar | None = None
        self._colors: SimpleNamespace | None = None
        self._windowedTabs: list[WindowedDocumentTab] = []  # Track windowed document tabs
        self._dockFocusConnected = False
        self._dockTabEventFilter: DockTabEventFilter | None = None
        self._dockTabifiedConnected = False

        _ = self._helper.newAction(
            window,
            "krita_ui_tweaks_next_tab",
            i18n("Goto next tab"),
            self.nextTab,
        )

        _ = self._helper.newAction(
            window,
            "krita_ui_tweaks_prev_tab",
            i18n("Goto previous tab"),
            self.prevTab,
        )

        qapp = typing.cast(QApplication, QApplication.instance())
        qapp.aboutToQuit.connect(lambda: self.onQuit())

        self.attachStyles()
        self._installDockFocusWatcher()
        self._installDockTabifiedWatcher()

    def onQuit(self):
        self._quit = True

    def shortPoll(self):
        if self._quit:
            return
        helper = self._helper
        doc = helper.getDoc()
        tabs = helper.getTabBar()
        if doc and tabs:
            self.updateDocumentTabs(doc)
            self.updateWindowedTabTitles(doc)

    def longPoll(self):
        if self._quit:
            return
        helper = self._helper
        app = helper.getApp()
        tabs = helper.getTabBar()
        if app and tabs:
            for doc in app.documents():
                self.updateDocumentTabs(doc)

    def updateDocumentTabs(self, doc: Document):
        helper = self._helper
        tabs = helper.getTabBar()
        if not tabs:
            return

        data = helper.getDocData(doc)
        if not data:
            return
        currTabText = data.doc.get("tabText", None)
        view = data.views[0][0]
        index = self.getIndexByView(view)
        # Use full tab text - elide mode handles visual truncation
        tabText = tabs.tabText(index)

        if currTabText != tabText:
            data.doc["tabText"] = tabText
            for v in data.views:
                view = v[0]
                index = self.getIndexByView(view)
                uid = self.getUid(index)
                if uid is not None:
                    viewData = self.getViewData(uid)
                    if viewData is not None:
                        toolbar = helper.isAlive(
                            viewData.toolbar, SplitToolbar
                        )
                        if toolbar:
                            toolbarTabs = toolbar.tabs()
                            splitTabIndex = toolbarTabs.getTabByView(view)
                            toolbarTabs.setTabText(splitTabIndex, tabText)

    def updateWindowedTabTitles(self, doc: Document):
        """Update titles of windowed document tabs when documents change."""
        helper = self._helper
        tabs = helper.getTabBar()
        if not tabs:
            return
        
        for windowedTab in self._windowedTabs:
            view = windowedTab.view()
            if view and view.document() == doc:
                # Get the updated tab text from the main tab bar
                index = self.getIndexByView(view)
                if index >= 0:
                    tabText = tabs.tabText(index)
                    windowedTab.setTitle(tabText)

    def closeAllDocuments(self):
        helper = self._helper
        mdi = helper.getMdi()
        if mdi:
            for win in list(mdi.subWindowList()):
                live = helper.isAlive(win, QMdiSubWindow)
                if live:
                    live.close()

        for wt in self._windowedTabs[:]:
            wt.closeDocument()

    def handleSplitter(self):
        helper = self._helper
        mdi = helper.getMdi()
        central = helper.getCentral()

        isEnabled = getOpt("toggle", "split_panes")

        if (
            not self.isHomeScreenShowing()
            and central
            and mdi
            and mdi.viewMode() == QMdiArea.ViewMode.TabbedView
            and isEnabled
        ):
            if not self._split:
                self._viewData = {}

                self._split = Split(parent=central, controller=self)
                for i, _ in enumerate(mdi.subWindowList()):
                    self.syncView(index=i)

                self._componentTimers.shortPoll.connect(self.shortPoll)
                self._componentTimers.longPoll.connect(self.longPoll)

        elif self._split:
            self._componentTimers.shortPoll.disconnect(self.shortPoll)
            self._componentTimers.longPoll.disconnect(self.longPoll)

            qwin = helper.getQwin()
            if qwin and mdi:
                updates = qwin.updatesEnabled()
                qwin.setUpdatesEnabled(False)
                viewMode = mdi.viewMode()

                # Close all windowed tabs and restore their subwindows
                for wt in self._windowedTabs[:]:  # Copy list to avoid modification during iteration
                    if wt._subwindow:
                        wt._subwindow.setParent(mdi)
                        wt._subwindow.setWindowFlags(Qt.WindowType.SubWindow)
                        wt._subwindow.showMaximized()
                    wt.deleteLater()
                self._windowedTabs.clear()

                for w in mdi.subWindowList():
                    w.showMaximized()
                    if viewMode == QMdiArea.ViewMode.SubWindowView:
                        w.showNormal()
                    w.setMinimumHeight(0)
                    w.setMaximumHeight(QWIDGETSIZE_MAX)
                    w.setMinimumWidth(0)
                    w.setMaximumWidth(QWIDGETSIZE_MAX)
                qwin.setUpdatesEnabled(updates)

                def cb():
                    mdi = helper.getMdi()
                    if mdi:
                        if mdi.viewMode() == QMdiArea.ViewMode.TabbedView:
                            s = mdi.size()
                            mdi.resize(s.width() + 1, s.height())
                            mdi.resize(s)
                        else:
                            mdi.tileSubWindows()

                QTimer.singleShot(0, cb)

            self._viewData = {}
            self._split.clear(True)
            self._split = None

    def colors(self):
        return self._colors

    def detachStyles(self):
        app = typing.cast(QApplication, QApplication.instance())
        css = app.styleSheet()
        match_first = r"/\*\s*KRITA_UI_TWEAKS_STYLESHEET_BEGIN\s*\*/"
        match_last = r"/\*\s*KRITA_UI_TWEAKS_STYLESHEET_END\s*\*/"
        css = re.sub(
            rf"{match_first}.*?{match_last}", "", css, flags=re.DOTALL
        )
        app.setStyleSheet(css)

    def attachStyles(self):
        if not getOpt("toggle", "split_panes"):
            return

        helper = self._helper
        useDarkIcons = helper.useDarkIcons()
        winColor = helper.paletteColor("Window")
        textColor = helper.paletteColor("Text")
        hlColor = helper.paletteColor("Highlight")

        colors = (
            SimpleNamespace(
                bar=winColor.darker(130).name(),
                tab=winColor.darker(120).name(),
                tabSeparator=winColor.darker(170).name(),
                tabSelected=winColor.lighter(120).name(),
                tabActive=hlColor.name(),
                tabText=textColor.name(),
                tabClose="lightcoral",
                menuSeparator=textColor.name(),
                splitHandle=winColor.name(),
            )
            if useDarkIcons
            else SimpleNamespace(
                bar=winColor.darker(150).name(),
                tab=winColor.darker(120).name(),
                tabSeparator=winColor.lighter(140).name(),
                tabSelected=winColor.lighter(130).name(),
                tabActive=hlColor.name(),
                tabText=textColor.name(),
                tabClose="darkred",
                menuSeparator=textColor.darker(150).name(),
                splitHandle=winColor.name(),
            )
        )

        style = f"""
                /* KRITA_UI_TWEAKS_STYLESHEET_BEGIN */
                QMainWindow::separator {{
                    background: transparent;
                }}
                QMdiArea[toasts="hidden"] KisFloatingMessage {{
                    opacity: 0;
                    min-width: 0;
                    max-width: 0;
                    min-height: 0;
                    max-height: 0;
                }}
                QMenu[class="splitPaneMenu"] {{
                    padding-top: 10px;
                    padding-bottom: 10px;
                }}
                QMenu[class="splitPaneMenu"]::separator {{
                    height: 1px;
                    margin: 10px 0;
                    background: {colors.menuSeparator};
                }}
                QMdiArea QTabBar, QMdiArea QTabBar::tab {{
                    min-height: 0;   
                    max-height: 0;
                }}
                QMdiArea SplitTabs {{
                    qproperty-drawBase: 0;
                    background: {colors.bar};      
                    min-height: {TAB_BAR_HEIGHT}px;   
                    max-height: {TAB_BAR_HEIGHT}px;
                    border: 0;
                    margin: 0;
                    padding: 0;
                    padding-right: 0px;
                }}
                QMdiArea SplitTabs QToolButton {{
                    border: none;
                    background: {colors.bar};      
                }}
                QMdiArea SplitTabs::tab {{
                    min-width: {TAB_MIN_WIDTH}px; 
                    max-width: {TAB_MAX_WIDTH}px; 
                    height: 34px;     
                    min-height: {TAB_BAR_HEIGHT}px;   
                    max-height: {TAB_BAR_HEIGHT}px;
                    background: {colors.tab};
                    border-radius: 0;
                    border: 1px solid {colors.tab};
                    border-top: 2px solid {TAB_SEPARATOR_COLOR};
                    border-right: 1px solid {colors.tabSeparator};
                    padding: 0px 8px;
                }}
                QMdiArea SplitTabs::tab:last {{
                    border-right: 1px solid {colors.tabSeparator};
                }}
                QMdiArea SplitTabs::tab:hover {{
                    border-top: 2px solid {TAB_SEPARATOR_COLOR};
                }}
                QMdiArea SplitTabs::tab:selected {{
                    background: {colors.tabSelected}; 
                    border: 1px solid {colors.tabSelected};
                    border-top: 2px solid {TAB_SEPARATOR_COLOR};
                    border-right: 1px solid {colors.tabSelected};
                }}
                QHeaderView::section {{
                    padding: 7px;
                }}
                QMdiArea SplitTabs::tear {{
                    width: 0px; 
                    border: none;
                }}
                QMdiArea SplitTabs[class="active"]::tab:selected {{
                    background: {colors.tabActive}; 
                    border: 1px solid {colors.tabActive};
                    border-top: 2px solid {TAB_SEPARATOR_COLOR};
                    border-right: 1px solid {colors.tabActive};
                }}
                /* KRITA_UI_TWEAKS_STYLESHEET_END */
            """

        self._colors = colors
        app = typing.cast(QApplication, QApplication.instance())

        css = app.styleSheet()

        match_first = r"/\*\s*KRITA_UI_TWEAKS_STYLESHEET_BEGIN\s*\*/"
        match_last = r"/\*\s*KRITA_UI_TWEAKS_STYLESHEET_END\s*\*/"
        css = re.sub(
            rf"{match_first}.*?{match_last}", "", css, flags=re.DOTALL
        )
        app.setStyleSheet(css + style)

    def onWindowShown(self):
        super().onWindowShown()
        self.handleSplitter()

    def onViewModeChanged(self):
        super().onViewModeChanged()
        self.handleSplitter()

    def onHomeScreenToggled(self, visible: bool = False):
        super().onHomeScreenToggled(visible)
        self.handleSplitter()

    def onThemeChanged(self):
        if not self.topSplit():
            return

        self.attachStyles()

    def onViewChanged(self):
        if not self.topSplit():
            return
        super().onViewChanged()
        helper = self._helper
        mdi = helper.getMdi()
        if mdi:
            activeWin = mdi.activeSubWindow()
            winList = mdi.subWindowList()
            if activeWin and winList:
                activeIndex = winList.index(activeWin)
                self.syncView(index=activeIndex)
        
        # Ensure windowed tabs stay on top after view changes
        self.raiseWindowedTabs()

    def onSubWindowDestroyed(self, uid: int | None) -> None:
        self.winClosed.emit()
        helper = self._helper
        if isinstance(uid, int):
            data = self.popViewData(uid)
            if data:
                toolbar = helper.isAlive(data.toolbar, SplitToolbar)
                split = helper.isAlive(
                    toolbar.split() if toolbar else None, Split
                )
                if split:
                    tabs = helper.isAlive(split.tabs(), SplitTabs)
                    if tabs:
                        splitTabIndex = tabs.getTabByView(data.view)
                        if splitTabIndex != -1:
                            tabs.removeTab(splitTabIndex)
                    split.checkShouldClose()

    def topSplit(self) -> "Split | None":
        central = self._helper.getCentral()
        if central:
            return central.findChild(Split)

    def defaultSplit(self, checkToolbar: bool = True) -> "Split | None":
        if checkToolbar:
            toolbar = self._helper.isAlive(self._activeToolbar, SplitToolbar)
            if toolbar:
                return toolbar.split()

        topSplit = self.topSplit()
        if topSplit:
            return topSplit.firstMostSplit()

    def nextTab(self):
        split = self.defaultSplit()
        if split:
            tabs = split.tabs()
            if tabs:
                tabs.nextTab()

    def prevTab(self):
        split = self.defaultSplit()
        if split:
            tabs = split.tabs()
            if tabs:
                tabs.prevTab()

    def setActiveToolbar(self, curr: SplitToolbar | None = None):
        top = self.topSplit()
        self._activeToolbar = self._helper.isAlive(
            self._activeToolbar, SplitToolbar
        )
        if not top or top.state() == Split.STATE_COLLAPSED:
            if self._activeToolbar:
                self._activeToolbar.tabs().setActiveHighlight(False)
            if top:
                self._activeToolbar = top.toolbar()
            else:
                self._activeToolbar = None
        elif curr:
            if self._activeToolbar and self._activeToolbar != curr:
                self._activeToolbar.tabs().setActiveHighlight(False)

            if top.state() == Split.STATE_SPLIT:
                self._activeToolbar = curr
                self._activeToolbar.tabs().setActiveHighlight(True)
            else:
                self._activeToolbar = None

    @contextmanager
    def syncedCall(self, force: bool = False):
        if self._syncing and not force:
            yield False
            return

        helper = self._helper
        qwin = helper.getQwin()
        mdi = helper.getMdi()
        win = helper.getWin()

        if not (qwin and mdi and win):
            yield False
            return

        syncing = self._syncing
        self._syncing = True
        updates = qwin.updatesEnabled()
        qwin.setUpdatesEnabled(False)
        helper.disableToast()
        try:
            yield True
        finally:
            helper.enableToast()
            qwin.setUpdatesEnabled(updates)
            self._syncing = syncing

    def syncView(
        self,
        index: int | None = None,
        split: "Split|None" = None,
        view: View | None = None,
        document: Document | None = None,
        addView: bool = False,
    ):

        if self._syncing or self._quit:
            return

        with self.syncedCall() as sync:
            if not sync:
                return

            helper = self._helper
            tabs = helper.getTabBar()

            if not tabs:
                return

            mdi = helper.getMdi()
            qwin = helper.getQwin()
            win = helper.getWin()

            assert mdi is not None
            assert qwin is not None
            assert win is not None

            if addView:
                if not isinstance(document, Document):
                    if not isinstance(view, View):
                        return
                    document = view.document()
                view = win.addView(document)
                index = mdi.subWindowList().index(mdi.activeSubWindow())
                view = None

            if view is not None:
                index = self.getIndexByView(view)
                if index == -1:
                    return

            if index is None:
                return

            uid = self.getUid(index)

            if uid is not None:
                data = self.getViewData(uid)
                defaultSplit = self.defaultSplit()
                activeWin = mdi.subWindowList()[index]
                mdi.setActiveSubWindow(activeWin)
                activeView = helper.getView()

                if not activeView:
                    return

                helper.setViewData(activeView, "splitWindowUid", uid)

                if (
                    defaultSplit
                    and mdi.viewMode() == QMdiArea.ViewMode.TabbedView
                ):

                    addTab = False
                    realign = False
                    if data is None:
                        data = ViewData(
                            view=activeView,
                            win=activeWin,
                            toolbar=(
                                split.toolbar()
                                if split
                                else defaultSplit.toolbar()
                            ),
                            watcher=None,
                            watcherCallback=None,
                            realignTick=None,
                        )
                        data.watcherCallback = (
                            lambda _, uid=uid: self.onSubWindowDestroyed(uid)
                        )
                        data.watcher = SubWindowInterceptor(
                            data.watcherCallback
                        )
                        activeWin.installEventFilter(data.watcher)
                        addTab = True
                    else:
                        attachedSplit = helper.isAlive(
                            data.toolbar.split() if data.toolbar else None,
                            Split,
                        )
                        split = helper.isAlive(split, Split)
                        if attachedSplit and split and split != attachedSplit:
                            attachedTabs = attachedSplit.tabs()
                            if attachedTabs:
                                splitTabIndex = attachedTabs.getTabByView(
                                    data.view
                                )
                                if splitTabIndex != -1:
                                    attachedTabs.removeTab(splitTabIndex)
                            data.toolbar = split.toolbar()
                            addTab = True
                        elif split:
                            # Check if tab actually exists in the target toolbar
                            # (handles reintegration from windowed document tabs)
                            targetTabs = split.tabs()
                            if targetTabs:
                                existingTabIndex = targetTabs.getTabByView(data.view)
                                if existingTabIndex == -1:
                                    # Tab doesn't exist in toolbar - need to add it
                                    data.toolbar = split.toolbar()
                                    addTab = True

                    toolbar = helper.isAlive(data.toolbar, SplitToolbar)
                    if toolbar:
                        toolbarSplit = helper.isAlive(toolbar.split(), Split)
                        assert toolbarSplit is not None
                        toolbarTabs = toolbar.tabs()
                        splitTabIndex = -1
                        if addTab:
                            self.setViewData(uid, data)

                            # Use full tab text - elide mode handles truncation visually
                            tabText = tabs.tabText(index)

                            # Hide Krita logo by using empty icon if configured
                            if HIDE_TAB_ICON:
                                splitTabIndex = toolbarTabs.addTab(tabText)
                            else:
                                splitTabIndex = toolbarTabs.addTab(
                                    tabs.tabIcon(index), tabText
                                )
                            if splitTabIndex != -1:
                                toolbarTabs.setUid(splitTabIndex, uid)

                            realign = True
                        else:
                            splitTabIndex = toolbarTabs.getTabByView(data.view)
                            realign = (
                                toolbarSplit._realignTick  # pyright: ignore [reportPrivateUsage]
                                != data.realignTick
                            )

                        data.realignTick = (
                            toolbarSplit._realignTick  # pyright: ignore [reportPrivateUsage]
                        )

                        if realign:
                            QTimer.singleShot(
                                10,
                                lambda: toolbarSplit.realignCanvas(
                                    view=data.view, tick=False
                                ),
                            )

                        if splitTabIndex != -1:
                            toolbarTabs.setCurrentIndex(splitTabIndex)

                        if toolbarSplit:
                            topSplit = toolbarSplit.topSplit()
                            if topSplit:
                                topSplit.resize(force=True)
                            data.win.raise_()
                            data.win.show()
                            ts = toolbar.split()
                            tp = ts.parent()
                            if isinstance(tp, Split):
                                self.setActiveToolbar(toolbar)
                            else:
                                self.setActiveToolbar(toolbar)

    def getUid(self, index: int | None) -> int | None:
        if index is not None:
            helper = self._helper
            mdi = helper.getMdi()
            if not mdi:
                return
            subwindows = mdi.subWindowList()
            if index >= 0 and index < len(subwindows):
                win = subwindows[index]
                uid = win.property("splitWindowUid")
                if not uid:
                    uid = helper.uid()
                    win.setProperty("splitWindowUid", uid)
                return uid

    def getViewData(self, uid: int | None) -> ViewData | None:
        if uid is not None:
            return self._viewData.get(uid, None)

    def setViewData(self, uid: int | None, data: Any) -> ViewData | None:
        if uid is not None:
            self._viewData[uid] = data

    def popViewData(self, uid: int | None) -> ViewData | None:
        if uid is not None:
            return self._viewData.pop(uid, None)

    def getIndexByView(self, view: View | None) -> int:
        mdi = self._helper.getMdi()
        if not mdi:
            return -1
        data = self._helper.getViewData(view)
        uid = data.get("splitWindowUid", None) if data else None
        if uid is not None:
            for i, w in enumerate(mdi.subWindowList()):
                if w.property("splitWindowUid") == uid:
                    return i
        return -1

    def getIndexByWindow(self, win: QMdiSubWindow | None) -> int:
        mdi = self._helper.getMdi()
        try:
            assert mdi is not None
            assert win is not None
            ret = mdi.subWindowList().index(win)
            return ret
        finally:
            return -1

    def getToolbarByView(self, view: View | None) -> SplitToolbar | None:
        if view is not None:
            data = self._helper.getViewData(view)
            uid = data.get("splitWindowUid", None) if data else None
            data = self.getViewData(uid)
            return (
                self._helper.isAlive(data.toolbar, SplitToolbar)
                if data
                else None
            )

    def getToolbarByWindow(
        self, win: QMdiSubWindow | None
    ) -> SplitToolbar | None:
        if win:
            uid = win.property("splitWindowUid")
            data = self.getViewData(uid)
            return (
                self._helper.isAlive(data.toolbar, SplitToolbar)
                if data
                else None
            )

    def getSplitByView(self, view: View | None) -> "Split | None":
        toolbar = self.getToolbarByView(view)
        if toolbar:
            return toolbar.split()

    def getSplitByWindow(self, win: QMdiSubWindow | None) -> "Split | None":
        toolbar = self.getToolbarByWindow(win)
        if toolbar:
            return toolbar.split()
    
    # === Windowed Document Tab Management ===
    
    def addWindowedTab(self, windowedTab: WindowedDocumentTab):
        """Add a windowed document tab to tracking."""
        if windowedTab not in self._windowedTabs:
            self._windowedTabs.append(windowedTab)
            # Ensure it stays on top
            windowedTab.raise_()
    
    def removeWindowedTab(self, windowedTab: WindowedDocumentTab):
        """Remove a windowed document tab from tracking."""
        if windowedTab in self._windowedTabs:
            self._windowedTabs.remove(windowedTab)
    
    def getWindowedTabs(self) -> list[WindowedDocumentTab]:
        """Get all windowed document tabs."""
        return self._windowedTabs.copy()
    
    def getWindowedTabByView(self, view: View | None) -> WindowedDocumentTab | None:
        """Find a windowed document tab by its view."""
        if view:
            for wt in self._windowedTabs:
                if wt.view() == view:
                    return wt
        return None
    
    def getWindowedTabByUid(self, uid: int | None) -> WindowedDocumentTab | None:
        """Find a windowed document tab by its UID."""
        if uid is not None:
            for wt in self._windowedTabs:
                if wt.uid() == uid:
                    return wt
        return None
    
    def raiseWindowedTabs(self):
        """Raise all windowed document tabs to stay on top."""
        for wt in self._windowedTabs:
            wt.raise_()

    def _installDockFocusWatcher(self):
        if self._dockFocusConnected:
            return
        qapp = typing.cast(QApplication, QApplication.instance())
        if not qapp:
            return
        qapp.focusChanged.connect(self._onFocusChanged)
        if not self._dockTabEventFilter:
            self._dockTabEventFilter = DockTabEventFilter(
                self._onDockTabBarEvent
            )
            qapp.installEventFilter(self._dockTabEventFilter)
        self._dockFocusConnected = True

    def _installDockTabifiedWatcher(self):
        if self._dockTabifiedConnected:
            return
        qwin = self._helper.getQwin()
        if not qwin:
            return
        if hasattr(qwin, "tabifiedDockWidgetActivated"):
            qwin.tabifiedDockWidgetActivated.connect(
                self._onDockTabifiedActivated
            )
            self._dockTabifiedConnected = True

    def _onDockTabifiedActivated(self, _dock: QDockWidget | None = None):
        if not self._windowedTabs:
            return
        QTimer.singleShot(0, self.raiseWindowedTabs)

    def _onFocusChanged(self, _old: QWidget | None, new: QWidget | None):
        if not self._windowedTabs or not new:
            return
        if not self._focusIsInDockArea(new):
            return
        QTimer.singleShot(0, self.raiseWindowedTabs)

    def _onDockTabBarEvent(self, tab_bar: QTabBar):
        if not self._windowedTabs:
            return
        if isinstance(tab_bar, SplitTabs):
            return
        central = self._helper.getCentral()
        if central and central.isAncestorOf(tab_bar):
            return
        QTimer.singleShot(0, self.raiseWindowedTabs)

    def _focusIsInDockArea(self, widget: QWidget) -> bool:
        central = self._helper.getCentral()
        if central and central.isAncestorOf(widget):
            return False
        if isinstance(widget, QTabBar):
            return True
        if isinstance(widget, QDockWidget):
            return True

        win = self._helper.getWin()
        if win:
            for dock in win.dockers():
                if dock and dock.isAncestorOf(widget):
                    return True

        w = widget
        while w:
            try:
                cls_name = w.metaObject().className()
            except Exception:
                cls_name = ""
            if cls_name and (
                "DockWidgetGroupWindow" in cls_name
                or "DockWidget" in cls_name
                or "Docker" in cls_name
            ):
                return True
            w = w.parentWidget()

        return False
