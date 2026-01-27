from krita import *
from PyQt5.QtWidgets import QWidget, QAction, QComboBox
from functools import partial
from pprint import pprint
from .api_krita import Krita as KritaAPI
from .api_krita.wrappers.database import Database

KRITA_ERASE_ACTION = "erase_action"
BRUSH_ACTION = "dninosores_activate_brush"
ERASE_ACTION = "dninosores_activate_eraser"
ERASE_ON_ACTION = "dninosores_eraser_on"
ERASE_OFF_ACTION = "dninosores_eraser_off"
ERASE_TOGGLE_ACTION = "dninosores_eraser_toggle"
MENU_LOCATION = "tools/scripts"
BRUSH_MODE = "BRUSH"
ERASER_MODE = "ERASER"

DEBUG = True


def print_dbg(msg):
    if DEBUG:
        print(msg)


class BrushSettings:

    def loadSettings(self):
        self.preset = KritaAPI.get_active_view().brush_preset
        self.size = KritaAPI.get_active_view().brush_size
        self.flow = KritaAPI.get_active_view().flow
        self.opacity = KritaAPI.get_active_view().opacity
        return self

    def applySettings(self):
        KritaAPI.get_active_view().brush_preset = self.preset
        KritaAPI.get_active_view().brush_size = self.size
        KritaAPI.get_active_view().flow = self.flow
        KritaAPI.get_active_view().opacity = self.opacity
        return self


class BrushState:
    # Store a brush state for each view
    eraser_on: bool = False
    brush_settings: BrushSettings = None
    eraser_settings: BrushSettings = None


