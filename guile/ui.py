"""
guile.ui — All UI components.

This file contains two sections:

  SECTION 1 — Render engine (lines ~50–160)
    The machinery that makes `with gui.card():` work.
    You don't need to read this to use guile — skip to Section 2.

  SECTION 2 — Components (lines ~160+)
    Every widget: layout containers, text, inputs, media, data.
    This is the interesting part for anyone building on guile.

Usage:
    with gui.card():
        gui.title("Hello")
        name = gui.input("Name", key="name")   # returns State[str]
        with gui.row(gap=8):
            gui.button("Save", on_click=lambda: save(name.value))
"""

from __future__ import annotations
import threading
import html as _html
from typing import Any, Callable, List, Optional, Union

from .state import State


# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — Render engine
#
# How `with gui.card():` works:
#   Each thread has a private stack of "current parent" nodes.
#   Entering `with gui.card()` pushes a Card node onto the stack.
#   Every gui.text(), gui.button() etc. that runs inside the block
#   automatically appends itself to the stack's top node.
#   Exiting the `with` block pops the Card and attaches it to its parent.
#   Result: the user writes flat, top-to-bottom code;
#           guile assembles a proper tree.
# ══════════════════════════════════════════════════════════════════════════

# ── Thread-local parent stack ──────────────────────────────────────────────
_local = threading.local()

def _stack() -> List["Node"]:
    if not hasattr(_local, "stack"):
        _local.stack = []
    return _local.stack

def _push(node: "Node"):  _stack().append(node)
def _pop()  -> "Node":    return _stack().pop()
def _current() -> Optional["Node"]:
    s = _stack(); return s[-1] if s else None

def _attach(node: "Node"):
    """Attach a leaf node to the current parent (called on construction)."""
    parent = _current()
    if parent is not None:
        parent.children.append(node)


# ── ID counter + callback registry ────────────────────────────────────────
#
# Clicks can arrive from the WebView mid-render, when the callback table is
# half-built. So we keep two: _callbacks is the scratch pad rebuilt during each
# render; _live_callbacks is the committed snapshot from the last completed
# render. dispatch() always reads _live_callbacks, so a click always finds its
# handler. Both are mutated in place (never reassigned) so importers keep a
# reference to the same live object.

_id_counter:    int  = 0
_callbacks:       dict = {}  # scratch — rebuilt every render
_live_callbacks:  dict = {}  # committed snapshot — always safe to read
_silent_callbacks: dict = {} # silent handlers (no re-render on update)

def _reset_render():
    """Start a fresh render: reset IDs, callbacks, and the auto-key counter."""
    global _id_counter, _auto_key_counter
    _id_counter       = 0
    _auto_key_counter = 0   # must reset so widget N always gets key _auto_N
    _callbacks.clear()
    _silent_callbacks.clear()

def _commit_callbacks():
    """After a render completes, promote scratch callbacks to live."""
    _live_callbacks.clear()
    _live_callbacks.update({k: v for k, v in _callbacks.items()
                            if not k.endswith('__silent')})
    _silent_callbacks.clear()
    _silent_callbacks.update({k[:-8]: v for k, v in _callbacks.items()
                              if k.endswith('__silent')})

def _next_id(key: Optional[str] = None) -> str:
    global _id_counter
    if key:
        return f"gk-{key}"
    _id_counter += 1
    return f"g{_id_counter}"

def _reg(cid: str, fn: Callable):
    """Register an event handler for this render pass."""
    _callbacks[cid] = fn

def dispatch_silent(cid: str, value: Any = None):
    """
    Call cid's silent handler, if any, without triggering a re-render.
    The handler updates state via set_silent(). Used by multiselect onchange
    to keep .value current while the user is mid-selection.
    """
    silent_fn = _silent_callbacks.get(cid)
    if silent_fn:
        try:
            silent_fn(value)
        except Exception:
            import traceback
            traceback.print_exc()


def dispatch(cid: str, value: Any = None):
    """
    Call the live handler for cid. Used by _Bridge in _app.py.

    Handlers come in two shapes: input widgets take one arg, handler(value);
    buttons and the file picker take none, handler(). We try the shape that
    matches whether a value arrived and fall back on TypeError.
    """
    fn = _live_callbacks.get(cid)
    if not fn:
        return
    try:
        if value is not None:
            try:
                fn(value)    # input widgets always receive a string value
                return
            except TypeError:
                fn()         # must be a zero-arg on_click — call without value
        else:
            try:
                fn()         # buttons, file picker — no value
            except TypeError:
                pass         # one-arg handler called with None — skip safely
    except Exception:
        import traceback
        traceback.print_exc()


# ── HTML helpers ───────────────────────────────────────────────────────────
def _esc(s: Any) -> str:
    """Escape for use inside an HTML attribute (quotes included)."""
    return _html.escape(str(s), quote=True)

def _txt(s: Any) -> str:
    """Escape for use as HTML text content."""
    return _html.escape(str(s))


# ── Window reference (set by _App, read by _FilePicker) ───────────────────
# Avoids a circular import between ui.py and _app.py.
_current_window = None

def _set_window(win):
    global _current_window
    _current_window = win


# ── Base node ──────────────────────────────────────────────────────────────
class Node:
    """
    Base class for every UI element.

    Containers (Column, Row, Card) use the __enter__/__exit__ context manager
    so children accumulate during the `with` block.

    Leaves (Text, Button, Input…) call _attach() on construction so they
    join the current parent automatically.
    """
    def __init__(self, key: Optional[str] = None):
        self.id       = _next_id(key)
        self.children: List[Node] = []

    def __enter__(self):
        _push(self)
        return self

    def __exit__(self, *_):
        node   = _pop()
        parent = _current()
        if parent is not None:
            parent.children.append(node)
        return False

    def render(self) -> str:
        raise NotImplementedError

    def _render_children(self) -> str:
        return "".join(c.render() for c in self.children)

    def __str__(self):
        return self.render()


# ── Internal state store ───────────────────────────────────────────────────
# Input widgets own their State internally so the user doesn't need to
# declare gui.state() for every text field. The store is keyed by the
# widget's key= argument and survives re-renders so typed text isn't lost.
# It is cleared when the window closes (_App calls _clear_state_store()).

_state_store: dict = {}

def _get_or_create_state(key: str, initial: Any) -> State:
    if key not in _state_store:
        _state_store[key] = State(initial, key=key)
    return _state_store[key]

def _clear_state_store():
    """Reset all input states — called when the window closes."""
    _state_store.clear()

# Per-render widget counter — the sole source of auto-generated keys.
# Incremented each time a stateful widget is created; reset each render.
# Because ui() always runs top-to-bottom in the same order, counter
# position N always refers to the same widget across renders.
_auto_key_counter: int = 0

