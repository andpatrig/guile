"""
guile — A lightweight Python desktop UI framework.

Quick start:

    import guile as gui

    def to_celsius(f):
        return round((f - 32) * 5 / 9, 1)

    fahrenheit = gui.state(32.0)

    @gui.app("Converter", width=360, height=300, center=True)
    def ui():
        with gui.card(gap=16):
            gui.title("Temperature converter")
            gui.slider("°F", value=fahrenheit, on_change=fahrenheit.set,
                       min=0, max=212)
            gui.text(f"{to_celsius(fahrenheit.value)} °C", size="2xl", bold=True)

    gui.run()

Source files:
    state.py     — reactive State class
    ui.py        — render engine + all widget classes
    _app.py      — window lifecycle, pywebview bridge
    _template.py — embedded HTML/CSS/JS page
    _package.py  — build a shareable executable (gui.package)
    _dev.py      — hot reload for development (gui.run(dev=True))
    __init__.py  — this file: the public API surface (gui.*)

Everything the user ever calls lives in this file as a plain function.
"""

from __future__ import annotations
import os
from typing import Any, Callable, Optional, Union

from .state import State
from .ui import (
    # Layout
    Column, Row, Card, Scroll,
    # Display
    _Text, _Title, _Badge, _Spacer, _Divider, _ProgressBar, _Html,
    # Inputs
    _Button, _Input, _NumberInput, _TextArea, _Checkbox, _Select, _MultiSelect, _Slider,
    _DateInput, _DateTimeInput, _FilePicker, _Tabs,
    # Media
    _Figure, _Map, Marker, ImageOverlay, TileOverlay, GeoJSON,
    # Data
    _Table,
    # Overlay
    _Modal,
    # Theme
    _Theme, THEMES,
)
from ._app import _App
from ._package import package, pack


# ── State ──────────────────────────────────────────────────────────────────

def state(initial: Any) -> State:
    """
    Create a reactive value. Setting .value re-renders the UI automatically.

        count = gui.state(0)
        items = gui.state([])

        count.set(42)
        count.update(lambda x: x + 1)
        count.toggle()          # bool shorthand
    """
    return State(initial)


# ── Layout ─────────────────────────────────────────────────────────────────

def col(*, gap: int = 12, padding: Union[int, str] = 0,
        align: str = "stretch", justify: str = "flex-start",
        fill: bool = False, scroll: bool = False,
        style: str = "", key: Optional[str] = None) -> Column:
    """Vertical stack. Use as `with gui.col():`"""
    return Column(gap=gap, padding=padding, align=align, justify=justify,
                  fill=fill, scroll=scroll, style=style, key=key)

def row(*, gap: int = 8, padding: Union[int, str] = 0,
        align: str = "center", justify: str = "flex-start",
        fill: bool = False, wrap: bool = False,
        style: str = "", key: Optional[str] = None) -> Row:
    """Horizontal stack. Use as `with gui.row():`"""
    return Row(gap=gap, padding=padding, align=align, justify=justify,
               fill=fill, wrap=wrap, style=style, key=key)

def card(*, gap: int = 12, padding: Union[int, str] = 20,
         margin: Union[int, str] = 0, fill: bool = False,
         style: str = "", key: Optional[str] = None) -> Card:
    """Raised surface. Use as `with gui.card():`. margin= adds outer spacing."""
    return Card(gap=gap, padding=padding, margin=margin, fill=fill,
                style=style, key=key)

def scroll(*, max_height: Optional[int] = 400,
           style: str = "", key: Optional[str] = None) -> Scroll:
    """
    Scrollable container. Use as `with gui.scroll():`.

    max_height= (default 400) sets the point at which the container starts
    scrolling. Pass max_height=None to let the parent's height constrain it.

        with gui.scroll():                    # scrolls after 400px
            gui.table(data)

        with gui.scroll(max_height=600):      # scrolls after 600px
            gui.table(data)

        with gui.scroll(max_height=None):     # fills parent, parent must have fixed height
            gui.table(data)
    """
    return Scroll(max_height=max_height, style=style, key=key)

