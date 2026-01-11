# Quick Export Plugin for Krita
# Based on Quick Export Layers Docker by fullmontis (public domain)

import krita
from .quickexportdocker import QuickExportDocker

Application.addDockWidgetFactory(krita.DockWidgetFactory("quickexport", 
                                 krita.DockWidgetFactoryBase.DockRight, 
                                 QuickExportDocker))

