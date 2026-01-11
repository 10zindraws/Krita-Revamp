"""
    Plugin for Krita UI Redesign, Copyright (C) 2020 Kapyia
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

from krita import Krita 
from PyQt5.QtCore import QObject, QEvent, QPoint

try:
    import sip  # type: ignore
except Exception:
    sip = None


def _is_deleted(qobj) -> bool:
    """Best-effort check for whether a Qt object has been deleted."""
    if qobj is None:
        return True
    if sip is not None:
        try:
            return bool(sip.isdeleted(qobj))
        except Exception:
            return False
    return False


class ntAdjustToSubwindowFilter(QObject):
    """
    Event Filter object. Ensure that a target widget is moved
    to a desired position (corner of the view) when the subwindow area updates.
    
    Updated for Krita 5.2+ compatibility.
    """
    
    def __init__(self, parent=None):
        super(ntAdjustToSubwindowFilter, self).__init__(parent)
        self.target = None

    def _onTargetDestroyed(self, *args):
        # Avoid keeping a Python reference to a deleted Qt object.
        self.target = None

    def eventFilter(self, obj, e):
        """Event filter: Update the Target's position to match to the current view
        if the (sub-)window has moved, changed in size or been activated."""
        t = self.target
        if (t and (e.type() == QEvent.Move or e.type() == QEvent.Resize or e.type() == QEvent.WindowActivate)):
            if _is_deleted(t):
                self.target = None
                return False
            try:
                t.adjustToView()
            except RuntimeError:
                # Target was deleted (wrapped C/C++ object...). Stop tracking it.
                self.target = None
        return False

    def setTargetWidget(self, wdgt):
        """Set which QWidget to adjust the position of."""
        self.target = wdgt
        if wdgt:
            # Ensure we clear the reference when the Qt object is destroyed.
            try:
                wdgt.destroyed.disconnect(self._onTargetDestroyed)
            except Exception:
                pass
            try:
                wdgt.destroyed.connect(self._onTargetDestroyed)
            except Exception:
                pass