def _auto_key(key: Optional[str]) -> str:
    """
    Return key if given, otherwise the next counter value.

    The counter resets each render and increments once per stateful widget.
    Since ui() runs the same widgets in the same order every render, position
    N always maps to the same widget — a stable key with no line introspection.
    Pass an explicit key= inside loops or conditionals, where the widget set
    can change between renders.
    """
    global _auto_key_counter
    _auto_key_counter += 1
    return key if key is not None else f"_auto_{_auto_key_counter}"


# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — Components
# ══════════════════════════════════════════════════════════════════════════

# Aliases so built-in min/max are not shadowed by widget parameters
import builtins as _builtins
builtins_min = _builtins.min
builtins_max = _builtins.max

_SIZE_CSS = {
    "xs":  "font-size:11px",
    "sm":  "font-size:13px",
    "md":  "font-size:15px",
    "lg":  "font-size:18px",
    "xl":  "font-size:24px;font-weight:700;letter-spacing:-0.01em",
    "2xl": "font-size:32px;font-weight:700;letter-spacing:-0.02em",
    "3xl": "font-size:44px;font-weight:800;letter-spacing:-0.03em",
}

def _px(v):
    return f"{v}px" if isinstance(v, int) else str(v)


# ── Layout containers ──────────────────────────────────────────────────────

class _Container(Node):
    """Base for Column, Row, Card. Renders a div with CSS class + style."""
    def __init__(self, css_class: str = "", inline_style: str = "",
                 key: Optional[str] = None):
        super().__init__(key)
        self._css   = css_class
        self._style = inline_style
        # Note: __enter__ / __exit__ are inherited from Node.

    def render(self) -> str:
        inner = self._render_children()
        return (f'<div id="{self.id}" class="{self._css}" '
                f'style="{self._style}">{inner}</div>')


class Column(_Container):
    """
    Vertical stack. Use as `with gui.col():`.

    Layout props (WHERE children sit):
        gap, padding, align (horizontal), justify (vertical), fill, scroll
    Style props (HOW the container looks):
        style="..." — any raw CSS
    """
    def __init__(self, *, gap: int = 12, padding: Union[int, str] = 0,
                 align: str = "stretch", justify: str = "flex-start",
                 fill: bool = False, scroll: bool = False,
                 style: str = "", key: Optional[str] = None):
        cls = "guile-col"
        if fill:   cls += " guile-fill"
        if scroll: cls += " guile-scroll"
        s = (f"gap:{_px(gap)};padding:{_px(padding)};"
             f"align-items:{align};justify-content:{justify};" + style)
        super().__init__(css_class=cls, inline_style=s, key=key)


class Row(_Container):
    """
    Horizontal stack. Use as `with gui.row():`.

    Layout props: gap, padding, align (vertical), justify (horizontal),
                  fill, wrap
    """
    def __init__(self, *, gap: int = 8, padding: Union[int, str] = 0,
                 align: str = "center", justify: str = "flex-start",
                 fill: bool = False, wrap: bool = False,
                 style: str = "", key: Optional[str] = None):
        cls = "guile-row"
        if fill: cls += " guile-fill"
        if wrap: cls += " guile-wrap"
        s = (f"gap:{_px(gap)};padding:{_px(padding)};"
             f"align-items:{align};justify-content:{justify};" + style)
        super().__init__(css_class=cls, inline_style=s, key=key)


class Card(_Container):
    """
    Raised surface with shadow. Use as `with gui.card():`.

    margin= adds space around the outside of the card.
    Use a string for fine control: margin="0 0 12px 0" (top right bottom left).
    """
    def __init__(self, *, gap: int = 12, padding: Union[int, str] = 20,
                 margin: Union[int, str] = 0,
                 style: str = "", key: Optional[str] = None):
        # Only emit margin CSS when non-zero (avoids polluting every card)
        m = f"margin:{_px(margin)};" if margin and margin != 0 else ""
        s = f"gap:{_px(gap)};padding:{_px(padding)};{m}" + style
        super().__init__(css_class="guile-col guile-card", inline_style=s, key=key)


class Scroll(_Container):
    """
    Scrollable container. Use as `with gui.scroll():`.

    max_height= sets the maximum height before the container starts scrolling.
    Defaults to 400px. Pass max_height=None to let the container expand freely
    (only useful when the parent has a fixed height that constrains it).
    """
    def __init__(self, *, max_height: Optional[int] = 400,
                 style: str = "", key: Optional[str] = None):
        h = f"max-height:{max_height}px;" if max_height is not None else ""
        super().__init__(css_class="guile-col guile-fill guile-scroll",
                         inline_style=h + style, key=key)


# ── Leaf base ──────────────────────────────────────────────────────────────

class _Leaf(Node):
    """Base for all non-container widgets. Auto-attaches to current parent."""
    def __init__(self, key: Optional[str] = None):
        super().__init__(key)
        _attach(self)

    def render(self) -> str:
        raise NotImplementedError


# ── Display widgets ────────────────────────────────────────────────────────

class _Text(_Leaf):
    def __init__(self, content: Any, *, size: str = "md", bold: bool = False,
                 italic: bool = False, muted: bool = False, underline: bool = False,
                 mono: bool = False, color: Optional[str] = None,
                 style: str = "", key: Optional[str] = None):
        self._content   = content
        self._size      = size
        self._bold      = bold
        self._italic    = italic
        self._muted     = muted
        self._underline = underline
        self._mono      = mono
        self._color     = color
        self._extra     = style
        super().__init__(key)

    def render(self) -> str:
        s = _SIZE_CSS.get(self._size, _SIZE_CSS["md"]) + ";"
        if self._muted:     s += "color:var(--text-2);"
        if self._color:     s += f"color:{self._color};"
        if self._bold:      s += "font-weight:700;"
        if self._italic:    s += "font-style:italic;"
        if self._underline: s += "text-decoration:underline;"
        if self._mono:      s += "font-family:var(--mono);"
        s += self._extra
        return (f'<span id="{self.id}" class="guile-text" style="{s}">'
                f'{_txt(self._content)}</span>')


class _Title(_Leaf):
    def __init__(self, content: Any, *, size: str = "xl", muted: bool = False,
                 style: str = "", key: Optional[str] = None):
        self._content = content
        self._size    = size
        self._muted   = muted
        self._extra   = style
        super().__init__(key)

    def render(self) -> str:
        s = _SIZE_CSS.get(self._size, _SIZE_CSS["xl"]) + ";"
        if self._muted: s += "color:var(--text-2);"
        s += self._extra
        return f'<div id="{self.id}" style="{s}">{_txt(self._content)}</div>'


