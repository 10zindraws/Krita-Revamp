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

from krita import *
from PyQt5.QtWidgets import QWidget, QMessageBox
from .nuTools.nttoolbox import ntToolBox
from .nuTools.nttooloptions import ntToolOptions
from . import variables


def find_docker_widget(window, docker_names):
    """
    Find a docker widget by trying multiple possible names.
    Krita 5.x may have different docker names than older versions.
    
    Args:
        window: QMainWindow instance
        docker_names: List of possible docker object names to try
    
    Returns:
        QWidget or None if not found
    """
    for name in docker_names:
        docker = window.findChild(QWidget, name)
        if docker is not None:
            return docker
    return None


class Redesign(Extension):

    usesFlatTheme = True  # Permanently enabled
    usesThinDocumentTabs = True  # Permanently enabled
    usesNuToolbox = False
    usesNuToolOptions = False
    ntTB = None
    ntTO = None

    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        # Flat theme and thin tabs are permanently enabled
        # No longer reading from settings

        if Application.readSetting("Redesign", "usesNuToolbox", "true") == "true":
            self.usesNuToolbox = True

        if Application.readSetting("Redesign", "usesNuToolOptions", "true") == "true":
            self.usesNuToolOptions = True

    def createActions(self, window):
        actions = []

        # Removed "Thin Document Tabs" and "Use PS Flat Theme" - now permanently enabled

        actions.append(window.createAction("nuToolbox", "NuToolbox", ""))
        actions[0].setCheckable(True)
        actions[0].setChecked(self.usesNuToolbox)

        actions.append(window.createAction("nuToolOptions", "NuToolOptions", ""))
        actions[1].setCheckable(True)

        if Application.readSetting("", "ToolOptionsInDocker", "false") == "true":
            actions[1].setChecked(self.usesNuToolOptions)

        menu = window.qwindow().menuBar().addMenu("Redesign")

        for a in actions:
            menu.addAction(a)

        actions[0].toggled.connect(self.nuToolboxToggled)
        actions[1].toggled.connect(self.nuToolOptionsToggled)

        # Build the flat theme stylesheets
        variables.buildFlatTheme()

        if (self.usesNuToolOptions and
            Application.readSetting("", "ToolOptionsInDocker", "false") == "true"):
                try:
                    self.ntTO = ntToolOptions(window)
                except Exception as e:
                    print(f"[Redesign] Failed to initialize NuToolOptions: {e}")

        if self.usesNuToolbox:
            try:
                self.ntTB = ntToolBox(window)
            except Exception as e:
                print(f"[Redesign] Failed to initialize NuToolbox: {e}")

        self.rebuildStyleSheet(window.qwindow())

        #self.nuToolOptionsToggled(self.usesNuToolOptions)
        #self.nuToolOptionsToggled(self.usesNuToolOptions)

    # Removed flatThemeToggled and tabHeightToggled methods - these are now permanently enabled

    def nuToolboxToggled(self, toggled):
        Application.writeSetting("Redesign", "usesNuToolbox", str(toggled).lower())
        self.usesNuToolbox = toggled

        if toggled:
            try:
                self.ntTB = ntToolBox(Application.activeWindow())
                self.ntTB.pad.show() 
                self.ntTB.updateStyleSheet()
            except Exception as e:
                print(f"[Redesign] Failed to enable NuToolbox: {e}")
                self.ntTB = None
        elif not toggled and self.ntTB:
            try:
                self.ntTB.close()
            except Exception:
                pass
            self.ntTB = None

    def nuToolOptionsToggled(self, toggled):
        if Application.readSetting("", "ToolOptionsInDocker", "false") == "true":
            Application.writeSetting("Redesign", "usesNuToolOptions", str(toggled).lower())
            self.usesNuToolOptions = toggled

            if toggled:
                try:
                    self.ntTO = ntToolOptions(Application.activeWindow())
                    self.ntTO.pad.show() 
                    self.ntTO.updateStyleSheet()
                except Exception as e:
                    print(f"[Redesign] Failed to enable NuToolOptions: {e}")
                    self.ntTO = None
            elif not toggled and self.ntTO:
                try:
                    self.ntTO.close()
                except Exception:
                    pass
                self.ntTO = None
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Redesign - NuToolOptions")
            msg.setText("NuToolOptions requires the Tool Options Location to be set to 'In Docker'.\n\n" +
                        "This setting can be found at:\n" +
                        "Settings → Configure Krita... → General → Tools → Tool Options Location\n\n" +
                        "Once the setting has been changed, please restart Krita.")
            msg.setIcon(QMessageBox.Information)
            msg.exec_()

    def rebuildStyleSheet(self, window):
        """
        Rebuild and apply the complete stylesheet based on current settings.
        Updated for Krita 5.2+ compatibility.
        """
        full_style_sheet = ""
        
        # Apply flat theme styles (Photoshop-style)
        if self.usesFlatTheme:
            full_style_sheet += f"\n {variables.flat_dock_style} \n"
            full_style_sheet += f"\n {variables.flat_button_style} \n"
            full_style_sheet += f"\n {variables.flat_main_window_style} \n"
            full_style_sheet += f"\n {variables.flat_menu_bar_style} \n"
            full_style_sheet += f"\n {variables.flat_combo_box_style} \n"
            full_style_sheet += f"\n {variables.flat_status_bar_style} \n"
            full_style_sheet += f"\n {variables.flat_tab_base_style} \n"
            full_style_sheet += f"\n {variables.flat_tree_view_style} \n"
            full_style_sheet += f"\n {variables.flat_scroll_style} \n"
            full_style_sheet += f"\n {variables.flat_slider_style} \n"
            full_style_sheet += f"\n {variables.flat_spinbox_style} \n"
            full_style_sheet += f"\n {variables.flat_toolbar_style} \n"
        
        # Apply the main window stylesheet
        window.setStyleSheet(full_style_sheet)

        # Overview Docker - try multiple possible names for Krita 5.x compatibility
        overview_docker_names = ['OverviewDocker', 'overviewdocker', 'overview_docker']
        overview = find_docker_widget(window, overview_docker_names)
        
        if overview and self.usesFlatTheme:
            try:
                overview.setStyleSheet(variables.flat_overview_docker_style)
            except Exception as e:
                print(f"[Redesign] Could not style OverviewDocker: {e}")

        # Document tabs (canvas area)
        canvas_style_sheet = ""

        if self.usesFlatTheme:
            if self.usesThinDocumentTabs:
                canvas_style_sheet += f"\n {variables.flat_tab_small_style} \n"
            else: 
                canvas_style_sheet += f"\n {variables.flat_tab_big_style} \n"
        else: 
            if self.usesThinDocumentTabs:
                canvas_style_sheet += f"\n {variables.small_tab_style} \n"

        canvas = window.centralWidget()
        if canvas:
            try:
                canvas.setStyleSheet(canvas_style_sheet)
                # Force size update
                canvas.resize(canvas.sizeHint())
            except Exception as e:
                print(f"[Redesign] Could not style canvas: {e}")

        # Update NuToolOptions stylesheet
        if self.usesNuToolOptions and self.ntTO:
            try:
                self.ntTO.updateStyleSheet()
            except Exception as e:
                print(f"[Redesign] Could not update NuToolOptions stylesheet: {e}")

        # Update NuToolbox stylesheet
        if self.usesNuToolbox and self.ntTB:
            try:
                self.ntTB.updateStyleSheet()
            except Exception as e:
                print(f"[Redesign] Could not update NuToolbox stylesheet: {e}")

Krita.instance().addExtension(Redesign(Krita.instance()))