def spacer(h: Optional[int] = None, w_: Optional[int] = None,
           fill: bool = False, key: Optional[str] = None) -> _Spacer:
    """Empty space. fill=True → flex:1 greedy spacer."""
    return _Spacer(h, w_, fill, key)

def divider(key: Optional[str] = None) -> _Divider:
    """Horizontal separator line."""
    return _Divider(key)


# ── Display ────────────────────────────────────────────────────────────────

def title(content: Any, *, size: str = "xl", muted: bool = False,
          style: str = "", key: Optional[str] = None) -> _Title:
    """Bold heading. size: xs | sm | md | lg | xl | 2xl | 3xl"""
    return _Title(content, size=size, muted=muted, style=style, key=key)

def text(content: Any, *, size: str = "md", bold: bool = False,
         italic: bool = False, muted: bool = False, underline: bool = False,
         mono: bool = False, color: Optional[str] = None,
         style: str = "", key: Optional[str] = None) -> _Text:
    """Inline or block text."""
    return _Text(content, size=size, bold=bold, italic=italic, muted=muted,
                 underline=underline, mono=mono, color=color, style=style, key=key)

def badge(text_: Any, *, variant: str = "primary",
          style: str = "", key: Optional[str] = None) -> _Badge:
    """Colored pill label. variant: primary | success | danger | warning | neutral"""
    return _Badge(text_, variant=variant, style=style, key=key)

def progress(value: Any, *, max: int = 100, color: Optional[str] = None,
             style: str = "", key: Optional[str] = None) -> _ProgressBar:
    """Horizontal progress bar. value goes from 0 to max."""
    return _ProgressBar(value, max=max, color=color, style=style, key=key)

def html(raw: str, key: Optional[str] = None) -> _Html:
    """Raw HTML escape hatch. Use sparingly."""
    return _Html(raw, key)


# ── Inputs ─────────────────────────────────────────────────────────────────

def button(label: Any, *, on_click: Optional[Callable] = None,
           variant: str = "primary", size: str = "md",
           disabled: bool = False, style: str = "",
           key: Optional[str] = None) -> _Button:
    """Button. variant: primary | secondary | ghost | danger. size: sm | md | lg"""
    return _Button(label, on_click=on_click, variant=variant, size=size,
                   disabled=disabled, style=style, key=key)

def input(label: str = "", *, placeholder: str = "",
          value: Optional[Union[str, State]] = None,
          type: str = "text", disabled: bool = False,
          on_change: Optional[Callable] = None,
          live: bool = False,
          style: str = "", key: Optional[str] = None) -> _Input:
    """
    Text input. Returns .value (str). Always provide key=.

    .value is kept current on every keystroke, but the UI only re-renders
    (and on_change only fires) when the field commits — Enter or focus
    leave. Pass live=True to re-render on every keystroke; avoid that next
    to large tables or figures, where each keystroke re-serializes the page.
    """
    return _Input(label, placeholder=placeholder, value=value, type=type,
                  disabled=disabled, on_change=on_change, live=live,
                  style=style, key=key)

def number_input(label: str = "", *,
                 value: Optional[Union[float, State]] = None,
                 min: Optional[float] = None,
                 max: Optional[float] = None,
                 step: float = 1.0,
                 unit: str = "",
                 disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "",
                 key: Optional[str] = None) -> _NumberInput:
    """
    Numeric input. Returns .value (float) directly — no string conversion needed.

    Follows the same value= convention as every other input widget.
    .value is kept current on every valid keystroke, but the UI only
    re-renders (and on_change only fires) when the field commits — Enter,
    focus leave, or a spinner click. An empty or invalid commit keeps the
    current value.

    Standalone — widget owns its state:
        depth = gui.number_input("Root depth", value=1.0, step=0.1, unit="m")
        gui.text(f"Depth: {depth.value} m")

    Bound to an existing State:
        Zr = gui.state(1.0)
        gui.number_input("Root depth", value=Zr, step=0.1, unit="m",
                         on_change=Zr.set)
        gui.text(f"Depth: {Zr.value} m")

    Arguments:
        label     — label shown above the field
        value     — initial float, or a State[float] for two-way binding.
                    Defaults to 0.0 when omitted.
        min       — minimum value, enforced on every change
        max       — maximum value, enforced on every change
        step      — spinner arrow increment
        unit      — unit label shown to the right: "mm", "m³/m³", "days" …
        disabled  — read-only appearance
        on_change — called with the new float when the field commits
    """
    return _NumberInput(label, value=value,
                        min=min, max=max, step=step,
                        unit=unit, disabled=disabled, on_change=on_change,
                        style=style, key=key)


