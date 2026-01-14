# Changelog

All notable changes to this project will be documented in this file.
###### Note: this project is a fork of Krita 5.2.14

## [1.1.0] - 2026-01-14

### Added
- Ability to change Krita's startup slash art to a custom image
- Added "Stroke" display in Brush Preset docker for Photoshop-like brush previews

### Fixed
- Crash: Unsafe object deletion during event processing
- Log spam: Missing initialization, overly verbose warnings, missing action definitions
- Plugin compatibility: Action registry now gracefully handles dynamically-created plugin actions without XML data
- Plugin permissions: Plugin configs now points to proper appdata directory to survive krita reinstalls and avoid write permission conflicts
- Unnecessary Stroke Updates: Fixed issue where the brush stroke preview flashes (regenerates) when the user is just painting strokes.
- Opacity and Flow: Fixed confusion of changing Opacity showing changed Flow in the Brush Stroke Preview thumbnail


## [1.0.0] - 2026-01-11

### Changed
- Removed news section at welcome screen
- "Activate Line Tool" only activates when freehand brush tool is the current tool
- Groups are shorter and use a folder icon instead of live thumbnail. Folder icon changes depending on collapsed vs uncollapsed.
- Vertical toolbar icons can be resized in Settings > Window
- Overview updates instantly - no more 1 second latency for updates to appear
- Krita revamp persistently remembers what settings you've changed on your brush preset unless you explicity reload to defaults

### Added
- Added smoothing slider - optional toolbar slider
- Added extra spacers toolbar actions
- plugin dockerundercursor
- plugin krita_ui_tweaks
- plugin quick_brush_size
- plugin separatebrusheraser
- plugin layer_kit
- plugin quickexportdocker
- plugin preset_groups
- plugin super_docker-lock
- plugin timer_watch
- plugin krita_work_timer
- plugin krita-redesign
- plugin label-box