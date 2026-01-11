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

from PyQt5.QtWidgets import QMdiArea, QDockWidget
from krita import Krita
from .ntadjusttosubwindowfilter import ntAdjustToSubwindowFilter
from .ntwidgetpad import ntWidgetPad
from .. import variables


def find_docker_by_names(window, names):
    """Try to find a docker by multiple possible object names."""
    for name in names:
        docker = window.findChild(QDockWidget, name)
        if docker is not None:
            return docker
    return None


class ntToolBox():

    def __init__(self, window):
        qWin = window.qwindow()
        mdiArea = qWin.findChild(QMdiArea)
        
        if mdiArea is None:
            raise RuntimeError("Could not find QMdiArea - NuToolbox requires MDI mode")
        
        # Try multiple possible docker names for Krita 5.x compatibility
        toolbox_names = ['ToolBox', 'toolbox', 'KoToolBox', 'toolBoxDocker']
        toolbox = find_docker_by_names(qWin, toolbox_names)
        
        if toolbox is None:
            raise RuntimeError("Could not find Toolbox docker")

        # Create "pad" with persistent key for collapse state
        self.pad = ntWidgetPad(mdiArea, persistentKey="nuToolbox")
        self.pad.setObjectName("toolBoxPad")
        self.pad.setViewAlignment('left')
        self.pad.borrowDocker(toolbox)
        
        # Create and install event filter
        self.adjustFilter = ntAdjustToSubwindowFilter(mdiArea)
        self.adjustFilter.setTargetWidget(self.pad)
        mdiArea.subWindowActivated.connect(self.ensureFilterIsInstalled)
        qWin.installEventFilter(self.adjustFilter)

        # Create visibility toggle action
        action = window.createAction("showToolbox", "Show Toolbox", "settings")
        action.setCheckable(True)

        # Start collapsed by default on first run (persisted via Redesign/nuToolbox_collapsed)
        isCollapsed = Krita.instance().readSetting("Redesign", "nuToolbox_collapsed", "true") == "true"
        action.setChecked(not isCollapsed)

        # Connect after setChecked() so we don't override the restored state on startup
        action.toggled.connect(self.pad.toggleWidgetVisible)

        # Disable the related QDockWidget
        self.dockerAction = toolbox.toggleViewAction()
        self.dockerAction.setEnabled(False)
        
        # Store reference to the toolbox docker for cleanup
        self._toolbox = toolbox

    def ensureFilterIsInstalled(self, subWin):
        """Ensure that the current SubWindow has the filter installed,
        and immediately move the Toolbox to current View."""
        if subWin:
            subWin.installEventFilter(self.adjustFilter)
            self.pad.adjustToView()
            self.updateStyleSheet()

    def findDockerAction(self, window, text):
        dockerMenu = None
        
        for m in window.qwindow().actions():
            if m.objectName() == "settings_dockers_menu":
                dockerMenu = m

                for a in dockerMenu.menu().actions():
                    if a.text().replace('&', '') == text:
                        return a
                
        return False

    def updateStyleSheet(self):
        try:
            self.pad.setStyleSheet(variables.nu_toolbox_style)
        except Exception as e:
            print(f"[Redesign] Could not update toolbox stylesheet: {e}")

    def close(self):
        if self.dockerAction:
            self.dockerAction.setEnabled(True)
        return self.pad.close()