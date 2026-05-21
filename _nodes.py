"""
guile._nodes — Internal render tree.

Thread-local stack of "current parent" nodes. When you enter
`with gui.card():` a Card node is pushed. Every gui.text(),
gui.button() etc. attaches itself to the current top automatically.
When the `with` block exits the node pops back to its parent.
"""

from __future__ import annotations
import threading
import html as _html
from typing import Any, Callable, List, Optional

# ── Thread-local render stack ──────────────────────────────────────────────
_local = threading.local()

def _stack() -> List["Node"]:
    if not hasattr(_local, "stack"):
        _local.stack = []
    return _local.stack

def _push(node: "Node"):   _stack().append(node)
def _pop()  -> "Node":     return _stack().pop()
def _current() -> Optional["Node"]:
    s = _stack(); return s[-1] if s else None

def _attach(node: "Node"):
    parent = _current()
    if parent is not None:
        parent.children.append(node)


# ── ID counter + dual-dict callback registry ───────────────────────────────
# _callbacks     — built fresh each render pass
# _live_callbacks — committed after each render; safe to read at any time
#                   (even mid-render) so clicks never miss their handler
_id_counter    = 0
_callbacks:      dict = {}
_live_callbacks: dict = {}

def _reset_render():
    """Clear ID counter and start a fresh callback table for this render."""
    global _id_counter
    _id_counter = 0
    _callbacks.clear()          # mutate in place — importers keep same reference

def _commit_callbacks():
    """Snapshot the just-built callbacks into _live_callbacks."""
    _live_callbacks.clear()
    _live_callbacks.update(_callbacks)

def _next_id(key: Optional[str] = None) -> str:
    global _id_counter
    if key:
        return f"gk-{key}"
    _id_counter += 1
    return f"g{_id_counter}"

def _reg(cid: str, fn: Callable):
    _callbacks[cid] = fn

def dispatch(cid: str, value: Any = None):
    """Call the live handler for cid, passing value if the handler accepts it."""
    fn = _live_callbacks.get(cid)
    if not fn:
        return
    try:
        # Try with value first; fall back to no-arg call for on_click lambdas
        try:
            fn(value)
        except TypeError:
            fn()
    except Exception:
        import traceback
        traceback.print_exc()


# ── HTML helpers ───────────────────────────────────────────────────────────
def _esc(s: Any) -> str:
    return _html.escape(str(s), quote=True)

def _txt(s: Any) -> str:
    return _html.escape(str(s))


# ── Base node ──────────────────────────────────────────────────────────────
class Node:
    """
    Base for all UI elements. Containers use __enter__/__exit__;
    leaves call _attach() on construction to join the current parent.
    """
    def __init__(self, key: Optional[str] = None):
        self.id       = _next_id(key)
        self.children: List[Node] = []

    def __enter__(self):
        _push(self); return self

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