def textarea(label: str = "", *, placeholder: str = "",
             value: Optional[Union[str, State]] = None,
             rows: int = 4, disabled: bool = False,
             on_change: Optional[Callable] = None,
             live: bool = False,
             style: str = "", key: Optional[str] = None) -> _TextArea:
    """
    Multi-line text input. Returns .value (str). Always provide key=.

    Like gui.input(): .value stays current per keystroke, UI re-renders on
    commit (focus leave). live=True re-renders on every keystroke.
    """
    return _TextArea(label, placeholder=placeholder, value=value, rows=rows,
                     disabled=disabled, on_change=on_change, live=live,
                     style=style, key=key)

def checkbox(label: str = "", *, value: Optional[Union[bool, State]] = None,
             disabled: bool = False, on_change: Optional[Callable] = None,
             key: Optional[str] = None) -> _Checkbox:
    """Boolean checkbox. Returns .value (bool). Always provide key=."""
    return _Checkbox(label, value=value, disabled=disabled,
                     on_change=on_change, key=key)

def select(options: Any, label: str = "", *,
           value: Optional[Union[str, State]] = None,
           disabled: bool = False, on_change: Optional[Callable] = None,
           style: str = "", key: Optional[str] = None) -> _Select:
    """Dropdown. options: list[str] | list[(val, label)] | dict. Returns .value (str)."""
    return _Select(options, label, value=value, disabled=disabled,
                   on_change=on_change, style=style, key=key)

def multiselect(options: Any, label: str = "", *,
                value: Optional[Union[list, State]] = None,
                rows: int = 4,
                disabled: bool = False,
                on_change: Optional[Callable] = None,
                style: str = "",
                key: Optional[str] = None) -> _MultiSelect:
    """
    Multi-select dropdown. Returns .value (list[str]), .set(), .update().

    The user holds Ctrl / Cmd to select multiple items.

        crops = gui.multiselect(
            ["Maize", "Wheat", "Soybean", "Cotton"],
            "Crop types", value=["Maize"], key="crops"
        )
        gui.text(f"Selected: {', '.join(crops.value)}")

    Arguments:
        options   — list[str] | list[(value, label)] | dict
        label     — label shown above the list
        value     — initial selection as a list of value strings, or a State[list]
        rows      — number of visible rows (default 4)
        disabled  — read-only appearance
        on_change — called with the new list[str] on every change
    """
    return _MultiSelect(options, label, value=value, rows=rows,
                        disabled=disabled, on_change=on_change,
                        style=style, key=key)


def slider(label: str = "", *, min: float = 0, max: float = 100,
           step: float = 1, value: Optional[Union[float, State]] = None,
           on_change: Optional[Callable] = None,
           style: str = "", key: Optional[str] = None) -> _Slider:
    """Range slider. Returns .value (float). Always provide key=."""
    return _Slider(label, min=min, max=max, step=step, value=value,
                   on_change=on_change, style=style, key=key)

def date_input(label: str = "", *, value: Optional[Union[str, State]] = None,
               disabled: bool = False, on_change: Optional[Callable] = None,
               style: str = "", key: Optional[str] = None) -> _DateInput:
    """Native date picker. Returns .value (str) as YYYY-MM-DD. Always provide key=."""
    return _DateInput(label, value=value, disabled=disabled,
                      on_change=on_change, style=style, key=key)

