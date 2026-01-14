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
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QApplication


def _get_palette_color(role):
    """
    Get palette color safely, compatible with both Qt 5.x and newer versions.
    Returns hex color string without the '#' prefix.
    """
    try:
        palette = QApplication.instance().palette()
        color = palette.color(role)
        return color.name().lstrip("#")
    except Exception:
        # Fallback colors (dark theme defaults)
        fallbacks = {
            QPalette.Highlight: "3daee9",
            QPalette.Window: "31363b",
            QPalette.AlternateBase: "2a2e32",
            QPalette.ToolTipText: "7f8c8d",
            QPalette.WindowText: "eff0f1",
            QPalette.Base: "1d2023",
            QPalette.Text: "eff0f1",
            QPalette.Button: "31363b",
            QPalette.ButtonText: "eff0f1",
        }
        return fallbacks.get(role, "888888")


# Color definitions - extracted from current palette for Photoshop-like flat theme
highlight = _get_palette_color(QPalette.Highlight)
background = _get_palette_color(QPalette.Window)
alternate = _get_palette_color(QPalette.AlternateBase)
inactive_text_color = _get_palette_color(QPalette.ToolTipText)
active_text_color = _get_palette_color(QPalette.WindowText)
base_color = _get_palette_color(QPalette.Base)
text_color = _get_palette_color(QPalette.Text)
button_color = _get_palette_color(QPalette.Button)

# Photoshop-style dark theme color overrides for a more authentic look
# These provide a flatter, more professional appearance
ps_bg_dark = "4d4d4d"       # Main dark background (Photoshop style)
ps_bg_medium = "424242"     # Medium panels (dockers, content areas)
ps_bg_toolbar = "4d4d4d"    # Toolbar & titlebar backgrounds
ps_bg_light = "5a5a5a"      # Lighter elements, hover states
ps_accent = "6b6b6b"        # Selection, active elements
ps_accent_hover = "7a7a7a"  # Brighter on hover
ps_border = "4d4d4d"        # Subtle borders
ps_separator = "383838"     # 2px separator lines between UI elements
ps_text = "f0f0f0"          # Main text color
ps_text_dim = "a0a0a0"      # Dimmed/inactive text

small_tab_size = 18

no_borders_style = " QToolBar { border: none; } "

nu_toolbox_style = f"""
            QWidget {{ 
                background-color: #01{alternate};
            }}
            
            .QScrollArea {{ 
                background-color: #00{background};
            }}
            
            QScrollArea * {{ 
                background-color: #00000000;
            }}
            
            QScrollArea QToolTip {{
                background-color: #{active_text_color};                         
            }}
            
            QAbstractButton {{
                background-color: #aa{background};
                border: none;
                border-radius: 4px;
            }}
            
            QAbstractButton:checked {{
                background-color: #cc{highlight};
            }}
            
            QAbstractButton:hover {{
                background-color: #{highlight};
            }}
            
            QAbstractButton:pressed {{
                background-color: #{alternate};
            }}
        """

nu_toggle_button_style = f"""
        QToolButton {{
            background-color: #aa{background};
            border: none;
            border-radius: 4px;
        }}
        
        QToolButton:hover {{
            background-color: #{highlight};
        }}
        
        QToolButton:pressed {{
            background-color: #{alternate};
        }}
        """

nu_scroll_area_style = f"""
        QScrollArea {{ 
            background-color: #{ps_bg_dark};
            border: none;
        }}
        """

small_tab_style = f"""
    QTabBar::tab {{ height: {small_tab_size}px; }}
    
    /* Exclude QMdiArea's native QTabBar (direct child only, not SplitTabs) */
    QMdiArea > QTabBar {{ min-height: 0px; max-height: 0px; padding: 0px; margin: 0px; border: none; }}
    QMdiArea > QTabBar::tab {{ min-height: 0px; max-height: 0px; min-width: 0px; max-width: 0px; padding: 0px; margin: 0px; border: none; }}
"""

""" FLAT THEME - Photoshop-style for Krita 5.2+ """

flat_tab_base_style = ""
flat_tab_big_style = ""
flat_tab_small_style = ""
flat_main_window_style = ""
flat_tool_button_style = ""
flat_push_button_style = ""
flat_dock_style = ""
flat_toolbar_style = ""
flat_menu_bar_style = ""
flat_combo_box_style = ""
flat_toolbox_style = ""
flat_status_bar_style = ""
flat_tree_view_style = ""
flat_overview_docker_style = ""
flat_scroll_style = ""
flat_slider_style = ""
flat_spinbox_style = ""


