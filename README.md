# Krita Revamp

<img width="1920" height="1051" alt="image" src="https://github.com/user-attachments/assets/4e97e1d7-4abe-410c-953e-d7711edb7842" />
Krita is a free and open source digital painting application. It is for artists who want to create professional work from start to end. Krita is used by comic book artists, illustrators, concept artists, matte and texture painters and in the digital VFX industry. <br>

I made Krita Revamp because Krita lacks important features for those coming from Photoshop/Clip Studio paint and not all of them can be added via plugins. I chose to modify Krita 5.2.14 because it is stable and fast which makes it perfect for professionals that want a painting program that just works.

### Features/Changes

- Removed news section at welcome screen so you can see more of your recent images
- For Photoshop users: "Activate Line Tool" only activates when freehand brush tool is the current tool <br>
Demo: https://krita-artists.org/t/canvas-input-settings-configure-selection-settings-photoshop-compatible-inconsistencies/32351/9?u=tenzindraws
- Groups are shorter and use a folder icon for thumbnails like Photoshop folders
<img width="259" height="354" alt="image" src="https://github.com/user-attachments/assets/6f4b769e-4570-4b58-b492-711033027401" /> <br>
- Vertical toolbar icons can be resized in Settings > Window
- Added "extra space" spacers so you can customize your toolbars more since expanding spacers can only be used once <br>
<img width="500" src="https://github.com/user-attachments/assets/e75fa0d9-e167-41cc-9278-41a22914d316" />

- Overview updates instantly - no more 1 second latency for brushstrokes to appear
- Implemented the same togglable horizontal relative zoom option from 5.3 prealpha to this version of Krita
- Added smoothing slider - optional toolbar slider
- Added extra spacers toolbar actions
- Krita revamp persistently remembers what settings you've changed on your brush preset and ONLY resets when you explicity click the "Reload the brush preset" button. The default version of Krita would reset your brush settings unless you clicked "Overwrite Brush Preset" every single time before closing Krita.
- Removed "Temporarily Save Tweaks To Presets" because it's not needed due to Revamp's change.

#### Built-in plugins
- dockerundercursor
- krita_ui_tweaks (modified PS version)
- quick_brush_size
- [separatebrusheraser](https://krita-artists.org/t/separate-brush-eraser-plugin/125172)
- [layer_kit](https://krita-artists.org/t/layer-kit-organize-your-layers-faster/157281/18)
- quickexportdocker <br>
<img width="294" height="449" alt="image" src="https://github.com/user-attachments/assets/5dcb81bb-f9eb-4306-8d8e-ed35018993b5" /> <br>
- preset_groups
- super_docker-lock
- timer_watch
- krita_work_timer
- krita-redesign (modified PS version)
- label-box


## Installation

If you're on Windows, download the latest release and install <br>

If you prefer to build from source, download the git repository or "Download Zip" and proceed with Krita's instructions

**Refer to Krita's docs for building from source:**

- **Windows:** <br>
https://docs.krita.org/sl/untranslatable_pages/building_krita.html#building-on-windows

- **Linux:** <br>
https://docs.krita.org/sl/untranslatable_pages/building_krita.html#building-on-linux
<br>


---
## Development Notes

**Krita Revamp vs Krita 5.2.14 diffs:** <br>
https://github.com/KDE/krita/compare/v5.2.14...10zindraws:Krita-Revamp:revamp-5.2.14
<br>

### License

Krita as a whole is licensed under the GNU Public License, Version 3. Individual files may have a different, but compatible license.