def datetime_input(label: str = "", *, value: Optional[Union[str, State]] = None,
                   disabled: bool = False, on_change: Optional[Callable] = None,
                   style: str = "", key: Optional[str] = None) -> _DateTimeInput:
    """
    Native datetime picker. Returns .value (str) as YYYY-MM-DDTHH:MM.

    Uses the browser's native datetime-local input — no external library needed.
    To parse the value in Python:
        from datetime import datetime
        dt = datetime.fromisoformat(widget.value)   # e.g. 2024-06-15T09:30

    To pre-fill with a specific datetime:
        gui.datetime_input("Start", value="2024-06-15T09:30", key="start")
    """
    return _DateTimeInput(label, value=value, disabled=disabled,
                          on_change=on_change, style=style, key=key)


def file_picker(label: str = "Choose file…", *,
                value: Optional[Union[str, State]] = None,
                file_types: tuple = (), save: bool = False,
                disabled: bool = False,
                on_change: Optional[Callable] = None,
                style: str = "", key: Optional[str] = None) -> _FilePicker:
    """OS native file dialog button. Returns .value (str) with the selected path.
    on_change is called with the selected path string after the dialog closes.

    The picker returns a path only — it never reads or parses the file, so it
    imposes no restriction on file type. You read the path yourself, e.g.:

        import yaml, tomllib   # tomllib is stdlib on Python 3.11+
        cfg = gui.file_picker("Load config…",
                              file_types=("yaml", "yml", "toml"),
                              on_change=load, key="cfg")

        def load(path):
            with open(path, "rb") as f:
                data = (tomllib.load(f) if path.endswith(".toml")
                        else yaml.safe_load(f))

    file_types accepts either bare extensions or full pywebview filter
    strings, mixed freely, and an "All files" entry is always appended so a
    too-narrow filter can never hide a file you meant to open:

        file_types=("yaml", "yml", "toml")   # simplest
        file_types=(".csv", "*.json")        # dots / globs are fine too
        file_types=("Data (*.yaml;*.toml)",) # explicit pywebview string
    """
    return _FilePicker(label, value=value, file_types=file_types,
                       save=save, disabled=disabled,
                       on_change=on_change, style=style, key=key)


def tabs(labels: list, *, value: Optional[Union[str, State]] = None,
         on_change: Optional[Callable] = None,
         style: str = "", key: Optional[str] = None) -> str:
    """
    Tab strip. Returns the active tab label as a plain string.
    Manages its own internal state — no gui.state() declaration needed.
    Always provide key= so the active tab survives re-renders.

    Basic usage:

        tab = gui.tabs(["Overview", "Data", "Info"], key="main")

        if tab == "Overview":
            gui.text("Summary content")
        elif tab == "Data":
            gui.table(records)
        elif tab == "Info":
            gui.text("About this app")

    Programmatic switching — bind to an external State so a callback
    can change the active tab:

        active = gui.state("Overview")
        gui.tabs(["Overview", "Data"], value=active,
                 on_change=active.set, key="main")

        def after_load(path):
            records.set(load(path))
            active.set("Data")   # jump to Data tab on load
    """
    return _Tabs(labels, value=value, on_change=on_change,
                 style=style, key=key).value


# ── Data ───────────────────────────────────────────────────────────────────

def table(data: Any, *, columns: Optional[list] = None,
          max_rows: int = 2000,
          style: str = "", key: Optional[str] = None) -> _Table:
    """
    Data table. Accepts common Python data structures directly:

        gui.table(df)                      # pandas DataFrame
        gui.table(arr)                     # numpy 2-D array
        gui.table(records)                 # list of dicts (native)
        gui.table(rows)                    # list of lists

    columns= selects/reorders which keys to show.
    max_rows= caps rendering (default 2000) with a notice row when clipped.
    """
    return _Table(data, columns=columns, max_rows=max_rows,
                  style=style, key=key)


