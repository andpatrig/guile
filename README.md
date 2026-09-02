# gui**le**

A lightweight Python framework for building desktop apps.

---

## Philosophy

Guile started as a personal tool for building lab and research apps — the kind of quick internal dashboards, data explorers, and parameter tools that are too specific to justify a full web stack, but too interactive for a script. It does two things and tries to do them well. First, it layers interactivity on top of the Python you already have: your functions stay ordinary Python, and guile just wires them to widgets. Second, it follows a single reactive rule — change a state value and the interface updates, patching only the parts that actually changed, so text stays in inputs and focus is never lost. The app is one Python process that opens a native window: no server, no ports, no browser tab.

---

## Install

```bash
pip install guile
```

Requires `pywebview`. On Windows, WebView2 ships with Windows 10/11 — nothing extra to install.

---

## Quick start

```python
import guile as gui

count = gui.state(0)

@gui.app("Counter", width=400, height=300)
def ui():
    with gui.col(align="center", justify="center", style="height:100vh"):
        with gui.card(gap=14):
            gui.title("Counter")
            with gui.row(gap=16, align="center", justify="center"):
                gui.button("−", variant="secondary",
                           on_click=lambda: count.update(lambda x: x - 1))
                gui.text(count.value, size="2xl", bold=True,
                         style="min-width:64px;text-align:center")
                gui.button("+",
                           on_click=lambda: count.update(lambda x: x + 1))

gui.run()
```

`@gui.app()` defines the app; `gui.run()` opens the window and blocks until it is closed. Code written after `gui.run()` executes once the window closes — a natural place to save the session or continue a processing pipeline (see `examples/field_notes.py`).

While building a UI, use `gui.run(dev=True)`: guile watches your script and reloads the app inside the open window every time you save the file. Errors show in the window without killing the session; each reload resets state to its initial values.

---

## How it works

- `gui.state(value)` — a reactive value; setting it re-renders the UI automatically. Read it through `.value`, always
- `with gui.card():` / `with gui.col():` / `with gui.row():` — layout containers; everything indented goes inside
- `gui.button()`, `gui.slider()`, `gui.input()`, `gui.table()` — widgets that take `on_click=` or return their current value
- `gui.figure(fig)` — embed a matplotlib figure inline
- `gui.leaflet(center, markers=..., layers=...)` — embed an interactive map; drape a georeferenced image (`gui.ImageOverlay`), a pre-tiled drone mosaic (`gui.TileOverlay`), or vector features (`gui.GeoJSON`) over it
- `gui.task(fn, on_done=...)` — run slow work on a background thread; the window stays responsive
- `gui.run()` — opens the window; `gui.run(dev=True)` adds hot reload while you build
- `gui.package("my_app.py")` — build a shareable executable in one call

---

## Examples

| File | What it shows |
|------|--------------|
| `counter.py`              | State, buttons, badges                       |
| `todo.py`                 | Lists, dynamic rendering, checkboxes         |
| `settings.py`             | Sliders, selects, form layout                |
| `field_notes.py`          | Save on exit — code after `gui.run()`        |
| `mesonet_map.py`          | Leaflet map with markers                     |
| `mesonet_interactive.py`  | Live mesonet station data                    |
| `weather_explorer.py`     | Table, date picker, file picker              |
| `soils_lab.py`            | Lab data entry form                          |
| `soil_water_retention.py` | Sliders driving a live chart                 |
| `upload_weather_data.py`  | File picker, DataFrame, table                |
| `canopeo.py`              | Image analysis                               |
| `map_draw.py`             | Leaflet with draw tools                      |
| `map_overlays.py`         | Image overlay + GeoJSON on a map             |
| `map_areas.py`            | Draw, edit, label and select areas           |

---

## Using AI assistants with guile

If you build guile apps with an AI tool (Claude Code, Copilot, ChatGPT, …),
point it at the machine-readable docs instead of the HTML pages:

- **[llms-full.txt](https://andpatrig.github.io/guile/llms-full.txt)** — the complete API, the golden rules, and verified examples in one self-contained file. Everything an assistant needs to write correct guile apps.
- **[llms.txt](https://andpatrig.github.io/guile/llms.txt)** — the short index, following the `llms.txt` convention.

Tools working inside a cloned repo can also read the guile source directly — every public function carries a full docstring.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pywebview` | The window (installed with guile) |
| `matplotlib` | `gui.figure()` (installed with guile) |
| `numpy`, `pandas` | Optional — `pip install guile[science]` |

Everything else is Python standard library.

---

## Files

| File | Role |
|------|------|
| `state.py` | Reactive value class |
| `ui.py` | Render engine + all widgets |
| `_app.py` | Window lifecycle, pywebview bridge |
| `_template.py` | Embedded HTML/CSS/JS |
| `_package.py` | `gui.package()` — PyInstaller wrapper |
| `_dev.py` | `gui.run(dev=True)` — hot reload |
| `__init__.py` | Public API (`gui.*`) |

---

## Changelog
**v0.8.7**
- Fix: a progress bar inside a height-constrained column could shrink to nothing; the track now has `flex-shrink: 0`.

**v0.8.6**
- `gui.package()` now bundles only the native pywebview backend for the platform, so a machine with PyQt or PySide installed no longer drags all of Qt into the build (`native_only=`, `exclude_modules=`).
- `gui.package()` warns when building from the Anaconda base and suggests a clean venv; the docs no longer claim a separate environment is unnecessary.
- Fix: PyInstaller `RecursionError` on Anaconda machines, caused by matplotlib's optional IPython import chain, which is now excluded.
- Fix: apps built from a venv made with Anaconda's Python failed at launch with `DLL load failed while importing _ctypes`.
- Fix: `gui.package()` crashed with `UnicodeEncodeError` when its output was redirected to a file.

**v0.8.5**
- **Fix: v0.8.4 is broken — do not use it.** Its inline JavaScript contained a stray `}` (a splice error in the draw-tools rewrite), so the script never parsed, `window._guile` was undefined, and every app rendered blank. The test suite now syntax-checks the inline script (`node --check`, with a bracket-balance fallback) so this cannot ship again.

**v0.8.4**
- Drawn shapes owned by Python: `gui.leaflet(drawn=[...], draw_style=...)` rebuilds the editable draw layer from your list, so file-loaded plots and in-app drawings live in one list with no doubled outlines. New callbacks `on_shape_edit(id, type, coords)` and `on_shape_delete(id)` report the toolbar's edit/delete saves; `on_shape_click(id)` and `on_shape_hover(id | None)` make shapes selectable. Per-shape `style` and `label`. See `examples/map_areas.py`.
- `gui.GeoJSON`: new `label=` (permanent text pill on each feature, property name or callable) and `on_hover=` (properties on enter, `None` on leave).
- Docs: the how-to gains a Maps chapter (interactive map, draping imagery, GeoJSON labels/hover, drawing and editing areas) and a Sharing chapter (building an executable, avoiding install warnings). `llms-full.txt` gains a worked mapping example and new pitfalls; both LLM files are current for AI-assisted coding.

**v0.8.3**
- Map fix: switching a `TileOverlay` URL or an `ImageOverlay` no longer flashes the base map. New overlay layers are added first and the previous ones are removed once the new rasters have loaded (2 s fallback), so the swap is a cross-fade.

**v0.8.2**
- Map fix: a keyed map no longer goes blank when an *unkeyed* ancestor is replaced (e.g. a sidebar element appearing or disappearing shifts auto-numbered ids). The registry now detects the orphaned Leaflet instance, disposes it, and rebuilds the map in place, keeping the user's current pan/zoom.

**v0.8.1**
- Map overlay layers: `gui.leaflet(layers=[...])` accepts `gui.ImageOverlay(png, bounds=...)` to drape a georeferenced PNG/JPG, `gui.TileOverlay(url)` for a pre-tiled pyramid (the practical route for large drone mosaics — tile with gdal2tiles, serve with `python -m http.server`), and `gui.GeoJSON(data, popup=, on_click=)` for vector features with a per-feature click callback. See `examples/map_overlays.py`.

**v0.8.0**
- `gui.package()` now defaults to `package_mode="onedir"` (a folder holding the executable and its libraries) instead of a single file. Onedir draws fewer antivirus/SmartScreen false positives and starts faster — zip it or wrap it in an installer to share. Pass `package_mode="onefile"` for the old single-executable behavior. This replaces the `onefile=` argument.

**v0.7.0**
- `@gui.app` now only *defines* the app; add `gui.run()` at the end of your script to open the window. Code after `gui.run()` executes when the window closes — a natural place to save the session or continue a pipeline (see `examples/field_notes.py`).
- Hot reload: `gui.run(dev=True)` watches your script and reloads the app inside the open window on every save. Errors show in the window without killing the session; each reload resets state to initial values.
- `State` is now fully explicit: read and compare through `.value` (`if count.value > 0:`). Comparing or operating on the State object itself raises a clear `TypeError` — this fixes silent misbehavior with numpy arrays and DataFrames.
- New `gui.task(fn, on_done=, on_error=, busy=)` — run slow work on a background thread; clicks and renders keep flowing, and state set inside the task drives live progress bars.
- Errors raised in callbacks now show a danger toast in the window (previously invisible in packaged, windowed apps).
- DOM patcher fix: programmatic updates to inputs, checkboxes, textareas, and selects now render correctly after the user has interacted with them; the caret no longer jumps in `live=True` inputs.
- `gui.number_input()` keeps `.value` current per keystroke but re-renders on commit (Enter, focus leave, spinner); an empty or invalid commit keeps the current value.
- Maps rendered conditionally (e.g. inside a tab) now load Leaflet lazily instead of staying blank.
- Duplicate `key=` values print a one-time warning; `gui.progress(value, max=0)` no longer raises.
- New example `field_notes.py` (load → run → save-on-exit); test suite expanded to 14 tests.

**v0.6.0** — Improved map tile presets. Added `gui.package()` for one-call PyInstaller builds.

**v0.5.0** — Added center=True to app window. Improved code structure in how-to page.

**v0.4.0** — Added tabs. Fixed `datetime-local` input to display in 24-hour format.

**v0.3.0** — Added `notify` and `modal` widgets.

**v0.2.0** — Added `max_height` to `gui.scroll()`. Fixed `multiselect` change event.

**v0.1.0** — First release. 27 widgets.

---

MIT License
