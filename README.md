# gui**le**

A lightweight Python framework for building desktop apps.

---

## Philosophy

Guile started as a personal tool for building lab and research apps — the kind of quick internal dashboards, data explorers, and parameter tools that are too specific to justify a full web stack, but too interactive for a script. The goal was always to stay out of the way: write Python top to bottom, get a window with a clean interface, nothing more.

It is not trying to compete with NiceGUI, PyQt, or Dash. It is the right tool for a simple lab, company, or personal project — and deliberately nothing more.

A few specific choices that shape how guile feels:

- **No full-page refresh.** When state changes, only the parts of the UI that actually changed are updated. Text stays in inputs, sliders don't jump, focus is never lost.
- **No nesting hell.** Layout is written top to bottom using `with` blocks. `with gui.card():` followed by indented widget calls reads the same way the finished UI looks.
- **No server.** The app runs as a single Python process and opens a window. There is no local HTTP server, no port to bind, no browser tab to manage.

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
                gui.text(count, size="2xl", bold=True,
                         style="min-width:64px;text-align:center")
                gui.button("+",
                           on_click=lambda: count.update(lambda x: x + 1))
```

---

## How it works

- `gui.state(value)` — a reactive value; setting it re-renders the UI automatically
- `with gui.card():` / `with gui.col():` / `with gui.row():` — layout containers; everything indented goes inside
- `gui.button()`, `gui.slider()`, `gui.input()`, `gui.table()` — widgets that take `on_click=` or return their current value
- `gui.figure(fig)` — embed a matplotlib figure inline
- `gui.leaflet(center, markers=...)` — embed an interactive map

---

## Examples

| File | What it shows |
|------|--------------|
| `01_counter.py`             | State, buttons, badges                |
| `02_todo.py`                | Lists, dynamic rendering, checkboxes  |
| `03_settings.py`            | Sliders, selects, form layout         |
| `04_mesonet_map.py`         | Leaflet map with markers              |
| `05_weather_explorer.py`    | Table, date picker, file picker       |
| `06_soils_lab.py`           | Lab data entry form                   |
| `07_ks_mesonet.py`          | Live mesonet station data             |
| `08_soil_water_retention.py`| Sliders driving a live chart          |
| `09_upload_weather_data.py` | File picker, DataFrame, table         |
| `10_canopeo.py`             | Image analysis                        |
| `11_map_draw.py`            | Leaflet with draw tools               |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pywebview` | Window |
| `matplotlib` | Only if you use `gui.figure()` |
| `numpy` | Only if your app uses it |

Everything else is Python standard library.

---

## Files

| File | Role |
|------|------|
| `state.py` | Reactive value class |
| `ui.py` | Render engine + all widgets |
| `_app.py` | Window lifecycle, pywebview bridge |
| `_template.py` | Embedded HTML/CSS/JS |
| `__init__.py` | Public API (`gui.*`) |

---

## Changelog
**v0.5.0** — Added center=True to app window. Improved code structure in how-to page.

**v0.4.0** — Added tabs. Fixed `datetime-local` input to display in 24-hour format.

**v0.3.0** — Added `notify` and `modal` widgets.

**v0.2.0** — Added `max_height` to `gui.scroll()`. Fixed `multiselect` change event.

**v0.1.0** — First release. 27 widgets.

---

MIT License