# ── Media ───────────────────────────────────────────────────────────────────

def figure(fig, *, dpi: int = 96, width: str = "100%",
           caption: Optional[str] = None, transparent: bool = True,
           static: bool = False, style: str = "",
           key: Optional[str] = None) -> _Figure:
    """Embed a matplotlib Figure as an inline PNG."""
    return _Figure(fig, dpi=dpi, width=width, caption=caption,
                   transparent=transparent, static=static, style=style, key=key)

def leaflet(center: tuple = (0.0, 0.0), *, zoom: int = 10,
            height: int = 380, markers: Optional[list] = None,
            on_click:  Optional[Callable] = None,
            on_move:   Optional[Callable] = None,
            on_shape:  Optional[Callable] = None,
            draw: Any = False, tiles: Any = "street",
            layers: Optional[list] = None,
            style: str = "", key: Optional[str] = None) -> _Map:
    """
    Embed an interactive Leaflet map. Requires internet for tile loading.

    Overlay layers — drawn in list order between the base tiles and markers:
        layers=[
            gui.ImageOverlay("ndvi.png",            # PNG/JPG over a lat/lon box
                             bounds=((39.18, -96.60), (39.20, -96.56)),
                             opacity=0.7),
            gui.TileOverlay("http://localhost:8000/tiles/{z}/{x}/{y}.png",
                            max_zoom=21),           # pre-tiled drone mosaic
            gui.GeoJSON("plots.geojson", color="#e63946", popup="plot_id",
                        on_click=lambda props: selected.set(props)),
        ]
    ImageOverlay embeds the file in the page — keep it modest. For large
    imagery tile it once (gdal2tiles) and serve the folder with
    `python -m http.server`; TileOverlay then streams only the tiles in view.

    Callbacks:
        on_click(lat, lon)      — fires when the user clicks the map background
        on_move(center, zoom)   — fires after pan/zoom ends;
                                  center=(lat, lon) tuple, zoom=int
        on_shape(type, coords)  — fires when a shape is drawn (requires draw=);
                                  type: "rectangle"|"polygon"|"polyline"|
                                        "circle"|"marker"
                                  coords: [[lat,lon], ...] for polygon/rect/polyline;
                                          {"lat","lng","radius"} for circle;
                                          {"lat","lng"} for marker

    Draw tools:
        draw=["rectangle","polygon"]  — show specific drawing tools
        draw=True                     — show all tools (rectangle, polygon,
                                        polyline, circle, marker)
        draw=False                    — no tools (default)

    Tile layers (base imagery) — all keyless public servers:
        tiles="street"     — OpenStreetMap (default)
        tiles="satellite"  — Esri World Imagery
        tiles="hybrid"     — satellite + place / road labels
        tiles="terrain"    — OpenTopoMap
        tiles="light"      — Carto Positron (muted, good under data)
        tiles="dark"       — Carto Dark Matter
        tiles="<url>"      — any XYZ template with {z}/{x}/{y}
        tiles={"url": "...", "attribution": "...", "max_zoom": 19}

    Switch views live by binding tiles to a State:

        view = gui.state("street")
        gui.select(["street", "satellite", "hybrid"], "Map view",
                   value=view, on_change=view.set, key="view")
        gui.leaflet(center=(39.19, -96.58), zoom=13,
                    tiles=view.value, key="map")

    Per-marker callbacks:
        gui.Marker((lat, lon), on_click=fn)

    Always supply key= when using any callback so the element ID is stable
    across renders — callback cids are derived from that ID.
    """
    if _App._current:
        _App._current._use_leaflet = True
        if draw:
            _App._current._use_leaflet_draw = True
    return _Map(center=center, zoom=zoom, height=height,
                markers=markers, on_click=on_click, on_move=on_move,
                on_shape=on_shape, draw=draw, tiles=tiles,
                layers=layers, style=style, key=key)



# ── Notify (imperative toast — bypasses the render cycle) ────────────────────