def buildFlatTheme():
    """
    Build the flat Photoshop-style theme stylesheets.
    Updated for Krita 5.2+ compatibility with modern Qt stylesheets.
    """
    global flat_tab_base_style
    global flat_tab_big_style
    global flat_tab_small_style
    global flat_main_window_style
    global flat_button_style
    global flat_dock_style
    global flat_toolbar_style
    global flat_menu_bar_style
    global flat_combo_box_style
    global flat_toolbox_style
    global flat_status_bar_style
    global flat_tree_view_style
    global flat_overview_docker_style
    global flat_scroll_style
    global flat_slider_style
    global flat_spinbox_style

    # Overview Docker - flat appearance
    flat_overview_docker_style = f"""
        QWidget#OverviewDocker {{
            background: #{ps_bg_dark};
            border: none;
        }}
        
        QWidget#OverviewDocker * {{
            background: #{ps_bg_dark};
        }}

        QWidget#OverviewDocker QSpinBox {{
            border: none;
            background-color: #{ps_bg_medium};
            border-radius: 3px;
            padding: 2px 4px;
            color: #{ps_text};
        }}
        
        QWidget#OverviewDocker QSpinBox:focus {{
            border: 1px solid #{ps_accent};
        }}
    """

    # Tab styling - Photoshop-like flat tabs
    flat_tab_base_style = f"""
        QTabWidget::pane {{
            border: none;
            background: #{ps_bg_dark};
        }}

        QTabBar {{
            background-color: #{ps_bg_medium};
            border: none;
            qproperty-drawBase: 0;
        }}

        QTabBar::tab {{
            background: #{ps_bg_medium};
            color: #{ps_text_dim};
            border: none;
            border-top: 2px solid #{ps_separator};
            padding: 6px 12px;
            margin: 0px;
        }}

        QTabBar::tab:selected {{
            background: #{ps_bg_dark};
            color: #{ps_text};
            border-top: 2px solid #{ps_separator};
        }}

        QTabBar::tab:!selected {{
            background: #{ps_bg_medium};
            color: #{ps_text_dim};
            border-top: 2px solid #{ps_separator};
            margin-top: 0px;
        }}

        QTabBar::tab:hover:!selected {{
            background: #{ps_bg_light};
            color: #{ps_text};
            border-top: 2px solid #{ps_separator};
        }}

        QTabBar::close-button {{
            image: url(:/16_light_tab-close.svg);
            subcontrol-position: right;
        }}

        QTabBar::close-button:hover {{
            background: #{ps_bg_light};
            border-radius: 2px;
        }}

        /* Exclude QMdiArea's native QTabBar (direct child only, not SplitTabs) */
        QMdiArea > QTabBar {{
            min-height: 0px;
            max-height: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}

        QMdiArea > QTabBar::tab {{
            min-height: 0px;
            max-height: 0px;
            min-width: 0px;
            max-width: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}

        /* SplitTabs styling for krita_ui_tweaks integration */
        /* Top separator line to distinguish tabs from toolbar/menubar */
        QMdiArea SplitTabs::tab {{
            border-top: 2px solid #{ps_separator};
        }}

        QMdiArea SplitTabs::tab:selected {{
            border-top: 2px solid #{ps_separator};
        }}

        QMdiArea SplitTabs::tab:hover {{
            border-top: 2px solid #{ps_separator};
        }}

        QMdiArea SplitTabs[class="active"]::tab:selected {{
            border-top: 2px solid #{ps_separator};
        }}
    """
    
    flat_tab_big_style = f"""
        QTabBar::tab {{
            border-top-right-radius: 0px;
            border-top-left-radius: 0px;
            border-top: 2px solid #{ps_separator};
            padding: 8px 16px;
            min-width: 80px;
        }}

        /* Exclude QMdiArea's native QTabBar (direct child only, not SplitTabs) */
        QMdiArea > QTabBar {{
            min-height: 0px;
            max-height: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}

        QMdiArea > QTabBar::tab {{
            min-height: 0px;
            max-height: 0px;
            min-width: 0px;
            max-width: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}
    """
    
    flat_tab_small_style = f"""
        QTabBar::tab {{
            border-top-right-radius: 0px;
            border-top-left-radius: 0px;
            border-top: 2px solid #{ps_separator};
            height: {small_tab_size}px;
            padding: 4px 10px;
        }}

        /* Exclude QMdiArea's native QTabBar (direct child only, not SplitTabs) */
        QMdiArea > QTabBar {{
            min-height: 0px;
            max-height: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}

        QMdiArea > QTabBar::tab {{
            min-height: 0px;
            max-height: 0px;
            min-width: 0px;
            max-width: 0px;
            padding: 0px;
            margin: 0px;
            border: none;
        }}
    """

    # Main window styling - Photoshop dark theme
    flat_main_window_style = f"""
        QMainWindow {{
            background: #{ps_bg_dark};
        }}
        
        QMainWindow::separator {{
            background: #{ps_separator};
            width: 4px;
            height: 4px;
        }}
        
        QMainWindow::separator:hover {{
            background: #{ps_accent};
        }}

        QHeaderView {{
            background: #{ps_bg_medium};
            border: none;
        }}
        
        QHeaderView::section {{
            background: #{ps_bg_medium};
            color: #{ps_text};
            border: none;
            border-right: 1px solid #{ps_border};
            padding: 4px 8px;
        }}
        
        QHeaderView::section:hover {{
            background: #{ps_bg_light};
        }}
        
        QLineEdit {{
            background: #{ps_bg_medium};
            border: 1px solid #{ps_border};
            border-radius: 3px;
            padding: 4px 8px;
            color: #{ps_text};
            selection-background-color: #{ps_accent};
        }}
        
        QLineEdit:focus {{
            border: 1px solid #{ps_accent};
        }}

        QStatusBar {{
            background: #{ps_bg_medium};
            border-top: 1px solid #{ps_border};
        }}
        
        QStatusBar > * {{
            border: none;
        }}
        
        QStatusBar::item {{
            border: none;
        }}

        /* Krita-specific slider spinbox */
        KisSliderSpinBox, KisDoubleSliderSpinBox {{
            background: #{ps_bg_medium};
            border: none;
            border-radius: 3px;
            color: #{ps_text};
            selection-background-color: #{ps_bg_medium};
        }}
        
        KisSliderSpinBox:hover, KisDoubleSliderSpinBox:hover {{
            background: #{ps_bg_light};
        }}
        
        /* Tooltip styling */
        QToolTip {{
            background: #{ps_bg_medium};
            color: #{ps_text};
            border: 1px solid #{ps_border};
            padding: 4px;
        }}
        
        /* Splitter handle */
        QSplitter::handle {{
            background: #{ps_border};
        }}
        
        QSplitter::handle:hover {{
            background: #{ps_accent};
        }}
    """

    # Button styling - flat Photoshop-style
    flat_button_style = f"""
        QAbstractButton:hover {{
            background: #{ps_bg_light};
        }}
        
        QAbstractButton:pressed {{
            background: #{ps_accent};
        }}

        QAbstractButton:checked {{
            background: #{ps_accent};
            color: white;
        }}
        
        QAbstractButton:disabled {{
            background: #{ps_bg_dark};
            color: #{ps_text_dim};
        }}

        QAbstractButton[popupMode="1"] {{
            padding-right: 16px;
        }}

        QPushButton {{
            background: #{ps_bg_medium};
            border: 1px solid #{ps_border};
            border-radius: 3px;
            padding: 5px 12px;
            color: #{ps_text};
        }}
        
        QPushButton:hover {{
            background: #{ps_bg_light};
            border-color: #{ps_accent};
        }}
        
        QPushButton:pressed {{
            background: #{ps_accent};
        }}
        
        QPushButton:default {{
            border-color: #{ps_accent};
        }}
        
        QToolButton {{
            background: transparent;
            border: none;
            border-radius: 3px;
            padding: 3px;
        }}
        
        QToolButton:hover {{
            background: #{ps_bg_light};
        }}
        
        QToolButton:pressed {{
            background: #{ps_accent};
        }}
        
        QToolButton:checked {{
            background: #{ps_accent};
        }}
        
        QToolButton[popupMode="1"] {{
            padding-right: 14px;
        }}
        
        QToolButton::menu-button {{
            border: none;
            width: 12px;
        }}
    """

    # Dock widget styling - Photoshop-like panels with separator lines
    flat_dock_style = f""" 
        QDockWidget {{
            background: #{ps_bg_dark};
            titlebar-close-icon: url(:/16_light_tab-close.svg);
            titlebar-normal-icon: url(:/16_light_tab-close.svg);
            border: 4px solid #{ps_separator};
        }}

        QDockWidget::title {{
            background: #{ps_bg_toolbar};
            border-bottom: 4px solid #{ps_separator};
            padding: 6px 8px;
            text-align: left;
            color: #{ps_text};
        }}

        QDockWidget::close-button, QDockWidget::float-button {{
            border: none;
            background: transparent;
            padding: 2px;
        }}
        
        QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
            background: #{ps_bg_light};
            border-radius: 2px;
        }}

        QDockWidget > QWidget {{
            background: #{ps_bg_dark};
            border: none;
        }}
        
        /* Scroll areas in dockers */
        QAbstractScrollArea {{
            background: #{ps_bg_dark};
            border: none;
        }}
        
        QScrollArea {{
            background: #{ps_bg_dark};
            border: none;
        }}
    """

    # Toolbar styling - flat with separator borders, no padding
    flat_toolbar_style = f"""
        QToolBar {{
            background: #{ps_bg_toolbar};
            border: 4px solid #{ps_separator};
            spacing: 4px;
            padding: 0px;
        }}

        QToolBar::handle {{
            background: #{ps_bg_light};
            width: 6px;
            margin: 2px;
            border-radius: 2px;
        }}

        QToolBar::separator {{
            background: #{ps_separator};
            width: 4px;
            margin: 4px 2px;
        }}
    """

    # Menu bar styling - flat dark with separator border, no padding
    flat_menu_bar_style = f"""
        QMenuBar {{
            background: #{ps_bg_toolbar};
            color: #{ps_text};
            border-bottom: 2px solid #{ps_separator};
            padding: 0px;
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 4px 8px;
            border-radius: 2px;
        }}

        QMenuBar::item:selected {{
            background: #{ps_bg_light};
        }}

        QMenuBar::item:pressed {{
            background: #{ps_accent};
        }}

        QMenu {{
            background: #{ps_bg_medium};
            border: 2px solid #{ps_separator};
            padding: 4px 0px;
        }}

        QMenu::item {{
            background: transparent;
            padding: 6px 24px 6px 8px;
            color: #{ps_text};
        }}

        QMenu::item:selected {{
            background: #{ps_accent};
            color: white;
        }}

        QMenu::item:disabled {{
            color: #{ps_text_dim};
        }}

        QMenu::separator {{
            height: 1px;
            background: #{ps_border};
            margin: 4px 8px;
        }}

        QMenu::indicator {{
            width: 16px;
            height: 16px;
            margin-left: 4px;
        }}
    """

    # Combo box styling - flat with bottom accent
    flat_combo_box_style = f"""
        QComboBox {{
            background: #{ps_bg_medium};
            border: 1px solid #{ps_border};
            border-radius: 3px;
            padding: 4px 8px;
            color: #{ps_text};
        }}
        
        /* Shorten KisCompositeOpComboBox (brush composite toolbar action) by 40px - only in toolbars */
        QToolBar KisCompositeOpComboBox {{
            max-width: 120px;
        }}

        QComboBox:hover {{
            border-color: #{ps_accent};
        }}
        
        QComboBox:focus {{
            border-color: #{ps_accent};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
            subcontrol-origin: padding;
            subcontrol-position: right center;
        }}
        
        QComboBox::down-arrow {{
            image: url(:/16_light_draw-arrow-down.svg);
            width: 12px;
            height: 12px;
        }}
        
        QComboBox QAbstractItemView {{
            background: #{ps_bg_medium};
            border: 1px solid #{ps_border};
            selection-background-color: #{ps_accent};
            selection-color: white;
            outline: none;
        }}
        
        QComboBox QAbstractItemView::item {{
            padding: 4px 8px;
            min-height: 24px;
        }}
        
        QComboBox QAbstractItemView::item:hover {{
            background: #{ps_bg_light};
        }}
    """

    flat_toolbox_style = f"""
        QWidget#ToolBox QToolButton {{
            border: none;
            background: transparent;
            border-radius: 3px;
            padding: 4px;
        }}
        
        QWidget#ToolBox QToolButton:hover {{
            background: #{ps_bg_light};
        }}
        
        QWidget#ToolBox QToolButton:checked {{
            background: #{ps_accent};
        }}
    """

    flat_status_bar_style = f"""
        QStatusBar {{ 
            background: #{ps_bg_medium}; 
            border-top: 2px solid #{ps_separator};
            color: #{ps_text};
        }}
        
        QStatusBar QLabel {{
            color: #{ps_text};
            padding: 2px 4px;
        }}
    """

    flat_tree_view_style = f"""
        QTreeView, QListView, QTableView {{
            background: #{ps_bg_dark}; 
            border: none;
            outline: none;
            color: #{ps_text};
            alternate-background-color: #{ps_bg_medium};
        }}
        
        QTreeView::item, QListView::item, QTableView::item {{
            padding: 4px;
            border: none;
        }}
        
        QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {{
            background: #{ps_bg_light};
        }}
        
        QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{
            background: #{ps_accent};
            color: white;
        }}
        
        QTreeView::branch {{
            background: #{ps_bg_dark};
        }}
        
        QTreeView::branch:hover {{
            background: #{ps_bg_light};
        }}
        
        QTreeView::branch:selected {{
            background: #{ps_accent};
        }}
    """

    # Scrollbar styling - thin and modern
    flat_scroll_style = f"""
        QScrollBar:vertical {{
            background: #{ps_bg_dark};
            width: 10px;
            margin: 0px;
            border: none;
        }}
        
        QScrollBar::handle:vertical {{
            background: #{ps_bg_light};
            min-height: 30px;
            border-radius: 4px;
            margin: 2px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: #{ps_text_dim};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        
        QScrollBar:horizontal {{
            background: #{ps_bg_dark};
            height: 10px;
            margin: 0px;
            border: none;
        }}
        
        QScrollBar::handle:horizontal {{
            background: #{ps_bg_light};
            min-width: 30px;
            border-radius: 4px;
            margin: 2px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background: #{ps_text_dim};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """

    # Slider styling
    flat_slider_style = f"""
        QSlider::groove:horizontal {{
            background: #{ps_bg_medium};
            height: 4px;
            border-radius: 2px;
        }}
        
        QSlider::handle:horizontal {{
            background: #{ps_text};
            width: 12px;
            height: 12px;
            margin: -4px 0;
            border-radius: 6px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background: #{ps_accent};
        }}
        
        QSlider::sub-page:horizontal {{
            background: #{ps_bg_medium};
            height: 4px;
            border-radius: 2px;
        }}
        
        QSlider::groove:vertical {{
            background: #{ps_bg_medium};
            width: 4px;
            border-radius: 2px;
        }}
        
        QSlider::sub-page:vertical {{
            background: #{ps_bg_medium};
            width: 4px;
            border-radius: 2px;
        }}
        
        QSlider::handle:vertical {{
            background: #{ps_text};
            width: 12px;
            height: 12px;
            margin: 0 -4px;
            border-radius: 6px;
        }}
        
        QSlider::handle:vertical:hover {{
            background: #{ps_accent};
        }}
    """

    # Spinbox styling - scoped to avoid interference with tabs
    flat_spinbox_style = f"""
        QSpinBox, QDoubleSpinBox {{
            background: #{ps_bg_medium};
            border: 5px solid #{ps_border};
            border-radius: 3px;
            padding: 2px 4px;
            color: #{ps_text};
        }}
        
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: #{ps_accent};
        }}
        
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            margin-bottom: -3px;
            margin-right: -3px;
            width: 13px;
            border: 3px solid #{ps_border};
            background: #{ps_border};
            image: url(:/16_light_draw-arrow-up.svg);
        }}
        
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            margin-top: -3px;
            margin-right: -3px;
            width: 13px;
            border: 3px solid #{ps_border};
            background: #{ps_border};
            image: url(:/16_light_draw-arrow-down.svg);
        }}
        
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background: #{ps_bg_light};
        }}

        /* Toolbar spinboxes: reduce vertical padding without changing font size */
        QToolBar QDoubleSpinBox,
        QToolBar KisDoubleSliderSpinBox,
        QToolBar KisSliderSpinBox {{
            padding-top: 6px;
            padding-bottom: 6px;
        }}

    """