class _Badge(_Leaf):
    _VARIANTS = {
        "primary": "background:var(--primary-light);color:var(--primary);",
        "success": "background:var(--success-light);color:#15803d;",
        "danger":  "background:var(--danger-light);color:#dc2626;",
        "warning": "background:var(--warning-light);color:#b45309;",
        "neutral": "background:var(--surface-2);color:var(--text-2);",
    }
    def __init__(self, text: Any, *, variant: str = "primary",
                 style: str = "", key: Optional[str] = None):
        self._text    = text
        self._variant = variant
        self._extra   = style
        super().__init__(key)

    def render(self) -> str:
        s = self._VARIANTS.get(self._variant, self._VARIANTS["neutral"]) + self._extra
        return (f'<span id="{self.id}" class="guile-badge" style="{s}">'
                f'{_txt(self._text)}</span>')


class _Spacer(_Leaf):
    def __init__(self, h: Optional[int] = None, w_: Optional[int] = None,
                 fill: bool = False, key: Optional[str] = None):
        self._h = h; self._w = w_; self._fill = fill
        super().__init__(key)

    def render(self) -> str:
        s = ""
        if self._h:    s += f"height:{self._h}px;"
        if self._w:    s += f"width:{self._w}px;"
        if self._fill: s += "flex:1;"
        return f'<div id="{self.id}" style="{s}"></div>'


class _Divider(_Leaf):
    def __init__(self, key: Optional[str] = None):
        super().__init__(key)

    def render(self) -> str:
        return (f'<hr id="{self.id}" style="border:none;'
                f'border-top:1px solid var(--border);width:100%;margin:2px 0">')


class _ProgressBar(_Leaf):
    def __init__(self, value: Any, *, max: int = 100,
                 color: Optional[str] = None, style: str = "",
                 key: Optional[str] = None):
        self._value = value
        self._max   = max
        self._color = color
        self._extra = style
        super().__init__(key)

    def render(self) -> str:
        pct    = min(100, max(0, float(self._value) / self._max * 100))
        fill_s = f"width:{pct:.1f}%;background:{self._color or 'var(--primary)'};"
        return (f'<div id="{self.id}" class="guile-progress-track" style="{self._extra}">'
                f'<div class="guile-progress-fill" style="{fill_s}"></div></div>')


class _Html(_Leaf):
    """Raw HTML escape hatch — injected verbatim, use with care."""
    def __init__(self, raw: str, key: Optional[str] = None):
        self._raw = raw
        super().__init__(key)

    def render(self) -> str:
        return f'<div id="{self.id}">{self._raw}</div>'

# ── Theme helper ───────────────────────────────────────────────────────────

class _Theme(_Leaf):
    """
    Injects a <style> block that overrides the design token CSS variables.

    All colours are derived from 8 core values using proper HLS colour math,
    so you never have to set hover shades, tints, or borders manually.
    """

    def __init__(
        self,
        preset:    Optional[str] = None,
        primary:   Optional[str] = None,
        bg:        Optional[str] = None,
        surface:   Optional[str] = None,
        surface_2: Optional[str] = None,
        text:      Optional[str] = None,
        text_2:    Optional[str] = None,
        border:    Optional[str] = None,
        radius:    Optional[int] = None,
        key:       Optional[str] = None,
    ):
        base = dict(THEMES.get(preset or "light"))
        if primary   is not None: base["primary"]   = primary
        if bg        is not None: base["bg"]        = bg
        if surface   is not None: base["surface"]   = surface
        if surface_2 is not None: base["surface_2"] = surface_2
        if text      is not None: base["text"]      = text
        if text_2    is not None: base["text_2"]    = text_2
        if border    is not None: base["border"]    = border
        if radius    is not None: base["radius"]    = radius
        self._vars = base
        super().__init__(key)

    def render(self) -> str:
        v   = self._vars
        css = _compute_theme_css(
            v["primary"], v["bg"], v["surface"], v["surface_2"],
            v["text"], v["text_2"], v["border"], v["radius"],
        )
        return (f'<div id="{self.id}" style="display:none">'
                f'<style>:root{{{css}}}</style></div>')


# ── Input widgets ──────────────────────────────────────────────────────────
#
# All input widgets:
#   • Own their State internally (no need for separate gui.state() calls)
#   • Expose .value (read), .set(v), .update(fn)
#   • Require key= to keep state stable across re-renders
#   • Accept value=some_state for two-way binding to an external State


class _Button(_Leaf):
    """Button. Pass on_click= with a zero-argument lambda."""
    def __init__(self, label: Any, *, on_click: Optional[Callable] = None,
                 variant: str = "primary", size: str = "md",
                 disabled: bool = False, style: str = "",
                 key: Optional[str] = None):
        self._label   = label
        self._variant = variant
        self._size    = size
        self._disabled = disabled
        self._style   = style
        super().__init__(key)
        if on_click:
            _reg(self.id, on_click)

    def render(self) -> str:
        cls = f"guile-btn guile-btn-{self._variant}"
        if self._size != "md":
            cls += f" guile-btn-{self._size}"
        js  = f"window._guile.trigger('{self.id}',null)"
        dis = " disabled" if self._disabled else ""
        return (f'<button id="{self.id}" class="{cls}" style="{self._style}"'
                f' onclick="{js}"{dis}>{_txt(self._label)}</button>')


class _Input(_Leaf):
    """Single-line text input. Returns .value (str), .set(), .update()."""
    def __init__(self, label: str = "", *, placeholder: str = "",
                 value: Optional[Union[str, State]] = None,
                 type: str = "text", disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label       = label
        self._placeholder = placeholder
        self._type        = type
        self._disabled    = disabled
        self._style       = style
        _key              = _auto_key(key)
        initial           = value.value if isinstance(value, State) else (value or "")
        self._state       = value if isinstance(value, State) \
                            else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        val = self._state.value
        js  = f"window._guile.trigger('{self.id}',this.value)"
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        dis = " disabled" if self._disabled else ""
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}<input class="guile-input" type="{self._type}"'
                f' value="{_esc(val)}" placeholder="{_esc(self._placeholder)}"'
                f' oninput="{js}"{dis}></div>')


