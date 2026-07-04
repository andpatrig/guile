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

    # ── Transparent proxy operators ────────────────────────────────────────
    def __str__(self):      return str(self._v)
    def __repr__(self):     return f"State({self._v!r})"
    def __int__(self):      return int(self._v)
    def __float__(self):    return float(self._v)
    def __bool__(self):     return bool(self._v)
    def __len__(self):      return len(self._v)
    def __iter__(self):     return iter(self._v)
    def __contains__(self, item): return item in self._v
    def __getitem__(self, k):     return self._v[k]
    def __add__(self, o):   return self._v + (o._v if isinstance(o, State) else o)
    def __radd__(self, o):  return (o._v if isinstance(o, State) else o) + self._v
    def __sub__(self, o):   return self._v - (o._v if isinstance(o, State) else o)
    def __rsub__(self, o):  return (o._v if isinstance(o, State) else o) - self._v
    def __mul__(self, o):   return self._v * (o._v if isinstance(o, State) else o)
    def __truediv__(self, o): return self._v / (o._v if isinstance(o, State) else o)
    def __eq__(self, o):    return self._v == (o._v if isinstance(o, State) else o)
    def __lt__(self, o):    return self._v <  (o._v if isinstance(o, State) else o)
    def __gt__(self, o):    return self._v >  (o._v if isinstance(o, State) else o)
    def __le__(self, o):    return self._v <= (o._v if isinstance(o, State) else o)
    def __ge__(self, o):    return self._v >= (o._v if isinstance(o, State) else o)
    def __hash__(self):     return id(self)
    def __neg__(self):      return -self._v
    def __abs__(self):      return abs(self._v)
    def __mod__(self, o):   return self._v % (o._v if isinstance(o, State) else o)
