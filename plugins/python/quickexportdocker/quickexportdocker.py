# Quick Export Plugin for Krita
# Based on Quick Export Layers Docker by fullmontis (public domain)

from PyQt5.QtCore import Qt, QRect, QUrl, QTimer
from PyQt5.QtWidgets import (QWidget, QLineEdit, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QCheckBox, 
                             QComboBox, QFileDialog, QLabel, QFrame,
                             QSizePolicy, QGridLayout, QSpinBox, QMessageBox)
from PyQt5.QtGui import QPalette, QColor, QDesktopServices
import krita
import os


class FormatRow(QWidget):
    """A single format row with width, height, format dropdown, and transparency button"""
    
    def __init__(self, parent_docker, initial_width=1920, initial_height=1080):
        super().__init__()
        self.parent_docker = parent_docker
        self.original_width = initial_width
        self.original_height = initial_height
        self.aspect_ratio = initial_width / initial_height if initial_height > 0 else 1.0
        self._updating = False  # Prevent recursive updates
        
        self.setupUI()
        
    def setupUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        
        # Width input
        self.widthInput = QLineEdit()
        self.widthInput.setFixedWidth(60)
        self.widthInput.setPlaceholderText("Width")
        self.widthInput.setText(f"{self.original_width}")
        self.widthInput.editingFinished.connect(self.onWidthChanged)
        layout.addWidget(self.widthInput)
        
        # Height input
        self.heightInput = QLineEdit()
        self.heightInput.setFixedWidth(60)
        self.heightInput.setPlaceholderText("Height")
        self.heightInput.setText(f"{self.original_height}")
        self.heightInput.editingFinished.connect(self.onHeightChanged)
        layout.addWidget(self.heightInput)
        
        # Format combo box
        self.formatComboBox = QComboBox()
        self.formatComboBox.addItem(i18n("PNG"))
        self.formatComboBox.addItem(i18n("JPEG"))
        self.formatComboBox.addItem(i18n("JPEG-XL"))
        self.formatComboBox.addItem(i18n("KRA"))
        self.formatComboBox.addItem(i18n("PSD"))
        self.formatComboBox.currentIndexChanged.connect(self.onFormatChanged)
        self.formatComboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.formatComboBox)
        
        # Transparency button (icon only, overlayed on the format dropdown)
        self.transparencyButton = QPushButton()
        self.transparencyButton.setObjectName("transparencyBtn")
        self.transparencyButton.setCheckable(True)
        self.transparencyButton.setChecked(True)
        self.transparencyButton.setToolTip(i18n("Toggle alpha channel (transparency) for PNG export"))
        self.transparencyButton.setFixedSize(24, 24)
        # Use Krita's icon library for selection-mode_invisible icon
        self.transparencyButton.setIcon(Application.icon("selection-mode_invisible"))
        layout.addWidget(self.transparencyButton)
        
        # Remove button
        self.removeButton = QPushButton()
        self.removeButton.setIcon(Application.icon("deletelayer"))
        self.removeButton.setFixedSize(24, 24)
        self.removeButton.setToolTip(i18n("Remove this format"))
        self.removeButton.clicked.connect(self.onRemoveClicked)
        layout.addWidget(self.removeButton)
        
        self.setLayout(layout)
        
        # Initial format state
        self.onFormatChanged(0)
        
    def onWidthChanged(self):
        """Handle width change, maintain aspect ratio"""
        if self._updating:
            return
        try:
            new_width = int(self.widthInput.text())
            if new_width > 0:
                self._updating = True
                new_height = int(round(new_width / self.aspect_ratio))
                self.heightInput.setText(str(new_height))
                self._updating = False
        except ValueError:
            pass
            
    def onHeightChanged(self):
        """Handle height change, maintain aspect ratio"""
        if self._updating:
            return
        try:
            new_height = int(self.heightInput.text())
            if new_height > 0:
                self._updating = True
                new_width = int(round(new_height * self.aspect_ratio))
                self.widthInput.setText(str(new_width))
                self._updating = False
        except ValueError:
            pass
            
    def onFormatChanged(self, index):
        """Show/hide transparency button based on format"""
        formatText = self.formatComboBox.currentText().upper()
        self.transparencyButton.setVisible(formatText == "PNG")
        
    def onRemoveClicked(self):
        """Remove this format row"""
        self.parent_docker.removeFormatRow(self)
        
    def updateFromDocument(self, width, height):
        """Update dimensions from current document"""
        self.original_width = width
        self.original_height = height
        self.aspect_ratio = width / height if height > 0 else 1.0
        self.widthInput.setText(str(width))
        self.heightInput.setText(str(height))
        
    def getExportSettings(self):
        """Get export settings for this format row"""
        try:
            width = int(self.widthInput.text())
            height = int(self.heightInput.text())
        except ValueError:
            width = self.original_width
            height = self.original_height
            
        return {
            'width': width,
            'height': height,
            'format': self.formatComboBox.currentText(),
            'transparency': self.transparencyButton.isChecked()
        }
        
    def getFormatIndex(self):
        return self.formatComboBox.currentIndex()
        
    def setFormatIndex(self, index):
        if index < self.formatComboBox.count():
            self.formatComboBox.setCurrentIndex(index)
            
    def isTransparencyChecked(self):
        return self.transparencyButton.isChecked()
        
    def setTransparencyChecked(self, checked):
        self.transparencyButton.setChecked(checked)