class _NumberInput(_Leaf):
    """
    Numeric input. Returns .value (float), .set(), .update().

    Stores and returns a float directly — no string conversion needed.
    Empty or invalid input silently falls back to the initial value.

    Follows the same value= convention as every other input widget:

        # Widget owns its state — pass a float or omit for 0.0
        depth = gui.number_input("Root depth", value=1.0, step=0.1, unit="m")
        gui.text(f"Depth: {depth.value} m")

        # Bind to an existing State
        Zr = gui.state(1.0)
        gui.number_input("Root depth", value=Zr, step=0.1, unit="m",
                         on_change=Zr.set)
    """
    def __init__(self, label: str = "", *,
                 value: Optional[Union[float, "State"]] = None,
                 min: Optional[float] = None,
                 max: Optional[float] = None,
                 step: float = 1.0,
                 unit: str = "",
                 disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "",
                 key: Optional[str] = None):
        self._label    = label
        self._min      = min
        self._max      = max
        self._step     = step
        self._unit     = unit
        self._disabled = disabled
        self._style    = style
        _key           = _auto_key(key)

        if isinstance(value, State):
            self._state    = value
            self._fallback = float(value.value)
        else:
            initial        = float(value) if value is not None else 0.0
            self._fallback = initial
            self._state    = _get_or_create_state(_key, initial)

        super().__init__(key)

        _fallback = self._fallback
        _state    = self._state

        def _handler(v):
            try:
                parsed = float(v)
                if min is not None: parsed = builtins_max(parsed, min)
                if max is not None: parsed = builtins_min(parsed, max)
            except (ValueError, TypeError):
                parsed = _fallback
            _state.set(parsed)
            if on_change:
                on_change(parsed)

        _reg(self.id, _handler)

    @property
    def value(self) -> float: return self._state.value
    def set(self, v: float):   self._state.set(float(v))
    def update(self, fn):      self._state.update(fn)

    def render(self) -> str:
        val  = self._state.value
        js   = f"window._guile.trigger('{self.id}',this.value)"
        dis  = " disabled" if self._disabled else ""
        mn   = f' min="{self._min}"'   if self._min is not None else ""
        mx   = f' max="{self._max}"'   if self._max is not None else ""
        lbl  = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
                f'{_txt(self._label)}</span>') if self._label else ""
        unit = (f'<span style="font-size:13px;color:var(--text-2);'
                f'margin-left:6px">{_txt(self._unit)}</span>') if self._unit else ""
        # Display the value without trailing zeros for clean appearance
        display = f"{val:g}"
        return (
            f'<div id="{self.id}" class="guile-field" style="{self._style}">'
            f'{lbl}'
            f'<div style="display:flex;align-items:center;gap:0">'
            f'<input class="guile-input" type="number"'
            f' value="{_esc(display)}" step="{self._step}"{mn}{mx}'
            f' oninput="{js}"{dis}>'
            f'{unit}'
            f'</div>'
            f'</div>'
        )


class _TextArea(_Leaf):
    """Multi-line text input. Returns .value (str), .set(), .update()."""
    def __init__(self, label: str = "", *, placeholder: str = "",
                 value: Optional[Union[str, State]] = None,
                 rows: int = 4, disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label       = label
        self._placeholder = placeholder
        self._rows        = rows
        self._disabled    = disabled
        self._style       = style
        _key              = _auto_key(key)
        initial           = value.value if isinstance(value, State) else (value or "")
        self._state       = value if isinstance(value, State) \
                            else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        val = self._state.value
        js  = f"window._guile.trigger('{self.id}',this.value)"
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        dis = " disabled" if self._disabled else ""
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}<textarea class="guile-textarea" rows="{self._rows}"'
                f' placeholder="{_esc(self._placeholder)}"'
                f' oninput="{js}"{dis}>{_txt(val)}</textarea></div>')


class _Checkbox(_Leaf):
    """Boolean checkbox. Returns .value (bool), .set(), .update()."""
    def __init__(self, label: str = "", *, value: Optional[Union[bool, State]] = None,
                 disabled: bool = False, on_change: Optional[Callable] = None,
                 key: Optional[str] = None):
        self._label    = label
        self._disabled = disabled
        _key           = _auto_key(key)
        initial        = value.value if isinstance(value, State) else bool(value)
        self._state    = value if isinstance(value, State) \
                         else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v == "true")
            if on_change: on_change(self._state.value)
        _reg(self.id, _handler)

    @property
    def value(self) -> bool: return self._state.value
    def set(self, v):         self._state.set(v)
    def update(self, fn):     self._state.update(fn)

    def render(self) -> str:
        chk = " checked" if self._state.value else ""
        js  = f"window._guile.trigger('{self.id}',String(this.checked))"
        dis = " disabled" if self._disabled else ""
        return (f'<label id="{self.id}" class="guile-check-group">'
                f'<input type="checkbox" class="guile-checkbox"{chk}'
                f' onchange="{js}"{dis}>'
                f'<span style="font-size:15px;color:var(--text)">'
                f'{_txt(self._label)}</span></label>')


class _Select(_Leaf):
    """
    Dropdown. options: list[str] | list[(value, label)] | dict.
    Returns .value (str), .set(), .update().
    """
    def __init__(self, options: Any, label: str = "", *,
                 value: Optional[Union[str, State]] = None,
                 disabled: bool = False, on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label    = label
        self._disabled = disabled
        self._style    = style
        # Normalize options to list of (value, label) pairs
        if isinstance(options, dict):
            self._opts = list(options.items())
        elif options and isinstance(options[0], (list, tuple)):
            self._opts = [(str(v), str(l)) for v, l in options]
        else:
            self._opts = [(str(o), str(o)) for o in options]
        _key        = _auto_key(key)
        initial     = (value.value if isinstance(value, State)
                       else (value or (self._opts[0][0] if self._opts else "")))
        self._state = value if isinstance(value, State) \
                      else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        current = str(self._state.value)
        opts    = "".join(
            f'<option value="{_esc(v)}"{" selected" if v == current else ""}>'
            f'{_txt(l)}</option>'
            for v, l in self._opts
        )
        js  = f"window._guile.trigger('{self.id}',this.value)"
        dis = " disabled" if self._disabled else ""
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}<select class="guile-select" onchange="{js}"{dis}>'
                f'{opts}</select></div>')