def notify(message: str, *,
           variant: str = "success",
           duration: float = 3.0) -> None:
    """
    Show a temporary notification toast by injecting it directly into the
    browser DOM. No state variable or re-render required.

    Call from callbacks only — not from inside ui().
    The window must be open before notify() is called.

        def save(path):
            df.value.to_csv(path, index=False)
            gui.notify("File saved!", variant="success")

        def delete():
            rows.set([])
            gui.notify("All rows cleared.", variant="warning", duration=5)

    Variants: "success", "danger", "warning", "primary", "neutral"
    duration: seconds before auto-dismiss (default 3).
    """
    from ._app import _App
    import html as _h
    import json as _json
    app = _App._current
    if not app or not app._window:
        return

    COLOURS = {
        "success": ("#16a34a", "#dcfce7"),
        "danger":  ("#dc2626", "#fee2e2"),
        "warning": ("#d97706", "#fef3c7"),
        "primary": ("#6366f1", "#ede9fe"),
        "neutral": ("#6b7280", "#f3f4f6"),
    }
    fg, bg = COLOURS.get(variant, COLOURS["primary"])
    # NOTE: no manual quote-escaping needed — the message is embedded
    # below via json.dumps(), the canonical way to produce a JS string
    # literal from Python (handles quotes, backslashes, and unicode).
    msg    = _h.escape(str(message))
    ms     = int(duration * 1000)

    close_style = (
        "background:none;border:none;cursor:pointer;"
        f"font-size:16px;line-height:1;color:{fg};"
        "padding:0;margin-left:8px;opacity:.7"
    )
    close_btn = (
        '<button onclick="this.parentNode.remove()"'
        f' style="{close_style}">&#x2715;</button>'
    )
    inner    = f"<span>{msg}</span>{close_btn}"
    card_css = f"background:{bg};color:{fg};border:1.5px solid {fg};"

    # Build JS as a single concatenated string — no join(), no list,
    # so semicolons land correctly inside the function body.
    js = (
        "(function(){"
        "var e=document.createElement('div');"
        "e.className='guile-notify';"
        f"e.style.cssText={_json.dumps(card_css)};"
        f"e.innerHTML={_json.dumps(inner)};"
        "document.body.appendChild(e);"
        f"setTimeout(function(){{if(e.parentNode)e.remove();}},{ms});"
        "})();"
    )
    app._window.evaluate_js(js)


# ── Background tasks ────────────────────────────────────────────────────────

def task(fn: Callable, *,
         on_done: Optional[Callable] = None,
         on_error: Optional[Callable] = None,
         busy: Optional[State] = None) -> None:
    """
    Run fn() on a background thread so the window stays responsive.

    Call from a callback (on_click=, on_change=) when the work is slow —
    downloading data, crunching an image, a long computation. Without
    task(), a slow callback freezes the whole app until it finishes:
    no clicks are handled and no renders happen, so even a progress bar
    can't update.

        df   = gui.state(None)
        busy = gui.state(False)

        def fetch():                      # runs in the background
            import pandas as pd
            return pd.read_csv(URL)       # the UI stays alive meanwhile

        def start():
            gui.task(fetch, on_done=df.set, busy=busy)

        @gui.app("Weather")
        def ui():
            gui.button("Loading…" if busy.value else "Fetch data",
                       on_click=start, disabled=busy.value)
            if df.value is not None:
                gui.table(df.value)

    Arguments:
        fn        — the slow function, called with no arguments (use a
                    lambda or functools.partial to bind arguments).
        on_done   — called with fn's return value when it finishes.
        on_error  — called with the exception if fn raises. When omitted,
                    the error is printed and shown as a danger toast.
        busy      — a State[bool] set to True while the task runs and
                    back to False when it finishes (success or error).
                    Bind it to disable buttons / show a "working" label.

    How it fits the render model:
      • State .set() calls made inside fn are safe from the background
        thread and re-render as usual — update a gui.state() progress
        value inside fn to drive a live progress bar.
      • on_done / on_error run back on the app's worker thread,
        serialized with every other event — so they can freely touch
        state without racing a render or another callback.
      • Call task() from callbacks, not from inside ui().
    """
    import threading as _threading
    from ._app import _App
    app = _App._current

    if busy is not None:
        busy.set(True)

    def _deliver(cb):
        """Run cb on the worker thread when there is an app, else inline."""
        if app is not None:
            app._queue.put(("call", cb, None))
        else:
            cb()

    def _runner():
        try:
            result = fn()
        except Exception as exc:
            def _fail(exc=exc):
                if busy is not None:
                    busy.set(False)
                if on_error is not None:
                    on_error(exc)
                else:
                    try:
                        raise exc
                    except Exception:
                        from .ui import _report_callback_error
                        _report_callback_error()
            _deliver(_fail)
        else:
            def _ok(result=result):
                if busy is not None:
                    busy.set(False)
                if on_done is not None:
                    on_done(result)
            _deliver(_ok)

    _threading.Thread(target=_runner, daemon=True,
                      name="guile-task").start()


