"""
guile.state — Reactive value containers.

Two flavours:
  state(value)           — explicit, like React useState
  [auto via gui.input()]  — inputs return their own internal State

Setting .value or calling .set() fires all registered listeners.
"""

from __future__ import annotations
import threading
from typing import Any, Callable, List

_listeners: List[Callable] = []
_lock = threading.Lock()


def _fire():
    with _lock:
        fns = list(_listeners)
    for fn in fns:
        try:
            fn()
        except Exception as e:
            print(f"[guile] listener error: {e}")


def register(fn: Callable):
    with _lock:
        if fn not in _listeners:
            _listeners.append(fn)


def unregister(fn: Callable):
    with _lock:
        if fn in _listeners:
            _listeners.remove(fn)


class State:
    """
    Reactive value. Setting .value triggers a re-render.

        count = gui.state(0)
        count.set(count.value + 1)
        count.update(lambda x: x + 1)

    Always read through .value — for comparisons and arithmetic too:

        if count.value > 0: ...
        total = price.value * qty.value
    """

    def __init__(self, initial: Any):
        self._v = initial

    @property
    def value(self) -> Any:
        return self._v

    @value.setter
    def value(self, new: Any):
        self._v = new
        _fire()

    def set(self, new: Any):
        self.value = new

    def set_silent(self, new: Any):
        """Update value without firing listeners or triggering a re-render.
        Used internally by multiselect to keep state current mid-selection.
        """
        self._v = new

    def update(self, fn: Callable):
        self.value = fn(self._v)

    def toggle(self):
        """Shorthand for boolean state."""
        self.value = not self._v

    # ── Display ────────────────────────────────────────────────────────────
    # str() shows the value so gui.text(my_state) and print(my_state) stay
    # readable; repr() makes the wrapper visible for debugging.
    def __str__(self):      return str(self._v)
    def __repr__(self):     return f"State({self._v!r})"

    # ── One rule: read the value through .value ────────────────────────────
    # Earlier versions proxied comparison and arithmetic operators so that
    # `count > 0` worked without .value. That shortcut was removed in 0.7:
    # it silently broke for numpy arrays and DataFrames ("truth value is
    # ambiguous"), and made State objects behave inconsistently in dicts
    # and sets. Now there is a single rule with no exceptions:
    #
    #     if count.value > 0: ...          not:  if count > 0
    #     total = price.value * qty.value  not:  price * qty
    #
    # Comparing or operating on a State object directly raises TypeError,
    # which points at the exact line to fix.
    def __bool__(self):
        # Without this, `if my_state:` would be silently True forever —
        # worse than an error. Raise with guidance instead (same approach
        # pandas takes for ambiguous truth values).
        raise TypeError(
            "State objects have no truth value. Use .value instead: "
            "`if my_state.value:`"
        )

    def __eq__(self, other):
        # Python's default would silently compare identity (`state == 5`
        # → False, always), which is a stealth bug for code migrating
        # from the old proxy behaviour. Raise with guidance instead.
        # `state is None` / `is not None` are unaffected.
        raise TypeError(
            "Compare the value, not the State object: "
            "`my_state.value == x`"
        )

    def __ne__(self, other):
        raise TypeError(
            "Compare the value, not the State object: "
            "`my_state.value != x`"
        )

    # Defining __eq__ would otherwise disable hashing; keep identity
    # hashing so States can still be dict keys / set members.
    __hash__ = object.__hash__