class _MultiSelect(_Leaf):
    """
    Multi-select dropdown. Returns .value (list[str]), .set(), .update().

    Renders as a <select multiple> sized to show up to `rows` options at once.
    The user holds Ctrl/Cmd to select multiple items.

        crops = gui.multiselect(
            ["Maize", "Wheat", "Soybean", "Cotton"],
            "Crop types", value=["Maize"], key="crops"
        )
        gui.text(f"Selected: {', '.join(crops.value)}")
    """
    def __init__(self, options: Any, label: str = "", *,
                 value: Optional[Union[list, "State"]] = None,
                 rows: int = 4,
                 disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "",
                 key: Optional[str] = None):
        self._label    = label
        self._rows     = rows
        self._disabled = disabled
        self._style    = style

        # Normalize options to list of (value, label) pairs
        if isinstance(options, dict):
            self._opts = list(options.items())
        elif options and isinstance(options[0], (list, tuple)):
            self._opts = [(str(v), str(l)) for v, l in options]
        else:
            self._opts = [(str(o), str(o)) for o in options]

        _key    = _auto_key(key)
        initial = (value.value if isinstance(value, State)
                   else (list(value) if value is not None else []))
        self._state = (value if isinstance(value, State)
                       else _get_or_create_state(_key, initial))
        super().__init__(key)

        def _handler(v):
            # JS sends selected values as a JSON-encoded list: '["a","b"]'
            import json
            try:
                selected = json.loads(v) if v else []
            except (ValueError, TypeError):
                selected = [v] if v else []
            self._state.set(selected)
            if on_change:
                on_change(selected)

        def _silent_handler(v):
            import json
            try:
                selected = json.loads(v) if v else []
            except (ValueError, TypeError):
                selected = [v] if v else []
            self._state.set_silent(selected)

        _reg(self.id, _handler)
        _callbacks[self.id + '__silent'] = _silent_handler

    @property
    def value(self) -> list: return self._state.value
    def set(self, v: list):   self._state.set(list(v))
    def update(self, fn):     self._state.update(fn)

    def render(self) -> str:
        selected = set(str(s) for s in (self._state.value or []))
        opts = "".join(
            f'<option value="{_esc(v)}"{" selected" if v in selected else ""}>'
            f'{_txt(l)}</option>'
            for v, l in self._opts
        )
        # Strategy: decouple state update from re-render.
        #
        # onchange fires on every click (including mid-Ctrl+click sequence).
        #   → Immediately sends selected values to Python via a "silent" path
        #     that updates state but suppresses re-render.
        #   → This keeps variables.value always current.
        #
        # onblur fires when the user moves focus away from the <select>.
        #   → Triggers a full re-render via the normal trigger path.
        #   → DOM is only replaced after the user has finished selecting.
        #
        # This is reliable regardless of interaction speed.
        collect = (f"JSON.stringify(Array.from(this.selectedOptions)"
                   f".map(function(o){{return o.value}}))")
        # silent update on every change — state updated, no re-render
        js_change = f"window._guile.silent('{self.id}',{collect})"
        # full trigger on blur — state already current, just re-renders
        js_blur   = f"window._guile.trigger('{self.id}',{collect})"
        dis = " disabled" if self._disabled else ""
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        hint = (f'<span style="font-size:11px;color:var(--text-2);margin-top:2px">'
                f'Hold Ctrl / Cmd to select multiple</span>')
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}'
                f'<select class="guile-select" multiple size="{self._rows}"'
                f' onchange="{js_change}" onblur="{js_blur}"{dis}>{opts}</select>'
                f'{hint}'
                f'</div>')


class _Slider(_Leaf):
    """Range slider. Returns .value (float), .set(), .update()."""
    def __init__(self, label: str = "", *, min: float = 0, max: float = 100,
                 step: float = 1, value: Optional[Union[float, State]] = None,
                 on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label = label
        self._min   = min
        self._max   = max
        self._step  = step
        self._style = style
        _key        = _auto_key(key)
        initial     = (value.value if isinstance(value, State)
                       else (value if value is not None else min))
        self._state = value if isinstance(value, State) \
                      else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(float(v))
            if on_change: on_change(float(v))
        _reg(self.id, _handler)

    @property
    def value(self) -> float: return self._state.value
    def set(self, v):          self._state.set(v)
    def update(self, fn):      self._state.update(fn)

    def render(self) -> str:
        val      = self._state.value
        trigger  = f"window._guile.trigger('{self.id}',this.value)"
        lbl_html = ""
        val_id   = f"{self.id}-val"   # ID of the live value span
        if self._label:
            lbl_html = (
                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
                f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
                f'{_txt(self._label)}</span>'
                f'<span id="{val_id}" style="font-size:13px;color:var(--text)">'
                f'{val:g}</span></div>'
            )
        # oninput  — updates the displayed value instantly in JS (no Python round-trip)
        # onchange — fires the Python callback only when the user releases the slider
        oninput  = (f"document.getElementById('{val_id}').textContent=this.value"
                    if self._label else "")
        oninput_attr  = f' oninput="{oninput}"' if oninput else ""
        onchange_attr = f' onchange="{trigger}"'
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl_html}'
                f'<input type="range" class="guile-slider"'
                f' min="{self._min}" max="{self._max}" step="{self._step}"'
                f' value="{val}"{oninput_attr}{onchange_attr}></div>')


class _DateInput(_Leaf):
    """Native OS date picker. Returns .value (str) as YYYY-MM-DD."""
    def __init__(self, label: str = "", *, value: Optional[Union[str, State]] = None,
                 disabled: bool = False, on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label    = label
        self._disabled = disabled
        self._style    = style
        _key           = _auto_key(key)
        initial        = value.value if isinstance(value, State) else (value or "")
        self._state    = value if isinstance(value, State) \
                         else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        val = self._state.value
        js  = f"window._guile.trigger('{self.id}',this.value)"
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        dis = " disabled" if self._disabled else ""
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}'
                f'<input type="date" class="guile-input"'
                f' value="{_esc(val)}" onchange="{js}"{dis}>'
                f'</div>')


