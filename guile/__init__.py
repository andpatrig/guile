"""
guile — A lightweight Python desktop UI framework.

Quick start:

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

Five source files:
    state.py     — reactive State class
    ui.py        — render engine + all widget classes
    _app.py      — window lifecycle, pywebview bridge
    _template.py — embedded HTML/CSS/JS page
    __init__.py  — this file: the public API surface (gui.*)

Everything the user ever calls lives in this file as a plain function.
"""

from __future__ import annotations
from typing import Any, Callable, Optional, Union

from .state import State
from .ui import (
    # Layout
    Column, Row, Card, Scroll,
    # Display
    _Text, _Title, _Badge, _Spacer, _Divider, _ProgressBar, _Html,
    # Inputs
    _Button, _Input, _NumberInput, _TextArea, _Checkbox, _Select, _MultiSelect, _Slider,
    _DateInput, _DateTimeInput, _FilePicker,
    # Media
    _Figure, _Map, Marker,
    # Data
    _Table,
    # Theme
    _Theme, THEMES,
)
from ._app import _App


# ── State ──────────────────────────────────────────────────────────────────

def state(initial: Any, *, key: str = "") -> State:
    """
    Create a reactive value. Setting .value re-renders the UI automatically.

        count = gui.state(0)
        items = gui.state([])

        count.set(42)
        count.update(lambda x: x + 1)
        count.toggle()          # bool shorthand
    """
    return State(initial, key=key)


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
         margin: Union[int, str] = 0,
         style: str = "", key: Optional[str] = None) -> Card:
    """Raised surface. Use as `with gui.card():`. margin= adds outer spacing."""
    return Card(gap=gap, padding=padding, margin=margin, style=style, key=key)

def scroll(*, style: str = "", key: Optional[str] = None) -> Scroll:
    """Scrollable container. Use as `with gui.scroll():`"""
    return Scroll(style=style, key=key)

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
          style: str = "", key: Optional[str] = None) -> _Input:
    """Text input. Returns .value (str). Always provide key=."""
    return _Input(label, placeholder=placeholder, value=value, type=type,
                  disabled=disabled, on_change=on_change, style=style, key=key)

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
    Empty or invalid input silently falls back to the initial value.

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
        on_change — called with the new float on every valid change
    """
    return _NumberInput(label, value=value,
                        min=min, max=max, step=step,
                        unit=unit, disabled=disabled, on_change=on_change,
                        style=style, key=key)


def textarea(label: str = "", *, placeholder: str = "",
             value: Optional[Union[str, State]] = None,
             rows: int = 4, disabled: bool = False,
             on_change: Optional[Callable] = None,
             style: str = "", key: Optional[str] = None) -> _TextArea:
    """Multi-line text input. Returns .value (str). Always provide key=."""
    return _TextArea(label, placeholder=placeholder, value=value, rows=rows,
                     disabled=disabled, on_change=on_change, style=style, key=key)

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
    """
    return _FilePicker(label, value=value, file_types=file_types,
                       save=save, disabled=disabled,
                       on_change=on_change, style=style, key=key)


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
            style: str = "", key: Optional[str] = None) -> _Map:
    """Embed an interactive Leaflet map (OpenStreetMap tiles). Requires internet."""
    if _App._current:
        _App._current._use_leaflet = True
    return _Map(center=center, zoom=zoom, height=height,
                markers=markers, style=style, key=key)



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


# ── App decorator ───────────────────────────────────────────────────────────

def app(title_: str = "Guile App", *, width: int = 800, height: int = 600,
        resizable: bool = False, debug: bool = False):
    """
    Decorator that turns a ui() function into a runnable desktop app.

        @gui.app("My App", width=480, height=400)
        def ui():
            with gui.card():
                gui.title("Hello, world")
    """
    def decorator(fn: Callable):
        _App(title_, width=width, height=height,
             resizable=resizable, debug=debug).run(fn)
        return fn
    return decorator