class QuickExportDocker(krita.DockWidget):
    """Quick Export Docker - A streamlined export panel for Krita"""
    
    # Photoshop-style desaturated color palette
    STYLE_SHEET = """
        QWidget {
            background-color: #4d4d4d;
            color: #cccccc;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 11px;
        }
        QLineEdit {
            background-color: #424242;
            border: 1px solid #5a5a5a;
            border-radius: 2px;
            padding: 4px 6px;
            color: #e0e0e0;
            selection-background-color: #6a6a6a;
        }
        QLineEdit:focus {
            border: 1px solid #888888;
        }
        QLineEdit:disabled {
            background-color: #454545;
            color: #888888;
        }
        QPushButton {
            background-color: #424242;
            border: 1px solid #5a5a5a;
            border-radius: 2px;
            padding: 5px 12px;
            color: #e0e0e0;
            min-height: 18px;
        }
        QPushButton:hover {
            background-color: #5a5a5a;
            border: 1px solid #6a6a6a;
        }
        QPushButton:pressed {
            background-color: #424242;
        }
        QPushButton:checked {
            background-color: #666666;
            border: 1px solid #888888;
        }
        QPushButton#exportBtn {
            background-color: #5a5a5a;
            font-weight: bold;
            padding: 6px 20px;
        }
        QPushButton#exportBtn:hover {
            background-color: #6a6a6a;
        }
        QPushButton#transparencyBtn {
            padding: 2px;
            min-width: 20px;
            max-width: 24px;
            border: 1px solid #5a5a5a;
            background-color: #424242;
        }
        QPushButton#transparencyBtn:checked {
            background-color: #707070;
            border: 1px solid #888888;
        }
        QPushButton#transparencyBtn:hover {
            background-color: #5a5a5a;
        }
        QPushButton#addFormatBtn {
            background-color: #424242;
            border: 1px solid #5a5a5a;
            padding: 5px 12px;
            min-height: 18px;
        }
        QPushButton#addFormatBtn:hover {
            background-color: #5a5a5a;
            border: 1px solid #5a5a5a;
        }
        QComboBox {
            background-color: #424242;
            border: 1px solid #5a5a5a;
            border-radius: 2px;
            padding: 4px 8px;
            color: #e0e0e0;
            min-width: 80px;
        }
        QComboBox:hover {
            border: 1px solid #6a6a6a;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #aaaaaa;
            margin-right: 6px;
        }
        QComboBox QAbstractItemView {
            background-color: #424242;
            border: 1px solid #5a5a5a;
            selection-background-color: #5a5a5a;
            color: #e0e0e0;
        }
        QLabel {
            color: #cccccc;
            background: transparent;
        }
        QLabel#statusLabel {
            color: #aaaaaa;
            font-size: 10px;
            padding: 2px;
        }
        QLabel#sectionLabel {
            color: #999999;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            padding-top: 4px;
        }
        QFrame#separator {
            background-color: #424242;
            max-height: 1px;
        }
    """

    def __init__(self):
        super(QuickExportDocker, self).__init__()
        
        # State tracking
        self._isExporting = False
        self._userEditedFilename = False
        self._lastDocumentName = ""
        self._formatRows = []  # List of FormatRow widgets
        
        self.setupUI()
        self.loadDefaults()
        
    def setupUI(self):
        """Initialize the user interface"""
        widget = QWidget()
        widget.setStyleSheet(self.STYLE_SHEET)
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        widget.setLayout(layout)
        self.setWindowTitle(i18n("Quick Export"))
        
        # === EXPORT DIRECTORY SECTION ===
        dirLabel = QLabel(i18n("Export Directory"))
        dirLabel.setObjectName("sectionLabel")
        layout.addWidget(dirLabel)
        
        dirLayout = QHBoxLayout()
        dirLayout.setSpacing(4)
        self.directoryTextField = QLineEdit()
        self.directoryTextField.setPlaceholderText(i18n("Select export folder..."))
        self.directoryDialogButton = QPushButton(i18n("Browse..."))
        self.directoryDialogButton.setMaximumWidth(70)
        self.directoryDialogButton.setFixedHeight(24)
        self.directoryOpenButton = QPushButton()
        self.directoryOpenButton.setIcon(Application.icon("folder"))
        # Fixed width for the folder button lives here.
        self.directoryOpenButton.setFixedSize(32, 24)
        self.directoryOpenButton.setToolTip(i18n("Open export folder"))
        dirLayout.addWidget(self.directoryTextField, 1, Qt.AlignVCenter)
        dirLayout.addWidget(self.directoryDialogButton, 0, Qt.AlignVCenter)
        dirLayout.addWidget(self.directoryOpenButton, 0, Qt.AlignVCenter)
        self.directoryTextField.setText(os.path.expanduser("~"))
        self.directoryDialogButton.clicked.connect(self.selectDir)
        self.directoryOpenButton.clicked.connect(self.openExportDirectory)
        layout.addLayout(dirLayout)
        
        # Separator
        self.addSeparator(layout)
        
        # === FILENAME SECTION ===
        filenameLabel = QLabel(i18n("File Name"))
        filenameLabel.setObjectName("sectionLabel")
        layout.addWidget(filenameLabel)
        
        self.filenameTextField = QLineEdit()
        self.filenameTextField.setPlaceholderText(i18n("Enter export filename..."))
        self.filenameTextField.textEdited.connect(self.onFilenameEdited)
        layout.addWidget(self.filenameTextField)
        
        # === FORMAT SECTION ===
        # Column headers
        formatHeaderLayout = QHBoxLayout()
        formatHeaderLayout.setSpacing(4)
        
        widthLabel = QLabel(i18n("WIDTH"))
        widthLabel.setObjectName("sectionLabel")
        widthLabel.setFixedWidth(60)
        widthLabel.setAlignment(Qt.AlignLeft)
        formatHeaderLayout.addWidget(widthLabel)
        
        heightLabel = QLabel(i18n("HEIGHT"))
        heightLabel.setObjectName("sectionLabel")
        heightLabel.setFixedWidth(60)
        heightLabel.setAlignment(Qt.AlignLeft)
        formatHeaderLayout.addWidget(heightLabel)
        
        formatLabel = QLabel(i18n("FORMAT"))
        formatLabel.setObjectName("sectionLabel")
        formatLabel.setAlignment(Qt.AlignLeft)
        formatHeaderLayout.addWidget(formatLabel)
        
        formatHeaderLayout.addStretch()
        layout.addLayout(formatHeaderLayout)
        
        # Container for format rows
        self.formatRowsContainer = QVBoxLayout()
        self.formatRowsContainer.setSpacing(2)
        layout.addLayout(self.formatRowsContainer)
        
        # Add initial format row
        self.addFormatRow()
        
        # Add Format button
        addFormatLayout = QHBoxLayout()
        self.addFormatButton = QPushButton()
        self.addFormatButton.setObjectName("addFormatBtn")
        self.addFormatButton.setIcon(Application.icon("addlayer"))
        self.addFormatButton.setText(i18n("Add Format"))
        self.addFormatButton.clicked.connect(self.addFormatRow)
        self.addFormatButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        addFormatLayout.addWidget(self.addFormatButton)
        layout.addLayout(addFormatLayout)
        
        # Separator
        self.addSeparator(layout)
        
        # === OPTIONS SECTION ===
        optionsLabel = QLabel(i18n("Options"))
        optionsLabel.setObjectName("sectionLabel")
        layout.addWidget(optionsLabel)
        
        self.batchmodeCheckBox = QCheckBox(i18n("Skip export dialog"))
        self.batchmodeCheckBox.setChecked(True)
        self.batchmodeCheckBox.setToolTip(i18n("Export directly without showing format options"))
        layout.addWidget(self.batchmodeCheckBox)
        
        self.exportOnlySelectedCheckBox = QCheckBox(i18n("Export only selected layer"))
        self.exportOnlySelectedCheckBox.setToolTip(i18n("Export only the currently selected layer"))
        layout.addWidget(self.exportOnlySelectedCheckBox)
        
        self.createFileDirectoryCheckBox = QCheckBox(i18n("Create subfolder with filename"))
        self.createFileDirectoryCheckBox.setToolTip(i18n("Create a subfolder named after the export file"))
        layout.addWidget(self.createFileDirectoryCheckBox)
        
        # Multi-layer export options
        self.exportLayersSeparatelyCheckBox = QCheckBox(i18n("Export layers separately"))
        self.exportLayersSeparatelyCheckBox.setToolTip(i18n("Export each layer as a separate file"))
        self.exportLayersSeparatelyCheckBox.stateChanged.connect(self.toggleExportLayersSeparately)
        layout.addWidget(self.exportLayersSeparatelyCheckBox)
        
        # Indented sub-options for layer export
        layerOptionsLayout = QVBoxLayout()
        layerOptionsLayout.setContentsMargins(16, 0, 0, 0)
        layerOptionsLayout.setSpacing(2)
        
        self.groupAsLayerCheckBox = QCheckBox(i18n("Treat groups as single layers"))
        self.groupAsLayerCheckBox.setChecked(True)
        self.groupAsLayerCheckBox.setVisible(False)
        layerOptionsLayout.addWidget(self.groupAsLayerCheckBox)
        
        self.ignoreFilterLayersCheckBox = QCheckBox(i18n("Ignore filter layers"))
        self.ignoreFilterLayersCheckBox.setChecked(True)
        self.ignoreFilterLayersCheckBox.setVisible(False)
        layerOptionsLayout.addWidget(self.ignoreFilterLayersCheckBox)
        
        self.ignoreInvisibleLayersCheckBox = QCheckBox(i18n("Ignore invisible layers"))
        self.ignoreInvisibleLayersCheckBox.setChecked(True)
        self.ignoreInvisibleLayersCheckBox.setVisible(False)
        layerOptionsLayout.addWidget(self.ignoreInvisibleLayersCheckBox)
        
        layout.addLayout(layerOptionsLayout)
        
        # Separator
        self.addSeparator(layout)
        
        # === EXPORT BUTTON ===
        exportLayout = QHBoxLayout()
        
        self.saveDefaultsButton = QPushButton(i18n("Save Defaults"))
        self.saveDefaultsButton.setToolTip(i18n("Save current settings as defaults"))
        self.saveDefaultsButton.clicked.connect(self.saveDefaults)
        exportLayout.addWidget(self.saveDefaultsButton)
        
        exportLayout.addStretch()
        
        self.exportButton = QPushButton(i18n("Export"))
        self.exportButton.setObjectName("exportBtn")
        self.exportButton.clicked.connect(self.exportAction)
        exportLayout.addWidget(self.exportButton)
        
        layout.addLayout(exportLayout)
        
        # Status message
        self.exportMessage = QLabel("")
        self.exportMessage.setObjectName("statusLabel")
        self.exportMessage.setWordWrap(True)
        layout.addWidget(self.exportMessage)

        # Add stretch to push everything up
        layout.addStretch()
        
        self.setWidget(widget)
        
        # Update format rows with current document dimensions
        self.updateFormatRowsFromDocument()
        
    def addFormatRow(self):
        """Add a new format row"""
        # Get current document dimensions
        document = Application.activeDocument()
        if document:
            width = document.width()
            height = document.height()
        else:
            width = 1920
            height = 1080
            
        formatRow = FormatRow(self, width, height)
        self._formatRows.append(formatRow)
        self.formatRowsContainer.addWidget(formatRow)
        
        # Update remove button visibility
        self.updateRemoveButtonVisibility()
        
    def removeFormatRow(self, formatRow):
        """Remove a format row"""
        if formatRow in self._formatRows:
            self._formatRows.remove(formatRow)
            self.formatRowsContainer.removeWidget(formatRow)
            formatRow.deleteLater()
            
        # Update remove button visibility
        self.updateRemoveButtonVisibility()
        self.adjustDockToContents()
        
    def updateRemoveButtonVisibility(self):
        """Hide remove button if only one format row exists"""
        for row in self._formatRows:
            row.removeButton.setVisible(len(self._formatRows) > 1)
            
    def updateFormatRowsFromDocument(self):
        """Update all format rows with current document dimensions"""
        document = Application.activeDocument()
        if document:
            width = document.width()
            height = document.height()
            for row in self._formatRows:
                row.updateFromDocument(width, height)
        
    def addSeparator(self, layout):
        """Add a horizontal separator line"""
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        layout.addWidget(separator)
        layout.addSpacing(4)
        
    def canvasChanged(self, canvas):
        """Called when the canvas changes - update filename and dimensions if not user-edited"""
        if not self._userEditedFilename and not self._isExporting:
            self.updateFilenameFromDocument()
        # Update format rows with new document dimensions
        self.updateFormatRowsFromDocument()
            
    def updateFilenameFromDocument(self):
        """Auto-fill filename from current document"""
        document = Application.activeDocument()
        if document:
            documentNameWithExt = "Untitled"
            if document.fileName():
                documentNameWithExt = document.fileName()
            documentName, _ = os.path.splitext(os.path.basename(documentNameWithExt))
            
            if documentName != self._lastDocumentName:
                self._lastDocumentName = documentName
                self.filenameTextField.setText(documentName)
                self._userEditedFilename = False
                
    def onFilenameEdited(self, text):
        """Called when user manually edits the filename"""
        self._userEditedFilename = True
        
    def showEvent(self, event):
        """Called when the docker becomes visible"""
        super().showEvent(event)
        if not self._userEditedFilename:
            self.updateFilenameFromDocument()
            
    def focusInEvent(self, event):
        """Called when the docker gains focus"""
        super().focusInEvent(event)
        # Don't auto-update if user has edited
        
    def focusOutEvent(self, event):
        """Called when the docker loses focus - can auto-update filename"""
        super().focusOutEvent(event)
        if not self._userEditedFilename and not self._isExporting:
            self.updateFilenameFromDocument()

    # Path escaping utilities for saving/loading settings
    def escapePath(self, path):
        path_escaped = path.encode("unicode_escape").decode("ascii")
        comma_encoded = "\\x" + hex(ord(","))[2:]
        return path_escaped.replace(",", comma_encoded)

    def decodePath(self, path):
        return path.encode("ascii").decode("unicode_escape")

    def saveDefaults(self):
        """Save current settings as defaults"""
        directory = self.escapePath(self.directoryTextField.text())
        batchmode = str(int(self.batchmodeCheckBox.isChecked()))
        exportOnlySelected = str(int(self.exportOnlySelectedCheckBox.isChecked()))
        exportLayersSeparately = str(int(self.exportLayersSeparatelyCheckBox.isChecked()))
        createFileDirectory = str(int(self.createFileDirectoryCheckBox.isChecked()))
        ignoreFilterLayers = str(int(self.ignoreFilterLayersCheckBox.isChecked()))
        groupAsLayer = str(int(self.groupAsLayerCheckBox.isChecked()))
        ignoreInvisibleLayers = str(int(self.ignoreInvisibleLayersCheckBox.isChecked()))
        
        # Save first format row settings for backwards compatibility
        formatDefault = "0"
        transparency = "1"
        if self._formatRows:
            formatDefault = str(self._formatRows[0].getFormatIndex())
            transparency = str(int(self._formatRows[0].isTransparencyChecked()))

        defaults = ",".join([directory, batchmode, exportOnlySelected, exportLayersSeparately, 
                             createFileDirectory, ignoreFilterLayers, 
                             groupAsLayer, ignoreInvisibleLayers, 
                             formatDefault, transparency])
        
        Application.writeSetting("", "quick_export_docker", defaults)
        self.exportMessage.setText(i18n("Settings saved."))

    def loadDefaults(self):
        """Load saved default settings"""
        defaults = Application.readSetting("", "quick_export_docker", "")
        if defaults == "":
            self.updateFilenameFromDocument()
            return
        
        try:
            defaults = defaults.split(",")
            if len(defaults) >= 9:
                [directory, batchmode, exportOnlySelected, exportLayersSeparately, 
                 createFileDirectory, groupAsLayer, ignoreFilterLayers, 
                 ignoreInvisibleLayers, formatDefault] = defaults[:9]

                self.directoryTextField.setText(self.decodePath(directory))
                self.batchmodeCheckBox.setChecked(bool(int(batchmode)))
                self.exportOnlySelectedCheckBox.setChecked(bool(int(exportOnlySelected)))
                self.exportLayersSeparatelyCheckBox.setChecked(bool(int(exportLayersSeparately)))
                self.createFileDirectoryCheckBox.setChecked(bool(int(createFileDirectory)))
                self.groupAsLayerCheckBox.setChecked(bool(int(groupAsLayer)))
                self.ignoreFilterLayersCheckBox.setChecked(bool(int(ignoreFilterLayers)))
                self.ignoreInvisibleLayersCheckBox.setChecked(bool(int(ignoreInvisibleLayers)))
                
                # Apply to first format row
                if self._formatRows:
                    formatIndex = int(formatDefault)
                    self._formatRows[0].setFormatIndex(formatIndex)
                
                    if len(defaults) >= 10:
                        transparency = defaults[9]
                        self._formatRows[0].setTransparencyChecked(bool(int(transparency)))

                self.toggleExportLayersSeparately()
        except Exception as e:
            print(f"Quick Export: Error loading defaults: {e}")
            
        self.updateFilenameFromDocument()

    def selectDir(self):
        """Open directory selection dialog"""
        directory = self.directoryTextField.text()
        if not os.path.isdir(directory):
            directory = os.path.expanduser("~")

        directory = QFileDialog.getExistingDirectory(
            self, i18n("Select Export Folder"), 
            directory, QFileDialog.ShowDirsOnly)
        if directory:
            self.directoryTextField.setText(directory)
            
    def openExportDirectory(self):
        """Open file explorer to the export directory if valid"""
        directory = self.directoryTextField.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.information(
                self,
                i18n("Quick Export"),
                i18n("Not a valid directory")
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    def toggleExportLayersSeparately(self):
        """Show/hide layer export sub-options based on checkbox state"""
        state = self.exportLayersSeparatelyCheckBox.isChecked()
        self.groupAsLayerCheckBox.setVisible(state)
        self.ignoreFilterLayersCheckBox.setVisible(state)
        self.ignoreInvisibleLayersCheckBox.setVisible(state)
        if not state:
            self.adjustDockToContents()

    def adjustDockToContents(self):
        """Shrink the dock to its content after layout changes."""
        QTimer.singleShot(0, self._applyDockResize)

    def _applyDockResize(self):
        content = self.widget()
        if not content:
            return
        content.adjustSize()
        target_height = self.sizeHint().height()
        self.setMinimumHeight(0)
        self.setMaximumHeight(target_height)
        self.resize(self.width(), target_height)
        self.updateGeometry()
        QTimer.singleShot(0, self._releaseDockHeightLimit)

    def _releaseDockHeightLimit(self):
        self.setMaximumHeight(16777215)

    def getExportFilename(self):
        """Get the filename to use for export (user-edited or document name)"""
        filename = self.filenameTextField.text().strip()
        if not filename:
            # Fallback to document name
            document = Application.activeDocument()
            if document and document.fileName():
                filename, _ = os.path.splitext(os.path.basename(document.fileName()))
            else:
                filename = "Untitled"
        return filename

    def getFileExtension(self, format_text):
        """Get the file extension for a format"""
        extensions = {
            "PNG": "png",
            "JPEG": "jpg",
            "JPEG-XL": "jxl",
            "KRA": "kra",
            "PSD": "psd"
        }
        return extensions.get(format_text.upper(), "png")

    def createExportInfoObject(self, file_format, transparency=True):
        """Create InfoObject with format-specific export settings"""
        info = krita.InfoObject()
        formatUpper = file_format.upper()
        
        if formatUpper == "PNG":
            # PNG Settings:
            # - Max compression (9)
            # - Force convert to sRGB enabled
            # - All other options disabled
            # - Transparency based on toggle button
            info.setProperty("compression", 9)
            info.setProperty("indexed", False)
            info.setProperty("interlaced", False)
            info.setProperty("saveSRGBProfile", True)  # Force convert to sRGB
            info.setProperty("forceSRGB", True)
            info.setProperty("alpha", transparency)
            info.setProperty("transparencyFillcolor", [255, 255, 255])  # White fill if no transparency
            
        elif formatUpper in ["JPEG", "JPG"]:
            # JPEG Settings:
            # - Quality: 100%
            # - Subsampling: 2x2, 1x1, 1x1 (smallest file) = 1
            # - Metadata Anonymizer enabled
            info.setProperty("quality", 100)
            info.setProperty("smoothing", 0)
            info.setProperty("subsampling", 1)  # 2x2,1x1,1x1 (smallest)
            info.setProperty("progressive", False)
            info.setProperty("optimize", True)
            info.setProperty("saveProfile", True)
            info.setProperty("transparencyFillcolor", [255, 255, 255])
            info.setProperty("storeMetaData", False)  # Anonymizer - don't store metadata
            info.setProperty("storeAuthor", False)  # Don't store author
            info.setProperty("exif", False)  # No EXIF
            
        elif formatUpper in ["JPEG-XL", "JXL"]:
            # JPEG-XL Settings:
            # - Don't save as animated
            # - Flatten the image
            # - No lossy encoding (lossless)
            # - Effort/Tradeoff: 9 (max)
            # - Decoding speed: 0 (slowest/best quality)
            info.setProperty("lossless", True)  # No lossy encoding
            info.setProperty("effort", 9)  # Max effort/tradeoff
            info.setProperty("decodingSpeed", 0)  # Slowest/best quality
            info.setProperty("flattenImage", True)  # Flatten the image
            info.setProperty("animated", False)  # Don't save as animated
            
        elif formatUpper == "KRA":
            # KRA native format - Krita's native format
            info.setProperty("flattenImage", False)
            
        elif formatUpper == "PSD":
            # PSD format - Photoshop compatibility
            info.setProperty("psdCompression", 1)  # RLE compression
            
        return info

    def exportAction(self):
        """Main export action - exports all format rows"""
        self._isExporting = True
        
        directory = self.directoryTextField.text()
        document = Application.activeDocument()

        self.exportMessage.setText(i18n("Exporting..."))
        
        if not document:
            self.exportMessage.setText(i18n("No document open."))
            self._isExporting = False
            return 
        elif not directory:
            self.exportMessage.setText(i18n("Select an export directory."))
            self._isExporting = False
            return 
        elif not os.path.exists(directory) or not os.path.isdir(directory):
            self.exportMessage.setText(i18n("Export directory doesn't exist."))
            self._isExporting = False
            return
        
        if not self._formatRows:
            self.exportMessage.setText(i18n("No formats to export."))
            self._isExporting = False
            return

        # Get the user-specified filename
        exportName = self.getExportFilename()
        
        exportDir = ""

        baseNode = document.rootNode()

        if self.exportOnlySelectedCheckBox.isChecked():
            baseNode = document.activeNode()
            if baseNode:
                exportName = baseNode.name()

        if self.createFileDirectoryCheckBox.isChecked():
            exportDir = exportName
            self.createDirectory(exportDir)

        Application.setBatchmode(self.batchmodeCheckBox.isChecked())

        exportedFormats = []
        
        # Count format occurrences to detect duplicates
        formatCounts = {}
        for formatRow in self._formatRows:
            settings = formatRow.getExportSettings()
            ext = self.getFileExtension(settings['format'])
            formatCounts[ext] = formatCounts.get(ext, 0) + 1
        
        # Track which formats need unique suffixes
        formatNeedsSuffix = {ext: count > 1 for ext, count in formatCounts.items()}
        
        try:
            # Export each format row
            for formatRow in self._formatRows:
                settings = formatRow.getExportSettings()
                formatText = settings['format']
                fileExtension = self.getFileExtension(formatText)
                targetWidth = settings['width']
                targetHeight = settings['height']
                transparency = settings['transparency']
                
                # Calculate effective PPI based on scale ratio
                originalWidth = document.width()
                originalHeight = document.height()
                originalPPI = int(document.resolution())
                
                # Calculate scale factor and effective PPI
                scaleX = targetWidth / originalWidth if originalWidth > 0 else 1.0
                effectivePPI = int(round(originalPPI * scaleX))
                
                # Create filename with PPI suffix if there are duplicate formats or different resolution
                if formatNeedsSuffix.get(fileExtension, False):
                    sizedExportName = f"{exportName}_{effectivePPI}ppi"
                elif targetWidth != originalWidth or targetHeight != originalHeight:
                    sizedExportName = f"{exportName}_{effectivePPI}ppi"
                else:
                    sizedExportName = exportName
                
                if self.exportLayersSeparatelyCheckBox.isChecked():
                    self.exportLayers(baseNode, exportDir, fileExtension, 
                                     targetWidth, targetHeight, transparency)
                else:
                    self.exportNodeWithScale(baseNode, exportDir, sizedExportName, 
                                            fileExtension, targetWidth, targetHeight, 
                                            transparency)
                
                exportedFormats.append(f"{sizedExportName}.{fileExtension}")
                
            self.exportMessage.setText(i18n(f"Exported: {', '.join(exportedFormats)}"))
        except Exception as e:
            self.exportMessage.setText(i18n(f"Export failed: {str(e)}"))
        finally:
            Application.setBatchmode(True)
            self._isExporting = False

    def exportNodeWithScale(self, node, export_folder, filename, file_format, 
                            target_width, target_height, transparency=True):
        """Export a single node with scaling and format-specific settings"""
        export_file_path = os.path.join(
            self.directoryTextField.text(), 
            export_folder, 
            f"{filename}.{file_format}"
        )

        document = Application.activeDocument()
        originalWidth = document.width()
        originalHeight = document.height()
        
        # Handle native format exports differently
        formatUpper = file_format.upper()
        
        # Check if we need to scale
        needsScaling = (target_width != originalWidth or target_height != originalHeight)
        
        if needsScaling:
            # Clone the document for scaling
            clonedDoc = document.clone()
            clonedDoc.scaleImage(target_width, target_height, 
                                int(clonedDoc.xRes()), int(clonedDoc.yRes()), "Bilinear")
            clonedDoc.refreshProjection()
            clonedDoc.waitForDone()
            
            if formatUpper == "KRA":
                clonedDoc.saveAs(export_file_path)
            elif formatUpper == "PSD":
                info = self.createExportInfoObject(file_format, transparency)
                clonedDoc.exportImage(export_file_path, info)
            else:
                bounds = QRect(0, 0, target_width, target_height)
                info = self.createExportInfoObject(file_format, transparency)
                clonedDoc.rootNode().save(export_file_path,
                                         clonedDoc.resolution() / 72.,
                                         clonedDoc.resolution() / 72.,
                                         info, bounds)
            
            clonedDoc.close()
        else:
            if formatUpper == "KRA":
                document.saveAs(export_file_path)
            elif formatUpper == "PSD":
                info = self.createExportInfoObject(file_format, transparency)
                document.exportImage(export_file_path, info)
            else:
                bounds = QRect(0, 0, document.width(), document.height())
                info = self.createExportInfoObject(file_format, transparency)
                
                node.save(export_file_path, 
                          document.resolution() / 72.,
                          document.resolution() / 72., 
                          info, bounds)

    def exportNode(self, node, export_folder, filename, file_format, transparency=True):
        """Export a single node with format-specific settings (no scaling)"""
        export_file_path = os.path.join(
            self.directoryTextField.text(), 
            export_folder, 
            f"{filename}.{file_format}"
        )

        document = Application.activeDocument()
        
        # Handle native format exports differently
        formatUpper = file_format.upper()
        
        if formatUpper == "KRA":
            # For KRA, save the document directly
            document.saveAs(export_file_path)
        elif formatUpper == "PSD":
            # For PSD, use exportImage with mime type
            info = self.createExportInfoObject(file_format, transparency)
            document.exportImage(export_file_path, info)
        else:
            # For image formats, export the node
            bounds = QRect(0, 0, document.width(), document.height())
            info = self.createExportInfoObject(file_format, transparency)
            
            node.save(export_file_path, 
                      document.resolution() / 72.,
                      document.resolution() / 72., 
                      info, bounds)

    def exportLayers(self, parentNode, parentDir, file_format, 
                     target_width, target_height, transparency=True):
        """Export layers separately with scaling"""
        for node in parentNode.childNodes():
            if node.name() == "Selection Mask":
                continue
            elif self.ignoreFilterLayersCheckBox.isChecked() and 'filter' in node.type():
                continue
            elif self.ignoreInvisibleLayersCheckBox.isChecked() and not node.visible():
                continue
            elif node.type() == 'grouplayer' and node.childNodes() and not self.groupAsLayerCheckBox.isChecked():
                newDir = os.path.join(parentDir, node.name())
                self.createDirectory(newDir)
                self.exportLayers(node, newDir, file_format, 
                                 target_width, target_height, transparency)
            else:
                node_name = node.name()
                # Check for format override tags in layer name
                export_format = file_format
                if '[jpeg]' in node_name.lower() or '[jpg]' in node_name.lower():
                    export_format = 'jpg'
                elif '[png]' in node_name.lower():
                    export_format = 'png'
                elif '[jxl]' in node_name.lower():
                    export_format = 'jxl'
                self.exportNodeWithScale(node, parentDir, node_name, export_format,
                                        target_width, target_height, transparency)

    def createDirectory(self, directory):
        """Create export directory if it doesn't exist"""
        target_directory = os.path.join(self.directoryTextField.text(), directory)
        if os.path.exists(target_directory) and os.path.isdir(target_directory):
            return
        try:
            os.makedirs(target_directory)
        except OSError as e:
            raise e
        
