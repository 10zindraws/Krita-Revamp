# SPDX-License-Identifier: GPL-3.0-or-later
# Brush Size Acceleration Plugin for Krita
# Provides accelerating keyboard shortcuts for brush size adjustment

from krita import Krita
from .quick_brush_size import BrushSizeAccelerationExtension
from .docker import registerDocker

# Get Krita instance
app = Krita.instance()

# Register the extension (provides the accelerating shortcuts)
app.addExtension(BrushSizeAccelerationExtension(app))

# Register the docker (provides the settings UI)
registerDocker()