# ── Overlays ────────────────────────────────────────────────────────────────

def modal(title: str = "", *,
          visible: bool = True,
          on_close: Optional[Callable] = None,
          width: int = 420,
          style: str = "",
          key: Optional[str] = None) -> _Modal:
    """
    Blocking modal dialog. Use as a context manager.

    When visible=False the modal renders nothing (no overhead).
    Always supply on_close= so the backdrop and ✕ button work.

        confirm = gui.state(False)

        def request_delete():
            confirm.set(True)

        def do_delete():
            # perform deletion
            confirm.set(False)

        @gui.app("My App")
        def ui():
            gui.button("Delete", on_click=request_delete)

            with gui.modal("Confirm delete",
                           visible=confirm.value,
                           on_close=lambda: confirm.set(False)):
                gui.text("This cannot be undone.")
                with gui.row(gap=8, justify="flex-end"):
                    gui.button("Cancel", variant="ghost",
                               on_click=lambda: confirm.set(False))
                    gui.button("Delete", variant="danger",
                               on_click=do_delete)
    """
    return _Modal(title, visible=visible, on_close=on_close,
                  width=width, style=style, key=key)

# ── Theme ──────────────────────────────────────────────────────────────────

def theme(
    preset:    Optional[str] = None,
    *,
    primary:   Optional[str] = None,
    bg:        Optional[str] = None,
    surface:   Optional[str] = None,
    surface_2: Optional[str] = None,
    text:      Optional[str] = None,
    text_2:    Optional[str] = None,
    border:    Optional[str] = None,
    radius:    Optional[int] = None,
    key:       Optional[str] = None,
) -> _Theme:
    """
    Apply a colour theme to the entire app.

    Call this as the FIRST thing inside your ui() function so it takes
    effect before any widgets are rendered.

    Built-in presets (8 values each, all others derived automatically):
        "light"  — indigo on light grey (default)
        "dark"   — indigo on near-black
        "neon"   — cyan on deep navy
        "rose"   — red on warm white
        "forest" — green on soft green
        "slate"  — grey on off-white

    Any argument overrides just that one value in the preset:
        gui.theme("dark", primary="#f43f5e")   # dark theme, rose accent
        gui.theme("light", radius=2)            # light theme, sharp corners

    Arguments:
        preset    — name of a built-in theme
        primary   — accent colour for buttons, sliders, focus rings (#hex)
        bg        — page/window background (#hex)
        surface   — card and input background (#hex)
        surface_2 — secondary surface, hover rows (#hex)
        text      — primary text colour (#hex)
        text_2    — secondary / muted text colour (#hex)
        border    — border and separator colour (#hex)
        radius    — base border radius for cards and inputs (int, px)

    All other colours (hover, tints, shadows, danger/success/warning) are
    derived automatically from these 8 values using HLS colour math.

    To see all built-in preset values:
        import guile; print(guile.THEMES)
    """
    return _Theme(preset=preset, primary=primary, bg=bg,
                  surface=surface, surface_2=surface_2,
                  text=text, text_2=text_2,
                  border=border, radius=radius, key=key)