class SeparateBrushEraserExtension(Extension):
    brush_state = None

    def __init__(self, parent):
        super().__init__(parent)

    def switch_to_brush(self):
        Krita.instance().action("KritaShape/KisToolBrush").trigger()

    def eraser_active(self):
        return Application.action(KRITA_ERASE_ACTION).isChecked()

    def preset_name(self, preset):
        """Normalize preset name from Krita API objects or strings."""
        if not preset:
            return ""
        if isinstance(preset, str):
            return preset
        if hasattr(preset, "name"):
            try:
                return preset.name()
            except TypeError:
                return preset.name
        return str(preset)

    def get_preset_docker(self):
        """Find the Brush Presets docker widget."""
        for docker in Krita.instance().dockers():
            if docker.objectName() == "PresetDocker":
                return docker
        return None

    def switch_to_tag(self, tag_url: str):
        """Switch the Brush Presets docker to a specific tag url."""
        if not tag_url:
            return
        docker = self.get_preset_docker()
        if not docker:
            print_dbg(f"[Tag Switch] Docker not found")
            return

        # Find KisTagChooserWidget by looking for its internal QComboBox
        # The hierarchy is: docker > KisPaintOpPresetsChooserPopup > KisPresetChooser >
        # KisResourceItemChooser > ... > KisTagChooserWidget > QComboBox
        # We search the entire docker for QComboBox instances and identify the tag combo
        # by checking if the first item's URL (Qt::UserRole + 1) is "All"
        combos = docker.findChildren(QComboBox)
        print_dbg(f"[Tag Switch] Found {len(combos)} combo boxes in docker")

        tag_combo = None
        for combo in combos:
            model = combo.model()
            if not model or model.rowCount() <= 0:
                continue
            # Check if first item has "All" as URL (UserRole + 1 = Url column in KisTagModel)
            first_url = model.data(model.index(0, 0), Qt.UserRole + 1)
            if first_url == "All":
                tag_combo = combo
                print_dbg(f"[Tag Switch] Found tag combo box (first URL = 'All')")
                break

        if not tag_combo:
            print_dbg(f"[Tag Switch] Tag combo box not found")
            return

        model = tag_combo.model()
        print_dbg(f"[Tag Switch] Looking for tag URL: '{tag_url}' in {model.rowCount()} rows")
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            row_url = model.data(index, Qt.UserRole + 1)  # Url column
            print_dbg(f"[Tag Switch]   Row {row}: URL = '{row_url}'")
            if row_url == tag_url:
                if tag_combo.currentIndex() != row:
                    print_dbg(f"[Tag Switch] Switching from row {tag_combo.currentIndex()} to row {row}")
                    tag_combo.setCurrentIndex(row)
                else:
                    print_dbg(f"[Tag Switch] Already on correct tag (row {row})")
                return
        print_dbg(f"[Tag Switch] Tag URL '{tag_url}' not found in combo")

    def maybe_switch_tag(self, from_preset_name: str, to_preset_name: str):
        """Switch tags only when presets are not in any shared tag."""
        print_dbg(f"[maybe_switch_tag] Called with from='{from_preset_name}', to='{to_preset_name}'")
        if not to_preset_name:
            print_dbg(f"[maybe_switch_tag] No target preset name")
            return
        with Database() as db:
            to_tags = db.get_tags_for_preset(to_preset_name)
            from_tags = set(db.get_tags_for_preset(from_preset_name)) if from_preset_name else set()
        print_dbg(f"[maybe_switch_tag] From preset: '{from_preset_name}', tags: {from_tags}")
        print_dbg(f"[maybe_switch_tag] To preset: '{to_preset_name}', tags: {to_tags}")
        if not to_tags:
            # Target preset has no dedicated tags, switch to "All" tag
            print_dbg(f"[maybe_switch_tag] Target preset has no tags, switching to 'All'")
            QTimer.singleShot(0, lambda: self.switch_to_tag("All"))
            return
        target_tag = to_tags[0]  # Capture the tag value before lambda
        if not from_tags:
            print_dbg(f"[maybe_switch_tag] Source has no tags, switching to: {target_tag}")
            QTimer.singleShot(0, lambda t=target_tag: self.switch_to_tag(t))
            return
        for tag in to_tags:
            if tag in from_tags:
                print_dbg(f"[maybe_switch_tag] Presets share tag: {tag}, not switching")
                return
        print_dbg(f"[maybe_switch_tag] No shared tags, switching to: {target_tag}")
        QTimer.singleShot(0, lambda t=target_tag: self.switch_to_tag(t))

    def get_current_brush_state(self):
        if (not KritaAPI.get_active_view() or not Application.activeWindow().
                activeView().currentBrushPreset()):
            return None
        if self.brush_state:
            return self.brush_state
        else:
            current_state = BrushState()
            current_state.eraser_on = self.eraser_active()
            current_state.brush_settings = BrushSettings().loadSettings()
            current_state.eraser_settings = BrushSettings().loadSettings()
            self.brush_state = current_state
            return current_state

    def apply_brush_state(self, state: BrushState) -> BrushState:
        """Sets brush settings to match the given state"""
        print_dbg(f"[apply_brush_state] eraser_active={self.eraser_active()}, state.eraser_on={state.eraser_on}")
        if self.eraser_active() == state.eraser_on:
            print_dbg(f"[apply_brush_state] States match, no change needed")
            return state

        current_settings = BrushSettings().loadSettings()
        current_preset_name = self.preset_name(current_settings.preset)
        print_dbg(f"[apply_brush_state] Current preset: {current_preset_name}")

        # toggling the eraser on
        if state.eraser_on:
            state.brush_settings = current_settings
            state.eraser_settings.applySettings()
            target_preset_name = self.preset_name(state.eraser_settings.preset)
            print_dbg(f"[apply_brush_state] Switching TO eraser, target preset: {target_preset_name}")
        else:
            state.eraser_settings = current_settings
            state.brush_settings.applySettings()
            target_preset_name = self.preset_name(state.brush_settings.preset)
            print_dbg(f"[apply_brush_state] Switching TO brush, target preset: {target_preset_name}")

        if target_preset_name:
            self.maybe_switch_tag(current_preset_name, target_preset_name)
        self.verify_eraser_state()
        return state

    def apply_current_brush_state(self):
        return self.apply_brush_state(self.get_current_brush_state())

    def activate_brush(self, switchTool=True):
        if not self.get_current_brush_state():
            return
        self.get_current_brush_state().eraser_on = False
        if switchTool:
            self.switch_to_brush()
        self.apply_current_brush_state()
        QTimer.singleShot(0, self.verify_eraser_state)

    def activate_eraser(self, switchTool=True):
        if not self.get_current_brush_state():
            return
        self.get_current_brush_state().eraser_on = True
        if switchTool:
            self.switch_to_brush()
        self.apply_current_brush_state()
        QTimer.singleShot(0, self.verify_eraser_state)

    def on_brush_toggled(self, toggled):
        if not self.get_current_brush_state():
            return
        # Triggers when krita switches to/from the brush tool for any reason. Does not trigger if the brush tool is already selected.
        if toggled:
            pass
        elif QApplication.queryKeyboardModifiers() & Qt.ShiftModifier:
            pass
            # print("Keeping eraser on bc shift is down")
        else:
            # print("Turning off eraser bc shift is not down")
            self.get_current_brush_state().eraser_on = False
            self.apply_current_brush_state()

    def verify_eraser_state(self):
        if self.get_current_brush_state():
            desired_state = self.get_current_brush_state().eraser_on
            if desired_state != self.eraser_active():
                Application.action(KRITA_ERASE_ACTION).trigger()

    def on_eraser_action(self, toggled):
        pass
        # self.get_eraser_button().setChecked(self.eraser_active())
        # self.verify_eraser_state()

    def classic_krita_eraser_toggle_auto(self):
        self.classic_krita_eraser_toggle(not self.brush_state.eraser_on)

    def classic_krita_eraser_toggle(self, toggled):
        # self.verify_eraser_state()
        # toggled = self.get_current_brush_state().eraser_on
        if toggled:
            self.activate_eraser(False)
        else:
            self.activate_brush(False)

    def on_eraser_button_clicked(self, toggled):
        # print(f"Clicked with value {toggled}")
        # Actually I think it would be better if this toggled like regular krita
        # i.e. swap the brush presets, then toggle eraser without switching tool
        # actually don't swap the brush presets but to toggle eraser without switching tool
        self.classic_krita_eraser_toggle(toggled)

    def on_eraser_button_toggled(self, toggled):
        # print(f"Button toggled with value {toggled}")
        self.get_eraser_button().setChecked(self.eraser_active())
        # self.verify_eraser_state()

    def setup(self):
        pass

    def createActions(self, window):
        # actions should be:
        # Switch to brush / switch to eraser, which activate the brush tool
        # Activate brush / eraser, which switch without activating the brush tool
        # Toggle, which toggles between the two options without switching the tool
        # A 'when you hold shift temporarily switch to the line tool without deactivating eraser' action
        activate_brush_action = window.createAction(BRUSH_ACTION,
                                                    "Switch to Brush",
                                                    MENU_LOCATION)
        activate_eraser_action = window.createAction(ERASE_ACTION,
                                                     "Switch to Eraser",
                                                     MENU_LOCATION)
        enable_eraser_action = window.createAction(ERASE_ON_ACTION,
                                                   "Activate Eraser",
                                                   MENU_LOCATION)
        disable_eraser_action = window.createAction(ERASE_OFF_ACTION,
                                                    "Deactivate Eraser",
                                                    MENU_LOCATION)
        toggle_eraser_action = window.createAction(ERASE_TOGGLE_ACTION,
                                                   "Toggle Eraser",
                                                   MENU_LOCATION)
        activate_brush_action.triggered.connect(
            partial(self.activate_brush, True))
        activate_eraser_action.triggered.connect(
            partial(self.activate_eraser, True))
        enable_eraser_action.triggered.connect(
            partial(self.activate_eraser, False))
        disable_eraser_action.triggered.connect(
            partial(self.activate_brush, False))
        toggle_eraser_action.triggered.connect(
            self.classic_krita_eraser_toggle_auto)

        QTimer.singleShot(500, self.bind_brush_toggled)

    def get_eraser_button(self):
        qwin = Application.activeWindow().qwindow()
        pobj = qwin.findChild(QToolBar, 'BrushesAndStuff')
        eraser_button = None
        for item, depth in IterHierarchy(pobj):
            try:
                if item.defaultAction() == Application.action(
                        KRITA_ERASE_ACTION):
                    eraser_button = item
            except:
                pass
        return eraser_button

    def print_state(self):
        if self.get_current_brush_state():
            desired_state = self.get_current_brush_state().eraser_on
            print(f"Eraser should be {desired_state}")
            print(f"Button checked is {self.get_eraser_button().isChecked()}")
            print(f"Eraser action is {self.eraser_active()}")
            print("\n")

    def bind_brush_toggled(self):
        success = False
        Application.action(KRITA_ERASE_ACTION).triggered.connect(
            self.on_eraser_action)
        for docker in Krita.instance().dockers():
            if docker.objectName() == "ToolBox":
                for item, level in IterHierarchy(docker):
                    if item.objectName() == "KritaShape/KisToolBrush":
                        brush_tool = item
                        brush_tool.toggled.connect(self.on_brush_toggled)
                        success = True
        if not success:
            print(
                "Binding eraser toggle to brush button failed. Try restarting Krita."
            )
        eraser_button = self.get_eraser_button()

        eraser_button.toggled.connect(self.on_eraser_button_toggled)
        eraser_button.clicked.connect(self.on_eraser_button_clicked)

        timer = QTimer(Application.activeWindow().qwindow())
        timer.timeout.connect(self.verify_eraser_state)
        timer.start(1)


class IterHierarchy:
    queue = []

    def __init__(self, root):
        self.root = root
        self.queue = []

    def __iter__(self):
        self.queue = self.walk_hierarchy(self.root)
        return self

    def walk_hierarchy(self, item, level=0, acc=[]):
        acc.append((item, level))
        for child in item.children():
            self.walk_hierarchy(child, level + 1, acc)
        return acc

    def __next__(self):
        if len(self.queue) > 0:
            cur_item = self.queue.pop(0)
            return cur_item[0], cur_item[1]
        else:
            raise StopIteration


Krita.instance().addExtension(SeparateBrushEraserExtension(Krita.instance()))
