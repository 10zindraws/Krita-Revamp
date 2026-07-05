# Krita Revamp

<img width="1920" height="1051" alt="image" src="https://github.com/user-attachments/assets/4e97e1d7-4abe-410c-953e-d7711edb7842" />
Krita is a free and open source digital painting application. It is for artists who want to create professional work from start to end. Krita is used by comic book artists, illustrators, concept artists, matte and texture painters and in the digital VFX industry. <br>

As an artist who has experience with Photoshop and some experience with Clip Studio Paint, krita has many weird quirks that make the program unnecessarily untuitive to use.
I made Krita Revamp because Krita (while it's a great open source painting program) gets in the way of painting sometimes with its UI and lack of important features. I've made several plugins as solutions and workarounds to make Krita easier to use but plugins alone are very limited compared to changing Krita's source code which where Krita Revamp comes into the picture.


## Why Krita 5.2.14?

It's the latest stable release which makes a strong foundation for modifications. Krita 5.3 prealpha has some minor improvements but it's currently still in development, unstable, and slower.

## Why not open pull requests to improve Krita as a whole?

Additional features can't be officially added to Krita 5.2.14 or 5.3 (according to their [monthly update](https://krita.org/en/posts/2025/monthly-update-33/)). Suggesting UI/UX changes and features for future versions of Krita and seeing them realized will take a long time and not all changes will be accepted.

### Features/Changes

- Brush stroke previews like Photoshop <br>
<img width="242" height="560" alt="image" src="https://github.com/user-attachments/assets/05f29cd4-2620-42e3-b0c1-c6c132fbec87" /> <br>
- Removed news section at welcome screen so you can see more of your recent images
- For Photoshop users: Horizontal relative zoom (like scrubby zoom) is an option (previously only an option in 5.3 prealpha). <br>
- For Photoshop users: "Activate Line Tool" only activates when freehand brush tool is the current tool <br>
[Demo and explanation](https://krita-artists.org/t/canvas-input-settings-configure-selection-settings-photoshop-compatible-inconsistencies/32351/9) <br>
  *make sure to unbind "Change Primary Setting" in Canvas Input Settings. Then bind Shift + Left Button to Activate Line Tool* <br>
  The Line Tool will not activate if you hold shift unless the freehand brush tool is your current active tool. Useful for lasso operations
- Groups are shorter and use a folder icon for thumbnails like Photoshop folders
<img width="259" height="354" alt="image" src="https://github.com/user-attachments/assets/6f4b769e-4570-4b58-b492-711033027401" /> <br>
- Vertical toolbar icons can be resized in Settings > Window
- Added "extra space" spacers so you can customize your toolbars more since expanding spacers can only be used once <br>
<img width="500" src="https://github.com/user-attachments/assets/e75fa0d9-e167-41cc-9278-41a22914d316" />

- Clipping Masks - see example: https://krita-artists.org/t/krita-with-clipping-test-build/68119/107?u=tenzindraws
- Overview updates instantly - no more 1 second latency for brushstrokes to appear
- Implemented the same togglable horizontal relative zoom option from 5.3 prealpha to this version of Krita
- Added smoothing slider - optional toolbar slider
- Added extra spacers toolbar actions
- Krita revamp persistently remembers what settings you've changed on your brush preset and ONLY resets when you explicity click the "Reload the brush preset" button. The default version of Krita would reset your brush settings unless you clicked "Overwrite Brush Preset" every single time before closing Krita.

#### Built-in plugins - Links lead to more info

- krita-redesign (modified version)
- krita_ui_tweaks (modified version)
- dockerundercursor
- [quick_brush_size](https://krita-artists.org/t/quick-brush-size/156643)
- [separatebrusheraser](https://krita-artists.org/t/separate-brush-eraser-plugin/125172) - You can use separate brushes for eraser and brush
- [layer_kit](https://krita-artists.org/t/layer-kit-organize-your-layers-faster/157281) - Adds Clipping Mask feature to Krita
- quickexportdocker - A fast file exporter that can export multiple file types and sizes <br>
<img width="294" height="449" alt="image" src="https://github.com/user-attachments/assets/5dcb81bb-f9eb-4306-8d8e-ed35018993b5" /> <br>
- [preset_groups](https://krita-artists.org/t/preset-groups-drag-and-drop-brush-management/154670) - For drag and drop brush management
- [super_docker-lock](https://krita-artists.org/t/super-docker-lock-keep-all-your-dockers-in-place/159261)
- [timer_watch](https://github.com/10zindraws/timer_watch_short) - A simple stopwatch, useful for gesture drawing
- [krita_work_timer](https://krita-artists.org/t/smart-time-tracker-plugin/155636) - Smart tracker to detect how much time you spend painting
- label-box
<br>

**Note: the plugins may not already be enabled after installing, to enable them go to the top bar of Krita and click `Settings → Python Plugin Manager → checkmark the plugins you want to use`**

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
### Development Notes

**Krita Revamp vs Krita 5.2.14 diffs:** <br>
https://github.com/KDE/krita/compare/v5.2.14...10zindraws:Krita-Revamp:revamp-5.2.14
<br>

---

### Donation

- Please consider donating to the Krita Foundation:
https://krita.org/en/donations/ <br>

- If you specifically find my Krita fork useful, feel free to support me at my [ko-fi page](https://ko-fi.com/tenzindraws)

---

### License

Krita as a whole is licensed under the GNU Public License, Version 3. Individual files may have a different, but compatible license.