# ── App decorator + run ─────────────────────────────────────────────────────

# The app registered by @gui.app, waiting for gui.run() to launch it.
_pending_app: Optional[tuple] = None   # (fn, config dict)
_run_called:  bool = False
_hint_installed: bool = False


def _install_run_hint():
    """
    If a script defines an app but never calls gui.run(), it exits doing
    nothing — the most confusing possible failure for a beginner. Print a
    clear hint at interpreter exit instead of staying silent.
    """
    global _hint_installed
    if _hint_installed:
        return
    _hint_installed = True
    import atexit

    def _hint():
        if _pending_app is not None and not _run_called:
            print("[guile] Your app never opened. @gui.app() defines the "
                  "app; gui.run() launches it.\n"
                  "        Add this line at the end of your script:\n\n"
                  "            gui.run()")
    atexit.register(_hint)


def app(title_: str = "Guile App", *, width: int = 800, height: int = 600,
        resizable: bool = False, center: bool = False, debug: bool = False):
    """
    Decorator that marks a function as the app's UI. The window opens when
    you call gui.run() — put it at the end of your script:

        @gui.app("My App", width=480, height=400)
        def ui():
            with gui.card():
                gui.title("Hello, world")

        gui.run()

    Because the decorator only *marks* the function, your script stays an
    ordinary Python module: importing it does not open a window, and code
    after gui.run() executes once the window is closed (see gui.run).

    center=True fills the window and centres your content on both axes, so a
    small single-card app needs no wrapping gui.col().

    If several functions are decorated, the last one defined is the app.
    """
    def decorator(fn: Callable):
        global _pending_app
        _pending_app = (fn, dict(title=title_, width=width, height=height,
                                 resizable=resizable, center=center,
                                 debug=debug,
                                 # source file of ui() — watched by dev mode
                                 file=fn.__code__.co_filename))
        _install_run_hint()
        return fn
    return decorator


def run(dev: bool = False) -> None:
    """
    Open the window and hand control to the app. Blocks until the user
    closes the window, then returns — so code after gui.run() is your
    "when the window closes" hook:

        df = gui.state(None)

        @gui.app("Data check")
        def ui():
            ...

        gui.run()

        # window just closed — your gui.state() values still hold
        # whatever the user left in them
        if df.value is not None:
            df.value.to_csv("last_session.csv", index=False)

    Typical uses for code after gui.run(): saving the session, closing
    instruments or connections, continuing a processing pipeline with the
    user's interactive choices, printing an exit summary.

    dev=True — hot reload while you build the UI:

        gui.run(dev=True)

    guile watches your script file; every time you save it, the app
    reloads inside the open window — no closing and relaunching. Each
    reload is a fresh start: module-level code re-runs and gui.state()
    values reset to their initial values, exactly as if you had re-run
    the script, except the window stays put. A save with a syntax error
    or crash shows the traceback in the window and keeps the previous
    UI running — fix the file and save again. Code after gui.run() does
    NOT execute on reloads, only when you finally close the window.
    Turn dev off for normal use and packaged apps.
    """
    global _run_called
    if _pending_app is None:
        raise SystemExit(
            "[guile] gui.run() was called but no app is defined.\n"
            "        Decorate your ui function first:\n\n"
            "            @gui.app(\"My App\")\n"
            "            def ui():\n"
            "                ...\n\n"
            "            gui.run()"
        )
    _run_called = True
    fn, cfg = _pending_app
    app = _App(cfg["title"], width=cfg["width"], height=cfg["height"],
               resizable=cfg["resizable"], center=cfg["center"],
               debug=cfg["debug"])
    if dev:
        script = cfg.get("file", "")
        if script and os.path.isfile(script):
            from ._dev import start_watcher
            start_watcher(app, script)
        else:
            print("[guile] dev mode unavailable: cannot locate the app's "
                  f"source file ({script!r}) — running without hot reload.")
    app.run(fn)