class _DateTimeInput(_Leaf):
    """
    Native datetime picker. Returns .value (str) as YYYY-MM-DDTHH:MM.

    Uses the browser's native <input type="datetime-local">.
    The returned string follows the HTML datetime-local format:
        "2024-06-15T09:30"

    To parse it in Python:
        from datetime import datetime
        dt = datetime.fromisoformat(widget.value)
    """
    def __init__(self, label: str = "", *, value: Optional[Union[str, State]] = None,
                 disabled: bool = False, on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label    = label
        self._disabled = disabled
        self._style    = style
        _key           = _auto_key(key)
        initial        = value.value if isinstance(value, State) else (value or "")
        self._state    = value if isinstance(value, State) else _get_or_create_state(_key, initial)
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        val = self._state.value
        js  = f"window._guile.trigger('{self.id}',this.value)"
        lbl = (f'<span style="font-size:13px;font-weight:500;color:var(--text-2)">'
               f'{_txt(self._label)}</span>') if self._label else ""
        dis = " disabled" if self._disabled else ""
        return (f'<div id="{self.id}" class="guile-field" style="{self._style}">'
                f'{lbl}'
                f'<input type="datetime-local" class="guile-input"'
                f' value="{_esc(val)}" onchange="{js}"{dis}>'
                f'</div>')


class _FilePicker(_Leaf):
    """
    Button that opens the OS native file dialog. Returns .value (str) with
    the selected path. The filename is shown in the button after selection.
    """
    def __init__(self, label: str = "Choose file…", *,
                 value: Optional[Union[str, State]] = None,
                 file_types: tuple = (), save: bool = False,
                 disabled: bool = False,
                 on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._label      = label
        self._file_types = file_types
        self._save       = save
        self._disabled   = disabled
        self._style      = style
        _key             = _auto_key(key)
        initial          = value.value if isinstance(value, State) else (value or "")
        self._state      = value if isinstance(value, State) \
                           else _get_or_create_state(_key, initial)
        super().__init__(key)

        # Capture the save flag and state in the closure so the handler
        # is fully self-contained and needs no imports at call time.
        _save       = self._save
        _file_types = self._file_types
        _state      = self._state
        _on_change  = on_change
        _disabled   = disabled

        def _handler():
            # Runs on a background thread (_Bridge._run → dispatch).
            # _current_window is set by _App via _set_window() — no import needed.
            if _disabled:
                return
            try:
                import webview
                win = _current_window
                if win is None:
                    return
                dialog_type = webview.FileDialog.SAVE if _save else webview.FileDialog.OPEN
                result = win.create_file_dialog(
                    dialog_type,
                    allow_multiple=False,
                    file_types=_file_types,
                )
                if result:
                    path = result[0] if isinstance(result, (list, tuple)) else result
                    _state.set(str(path))
                    if _on_change:
                        _on_change(str(path))
            except Exception:
                import traceback
                traceback.print_exc()

        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v):        self._state.set(v)

    def render(self) -> str:
        js       = f"window._guile.trigger('{self.id}',null)"
        path     = self._state.value
        filename = path.replace("\\", "/").split("/")[-1] if path else ""
        lbl_html = _txt(self._label)
        if filename:
            lbl_html += (f' <span style="font-weight:400;opacity:.65;font-size:13px">'
                         f'({_txt(filename)})</span>')
        dis_attr  = ' disabled' if self._disabled else ""
        dis_style = (self._style + ";opacity:.45;cursor:not-allowed"
                     if self._disabled else self._style)
        return (f'<button id="{self.id}" class="guile-btn guile-btn-secondary"'
                f' style="{dis_style}" onclick="{js}"{dis_attr}>📁 {lbl_html}</button>')


class _Tabs(_Leaf):
    """
    Tab strip navigation. Manages its own internal state — no gui.state()
    declaration needed. Returns .value (str), the active tab label.
    Always supply key= so the active tab survives re-renders.

        tab = gui.tabs(["Overview", "Data", "Info"], key="t")
        if tab == "Overview":
            ...
        elif tab == "Data":
            gui.table(records)

    For programmatic switching, bind to an external State:

        active = gui.state("Overview")
        gui.tabs(["Overview", "Data"], value=active,
                 on_change=active.set, key="t")
        # from a callback: active.set("Data")
    """
    def __init__(self, labels: list, *,
                 value: Optional[Union[str, State]] = None,
                 on_change: Optional[Callable] = None,
                 style: str = "", key: Optional[str] = None):
        self._labels = [str(l) for l in labels]
        self._style  = style
        _key         = _auto_key(key)
        initial      = (value.value if isinstance(value, State)
                        else (value if value is not None
                              else (self._labels[0] if self._labels else "")))
        self._state  = (value if isinstance(value, State)
                        else _get_or_create_state(_key, initial))
        super().__init__(key)
        def _handler(v):
            self._state.set(v)
            if on_change: on_change(v)
        _reg(self.id, _handler)

    @property
    def value(self) -> str: return self._state.value
    def set(self, v: str):   self._state.set(str(v))
    def update(self, fn):    self._state.update(fn)

    def render(self) -> str:
        active = self._state.value
        buttons = "".join(
            f'<button class="guile-tab-btn{" guile-tab-active" if l == active else ""}"'
            f' onclick="window._guile.trigger(\'{self.id}\',\'{_esc(l)}\')">'
            f'{_txt(l)}</button>'
            for l in self._labels
        )
        return (f'<div id="{self.id}" class="guile-tabs" style="{self._style}">'
                f'<div class="guile-tab-strip">{buttons}</div>'
                f'</div>')


# ── Data widget ────────────────────────────────────────────────────────────

class _Table(_Leaf):
    """
    Simple data table. Pass a list of dicts.
    Use columns= to select or reorder which keys are shown.
    """
    @staticmethod
    def _normalise(data: Any) -> list:
        """
        Convert common data structures to list[dict] for rendering.

        Accepted inputs:
          list[dict]        — native format, returned as-is
          pandas DataFrame  — converted via to_dict("records")
          numpy 2-D array   — rows become dicts keyed "0", "1", "2" …
          numpy 1-D array   — single column keyed "value"
          list[list]        — rows become dicts keyed by column index
          list[scalar]      — single column keyed "value"
        """
        if data is None:
            return []

        # pandas DataFrame
        try:
            import pandas as _pd
            if isinstance(data, _pd.DataFrame):
                return data.to_dict("records")
        except ImportError:
            pass

        # numpy array
        try:
            import numpy as _np
            if isinstance(data, _np.ndarray):
                if data.ndim == 1:
                    return [{"value": v} for v in data.tolist()]
                if data.ndim == 2:
                    return [{str(j): row[j] for j in range(len(row))}
                            for row in data.tolist()]
        except ImportError:
            pass

        # list[list] or list[tuple]
        if data and isinstance(data[0], (list, tuple)):
            return [{str(j): row[j] for j in range(len(row))}
                    for row in data]

        # list[scalar] — single-column table
        if data and not isinstance(data[0], dict):
            return [{"value": v} for v in data]

        # Already list[dict]
        return list(data)

    def __init__(self, data: Any, *, columns: Optional[list] = None,
                 max_rows: int = 2000,
                 style: str = "", key: Optional[str] = None):
        self._data     = self._normalise(data)
        self._columns  = columns or (list(self._data[0].keys()) if self._data else [])
        self._max_rows = max_rows
        self._style    = style
        super().__init__(key)

    def render(self) -> str:
        if not self._data or not self._columns:
            return (f'<div id="{self.id}" class="guile-table-empty"'
                    f' style="{self._style}">No data</div>')
        data    = self._data[:self._max_rows]
        clipped = len(self._data) > self._max_rows
        headers = "".join(
            f'<th class="guile-th">{_txt(col)}</th>' for col in self._columns
        )
        rows = "".join(
            '<tr class="guile-tr">'
            + "".join(
                f'<td class="guile-td">{_txt(row.get(col, ""))}</td>'
                for col in self._columns
            )
            + "</tr>"
            for row in data
        )
        notice = (
            f'<tr><td colspan="{len(self._columns)}" '
            f'style="padding:8px 14px;font-size:12px;color:var(--text-3);'
            f'text-align:center;font-style:italic">'
            f'Showing {self._max_rows:,} of {len(self._data):,} rows'
            f'</td></tr>'
        ) if clipped else ""
        return (f'<div id="{self.id}" class="guile-table-wrap" style="{self._style}">'
                f'<table class="guile-table">'
                f'<thead><tr>{headers}</tr></thead>'
                f'<tbody>{rows}{notice}</tbody>'
                f'</table></div>')


# ── Media widgets ──────────────────────────────────────────────────────────

class _Figure(_Leaf):
    """
    Embeds a matplotlib Figure as a base64 PNG image.
    transparent=True blends the plot background with the app theme.
    static=True caches the result — use for figures that never change.
    """
    _cache: dict = {}

    def __init__(self, fig, *, dpi: int = 96, width: Optional[str] = "100%",
                 caption: Optional[str] = None, transparent: bool = True,
                 static: bool = False, style: str = "",
                 key: Optional[str] = None):
        self._fig         = fig
        self._dpi         = dpi
        self._width       = width
        self._caption     = caption
        self._transparent = transparent
        self._static      = static
        self._style       = style
        super().__init__(key)

    def _to_base64(self) -> str:
        """
        Encode the figure to a base64 PNG string.

        Fast path (persistent figures):
            If the figure has already been drawn at least once, we grab the
            raw RGBA pixel buffer directly from the canvas — no savefig, no
            file-format overhead. This is ~3x faster than savefig and works
            with any matplotlib Agg backend figure.

        Slow path (first render, or transparent/bbox figures):
            Falls back to savefig for correctness (handles bbox_inches,
            transparent backgrounds, and figures that have never been drawn).
        """
        import io, base64, struct, zlib
        import matplotlib.pyplot as plt

        # ── Try fast canvas path first ─────────────────────────────────
        try:
            canvas = self._fig.canvas
            # Ensure the canvas has been drawn at least once
            if not getattr(canvas, '_is_drawn', False):
                canvas.draw()
                canvas._is_drawn = True

            w, h = canvas.get_width_height()
            raw  = bytes(canvas.buffer_rgba())

            # Encode raw RGBA bytes to PNG using only stdlib (no Pillow)
            def _chunk(tag: bytes, data: bytes) -> bytes:
                c = tag + data
                return (struct.pack('>I', len(data)) + c
                        + struct.pack('>I', zlib.crc32(c) & 0xffffffff))

            rows = b''.join(
                b'\x00' + raw[y * w * 4:(y + 1) * w * 4]
                for y in range(h)
            )
            png = (
                b'\x89PNG\r\n\x1a\n'
                + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                + _chunk(b'IDAT', zlib.compress(rows, 1))   # level 1 = fastest
                + _chunk(b'IEND', b'')
            )
            result = base64.b64encode(png).decode()
            plt.close(self._fig)
            return result

        except Exception:
            # ── Slow path fallback ─────────────────────────────────────
            buf = io.BytesIO()
            self._fig.savefig(
                buf, format="png", dpi=self._dpi, bbox_inches="tight",
                facecolor="none" if self._transparent
                          else self._fig.get_facecolor(),
                transparent=self._transparent,
            )
            buf.seek(0)
            result = base64.b64encode(buf.read()).decode()
            plt.close(self._fig)
            return result

    def render(self) -> str:
        if self._static and self.id in _Figure._cache:
            b64 = _Figure._cache[self.id]
        else:
            b64 = self._to_base64()
            if self._static:
                _Figure._cache[self.id] = b64

        caption_html = (
            f'<figcaption style="font-size:13px;color:var(--text-2);'
            f'text-align:center;margin-top:6px">{_txt(self._caption)}</figcaption>'
            if self._caption else ""
        )
        return (f'<figure id="{self.id}" style="margin:0">'
                f'<img src="data:image/png;base64,{b64}"'
                f' style="width:{self._width};display:block;{self._style}"'
                f' alt="{_esc(self._caption or "figure")}">'
                f'{caption_html}</figure>')


class Marker:
    """
    A map marker for gui.leaflet().
        Marker((lat, lon), popup="Hello", tooltip="hover text")
        Marker((lat, lon), on_click=lambda: ...)
    """
    def __init__(self, latlng: tuple, popup: Optional[str] = None,
                 tooltip: Optional[str] = None,
                 on_click: Optional[Callable] = None):
        self.latlng  = latlng
        self.popup   = popup
        self.tooltip = tooltip
        self._cid    = None
        if on_click:
            self._cid = _next_id()
            _reg(self._cid, on_click)

    def to_dict(self) -> dict:
        return {"latlng": list(self.latlng), "popup": self.popup,
                "tooltip": self.tooltip, "cid": self._cid}


class _Map(_Leaf):
    """
    Interactive Leaflet map. Requires internet for tile loading.
    User pan/zoom is preserved across re-renders.
    Always supply key= so the map instance persists correctly.

    Callbacks:
        on_click(lat, lon)        — user clicks the map background
        on_move(center, zoom)     — pan/zoom ends; center=(lat,lon), zoom=int
        on_shape(type, coords)    — shape drawn via draw tools;
                                    type: "rectangle"|"polygon"|"polyline"|
                                          "circle"|"marker"
                                    coords: list of [lat,lon] pairs for
                                            polygon/rectangle/polyline;
                                            {"lat","lng","radius"} for circle;
                                            {"lat","lng"} for marker
        Marker(..., on_click=fn)  — user clicks a specific marker

    Draw tools:
        draw=["rectangle","polygon"]  — enable specific tools
        draw=True                     — enable all tools
        draw=False / draw=[]          — no tools (default)
    """
    _DRAW_ALL = ["rectangle", "polygon", "polyline", "circle", "marker"]

    def __init__(self, *, center: tuple = (0.0, 0.0), zoom: int = 10,
                 height: int = 380, markers: Optional[list] = None,
                 on_click: Optional[Callable] = None,
                 on_move:  Optional[Callable] = None,
                 on_shape: Optional[Callable] = None,
                 draw: Any = False,
                 style: str = "", key: Optional[str] = None):
        self._center   = center
        self._zoom     = zoom
        self._height   = height
        self._markers  = markers or []
        self._on_click = on_click
        self._on_move  = on_move
        self._on_shape = on_shape
        self._style    = style

        # Normalise draw tools
        if draw is True:
            self._draw = self._DRAW_ALL[:]
        elif not draw:
            self._draw = []
        else:
            self._draw = [t for t in draw if t in self._DRAW_ALL]

        super().__init__(key)

        # Use stable suffixed cids derived from self.id (stable because key= is set).
        if on_click:
            self._on_click_cid = self.id + "-click"
            _reg(self._on_click_cid,
                 lambda v: on_click(v["lat"], v["lng"]))
        else:
            self._on_click_cid = None

        if on_move:
            self._on_move_cid = self.id + "-move"
            _reg(self._on_move_cid,
                 lambda v: on_move(tuple(v["center"]), int(v["zoom"])))
        else:
            self._on_move_cid = None

        if on_shape:
            self._on_shape_cid = self.id + "-shape"
            _reg(self._on_shape_cid,
                 lambda v: on_shape(v["type"], v["coords"]))
        else:
            self._on_shape_cid = None

    def render(self) -> str:
        import json
        cfg = {
            "center":       list(self._center),
            "zoom":         self._zoom,
            "markers":      [m.to_dict() if isinstance(m, Marker) else m
                             for m in self._markers],
            "on_click_cid": self._on_click_cid,
            "on_move_cid":  self._on_move_cid,
            "on_shape_cid": self._on_shape_cid,
            "draw":         self._draw,
        }
        cfg_json = _esc(json.dumps(cfg))
        return (f'<div id="{self.id}" class="guile-map"'
                f' data-guile-map="{cfg_json}"'
                f' style="{self._style}">'
                f'<div class="guile-map-canvas"'
                f' style="height:{self._height}px"></div></div>')




# ── Modal dialog ────────────────────────────────────────────────────────────

class _Modal(_Container):
    """
    Blocking modal dialog. Renders a full-screen overlay with a centred card.
    Use as a context manager — put any guile widgets inside, including buttons.

    When visible=False the modal is not rendered (zero DOM footprint).
    Always supply on_close= so the backdrop click and ✕ button work.

        confirm = gui.state(False)

        with gui.modal("Delete sample?",
                       visible=confirm.value,
                       on_close=lambda: confirm.set(False)):
            gui.text("This cannot be undone.")
            with gui.row(gap=8, justify="flex-end"):
                gui.button("Cancel", on_click=lambda: confirm.set(False))
                gui.button("Delete", variant="danger", on_click=do_delete)
    """
    def __init__(self, title: str = "", *,
                 visible: bool = True,
                 on_close: Optional[Callable] = None,
                 width: int = 420,
                 style: str = "",
                 key: Optional[str] = None):
        self._title    = title
        self._visible  = visible
        self._width    = width
        self._style    = style
        self._on_close = on_close
        super().__init__(css_class="guile-col", inline_style="", key=key)
        if on_close:
            _reg(self.id + "-close", lambda: on_close())

    def render(self) -> str:
        if not self._visible:
            return f'<div id="{self.id}" style="display:none"></div>'

        inner      = self._render_children()
        close_js   = (f"window._guile.trigger('{self.id}-close',null)"
                      if self._on_close else "")
        close_btn  = (f'<button onclick="{close_js}" '
                      f'style="background:none;border:none;cursor:pointer;'
                      f'font-size:18px;color:var(--text-2);padding:0;'
                      f'line-height:1">✕</button>') if self._on_close else ""
        title_html = (f'<div style="display:flex;justify-content:space-between;'
                      f'align-items:center;margin-bottom:16px">'
                      f'<span style="font-size:16px;font-weight:600">'
                      f'{_txt(self._title)}</span>{close_btn}</div>') if self._title else ""

        backdrop_onclick = (
            f' onclick="if(event.target===this){{{close_js}}}"'
            if close_js else ""
        )
        return (
            f'<div id="{self.id}"'
            f' style="position:fixed;inset:0;background:rgba(0,0,0,.45);'
            f'z-index:9998;display:flex;align-items:center;'
            f'justify-content:center;padding:24px;"'
            f'{backdrop_onclick}>'
            f'<div style="background:var(--surface);'
            f'border-radius:var(--r-lg);padding:24px;'
            f'width:100%;max-width:{self._width}px;'
            f'box-shadow:0 20px 60px rgba(0,0,0,.25);{self._style}"'
            f' onclick="event.stopPropagation()">'
            f'{title_html}'
            f'<div class="guile-col" style="gap:12px">{inner}</div>'
            f'</div></div>'
        )

# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — Theming
# ══════════════════════════════════════════════════════════════════════════

# Built-in theme presets.
# Each theme is defined by 8 core variables; all others are computed.
THEMES: dict = {
    "light": dict(
        primary="#6366f1", bg="#f2f2f7",  surface="#ffffff",
        surface_2="#f5f5f7", text="#1c1c1e", text_2="#6e6e73",
        border="#d1d1d6", radius=10,
    ),
    "dark": dict(
        primary="#818cf8", bg="#1c1c1e",  surface="#2c2c2e",
        surface_2="#3a3a3c", text="#f5f5f7", text_2="#98989f",
        border="#48484a", radius=10,
    ),
    "neon": dict(
        primary="#22d3ee", bg="#0f172a",  surface="#1e293b",
        surface_2="#334155", text="#f1f5f9", text_2="#94a3b8",
        border="#334155", radius=8,
    ),
    "rose": dict(
        primary="#f43f5e", bg="#fff1f2",  surface="#ffffff",
        surface_2="#ffe4e6", text="#1c1917", text_2="#78716c",
        border="#fecdd3", radius=12,
    ),
    "forest": dict(
        primary="#16a34a", bg="#f0fdf4",  surface="#ffffff",
        surface_2="#dcfce7", text="#14532d", text_2="#4d7c0f",
        border="#bbf7d0", radius=8,
    ),
    "slate": dict(
        primary="#64748b", bg="#f8fafc",  surface="#ffffff",
        surface_2="#f1f5f9", text="#0f172a", text_2="#64748b",
        border="#e2e8f0", radius=6,
    ),
}


def _compute_theme_css(primary, bg, surface, surface_2,
                       text, text_2, border, radius) -> str:
    """Derive all CSS variables from 8 core values."""
    import colorsys

    def _hex_rgb(h):
        h = h.lstrip("#")
        if len(h) == 3:                    # expand shorthand: #abc → aabbcc
            h = h[0]*2 + h[1]*2 + h[2]*2
        return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

    def _rgb_hex(r, g, b):
        return "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255))

    def _darken(h, amt=0.10):
        hls = colorsys.rgb_to_hls(*_hex_rgb(h))
        return _rgb_hex(*colorsys.hls_to_rgb(hls[0], max(0, hls[1] - amt), hls[2]))

    def _tint(h, opacity=0.15, over="#ffffff"):
        r1, g1, b1 = _hex_rgb(h)
        r2, g2, b2 = _hex_rgb(over)
        return _rgb_hex(
            r1 * opacity + r2 * (1 - opacity),
            g1 * opacity + g2 * (1 - opacity),
            b1 * opacity + b2 * (1 - opacity),
        )

    primary_h     = _darken(primary)
    primary_light = _tint(primary, 0.15, surface)

    # Status colours are fixed across all themes
    danger,  dl = "#ef4444", _tint("#ef4444", 0.15, surface)
    success, sl = "#22c55e", _tint("#22c55e", 0.15, surface)
    warning, wl = "#f59e0b", _tint("#f59e0b", 0.15, surface)

    r_sm = max(4, radius - 4)
    r_lg = radius + 6

    # Lighter shadow for light backgrounds, heavier for dark ones
    is_dark  = int(bg.lstrip("#")[:2], 16) < 100
    sh_alpha = "(.3),0 4px 14px rgba(0,0,0,.4)" if is_dark else "(.06),0 4px 14px rgba(0,0,0,.08)"
    
    return (
        f"--primary:{primary};--primary-h:{primary_h};"
        f"--primary-light:{primary_light};"
        f"--bg:{bg};--surface:{surface};--surface-2:{surface_2};"
        f"--text:{text};--text-2:{text_2};"
        f"--border:{border};--border-focus:{primary};"
        f"--danger:{danger};--danger-light:{dl};"
        f"--success:{success};--success-light:{sl};"
        f"--warning:{warning};--warning-light:{wl};"
        f"--r:{radius}px;--r-sm:{r_sm}px;--r-lg:{r_lg}px;"
        f"--shadow:0 1px 3px rgba(0,0,0{sh_alpha});"
        f"--shadow-sm:0 1px 2px rgba(0,0,0,.06);"
        f"--shadow-lg:0 8px 32px rgba(0,0,0,.12);"
    )
