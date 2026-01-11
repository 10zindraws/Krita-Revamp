# SPDX-License-Identifier: CC0-1.0

from .pyqt import Qt
from .component import Component, Window


class Dockers(Component):
    def __init__(self, window: Window):
        super().__init__(window)
        
        app = self._helper.getApp()
        assert app is not None
        
        # Ensure docking stays enabled now that the toggle option is removed.
        app.writeSetting("krita_ui_teaks", "dockingEnabled", "true")

        for dock in window.dockers():
            dock.setAllowedAreas(Qt.AllDockWidgetAreas)
