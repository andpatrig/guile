"""
guile._app — Window lifecycle and pywebview integration.

This file contains two classes:

  _App     — creates and manages the pywebview window, drives re-renders
  _Bridge  — the thin object exposed to JavaScript as window.pywebview.api

You don't need to read this file to use guile. It's called automatically
by the @gui.app() decorator in __init__.py.

The event flow for a button click:
    1. User clicks → JS calls window._guile.trigger(cid, value)
    2. JS calls window.pywebview.api.handle(cid, value)      [WebView thread]
    3. _Bridge.handle() puts the event on a queue and returns immediately
       (returning quickly is mandatory — blocking the WebView thread
       would deadlock evaluate_js, which also needs that thread)
    4. The single worker thread: dispatch(cid) → callback → State.set()
    5. State.set() queues a render request; the worker coalesces all
       pending requests into ONE _render() per drain of the queue
    6. _render() calls evaluate_js(js) to push new HTML to the browser
    7. JS patcher updates only the changed DOM nodes

Why one worker thread instead of one thread per event:
    Everything that touches the render machinery — dispatch, callbacks,
    State changes, ui() execution, the module-level callback registry in
    ui.py — runs on this one thread, serially. That removes by design a
    whole class of races (two events interleaving, _reset_render() firing
    mid-build on another thread) and makes render batching automatic: a
    callback that calls .set() five times queues five render requests,
    which the worker drains into a single render with all final values.
"""

from __future__ import annotations
import html
import json
import queue
import threading
import traceback
from typing import Callable, Optional

from .state import register as _reg_listener, unregister as _unreg_listener
from .ui import (
    Column,
    _reset_render, _commit_callbacks,
    dispatch as _dispatch, dispatch_silent as _dispatch_silent,
    _clear_state_store, _set_window,
)
from ._template import get_html


class _App:
    """
    Manages the pywebview window and the render loop.

    Created by @gui.app() — you never instantiate this directly.
    """

    # Class-level reference to the running app — used by gui.leaflet()
    # to set _use_leaflet=True before the window opens.
    _current: Optional["_App"] = None

    def __init__(self, title: str, *, width: int = 800, height: int = 600,
                 resizable: bool = False, center: bool = False,
                 debug: bool = False):
        self.title      = title
        self.width      = width
        self.height     = height
        self.resizable  = resizable
        self.center     = center
        self.debug      = debug
        self._build     = None   # the ui() function supplied by the user
        self._window    = None   # pywebview window object
        self._ready     = False  # True after the page finishes loading
        self._use_leaflet      = False  # set to True by gui.leaflet()
        self._use_leaflet_draw = False  # set to True by gui.leaflet(draw=...)

        # The single event queue. Items are tuples:
        #   ("event",  cid, value)  — user interaction → dispatch(cid, value)
        #   ("silent", cid, value)  — state update only, no render
        #   ("render", None, None)  — a State changed, re-render needed
        # One daemon worker drains it; see _worker_loop().
        self._queue = queue.Queue()
        threading.Thread(target=self._worker_loop, daemon=True,
                         name="guile-worker").start()

    def _make_root(self) -> Column:
        """
        Build the root container that wraps the user's ui().

        With center=True the root fills the window and centres its children
        on both axes — the same effect as wrapping everything in
        gui.col(align="center", justify="center", style="min-height:100vh"),
        but without the boilerplate. Handy for small single-card apps.
        """
        if self.center:
            return Column(fill=True, align="center", justify="center",
                          style="min-height:100vh")
        return Column(fill=True)

    def run(self, build_fn: Callable):
        """Start the app. Blocks until the window is closed."""
        try:
            import webview
        except ImportError:
            raise SystemExit(
                "[guile] pywebview is required but not installed.\n"
                "        Install it with:  pip install pywebview"
            )

        self._build = build_fn
        _App._current = self
        _reg_listener(self._rerender)  # re-render on every State change

        # Run ui() once before the window exists so flag-setting side effects
        # (e.g. gui.leaflet() → _use_leaflet) are captured before get_html()
        # picks which <script>/<link> tags to include. Any error here is
        # ignored on purpose: the first real _render() runs ui() again and
        # reports the error (console + in-window panel).
        try:
            _reset_render()
            root = self._make_root()
            root.__enter__()
            self._build()
            root.__exit__(None, None, None)
        except Exception:
            pass

        api = _Bridge(self)
        self._window = webview.create_window(
            title=self.title,
            html=get_html(self.title,
                          use_leaflet=self._use_leaflet,
                          use_leaflet_draw=self._use_leaflet_draw),
            js_api=api,
            width=self.width,
            height=self.height,
            resizable=self.resizable,
            background_color="#000000",  # overridden immediately by CSS
        )
        self._window.events.loaded += self._on_loaded
        self._window.events.closed += self._on_closed
        webview.start(debug=self.debug, http_server=False)

    # ── Window event handlers ──────────────────────────────────────────────

    def _on_loaded(self):
        """Fires when the HTML page finishes loading. Trigger first render."""
        self._ready = True
        _set_window(self._window)   # give _FilePicker access to the window
        self._queue.put(("render", None, None))

    def _on_closed(self):
        """Fires when the user closes the window. Clean up."""
        self._ready = False
        _set_window(None)
        _unreg_listener(self._rerender)
        _clear_state_store()
        from .ui import _Figure
        _Figure._cache.clear()   # static-figure cache dies with the window

    # ── Worker loop + render ──────────────────────────────────────────────

    def _rerender(self):
        """
        Queue a render request. Called on every State change, possibly from
        another thread; the worker coalesces bursts into a single render.
        (See the module docstring for why batching is automatic here.)
        """
        self._queue.put(("render", None, None))

    def _worker_loop(self):
        """
        The only thread that runs dispatch, callbacks, ui(), and evaluate_js.
        Drains the queue in batches: dispatch every event in arrival order,
        then render once if anything changed. Serial by design — no locks.
        """
        while True:
            batch = [self._queue.get()]
            try:
                while True:                     # drain whatever else is queued
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                pass

            needs_render = False
            for kind, cid, value in batch:
                if kind == "event":
                    # .set() calls inside the callback queue "render" items
                    # that land in the next batch and coalesce into one render.
                    _dispatch(cid, value)
                elif kind == "silent":
                    _dispatch_silent(cid, value)
                elif kind == "render":
                    needs_render = True
            if needs_render:
                self._render()

    def _render(self):
        """
        Run ui(), serialize to HTML, and push it to the browser via
        evaluate_js. Only ever called from the worker thread, so renders
        are serial by construction — no re-entrancy guard needed.

        Note: ui() must not call state.set() unconditionally — every render
        would queue another render, looping forever. Use on_change=/on_click=
        callbacks instead.
        """
        if not self._build or not self._window or not self._ready:
            return
        try:
            _reset_render()
            root = self._make_root()
            root.__enter__()
            self._build()
            root.__exit__(None, None, None)
            _commit_callbacks()
            js = f"window._guile.update({json.dumps(root.render())})"
            self._window.evaluate_js(js)
        except Exception:
            self._show_error(traceback.format_exc())

    def _show_error(self, tb: str):
        """
        A ui() error would otherwise leave a blank window. Print the
        traceback and also render it into the page, so a typo is visible
        where you're looking instead of only in the terminal.
        """
        traceback.print_exc()
        panel = ('<pre style="margin:16px;padding:16px;overflow:auto;'
                 'font:13px/1.5 monospace;color:#b91c1c;background:#fef2f2;'
                 'border:1px solid #fecaca;border-radius:8px">'
                 + html.escape(tb) + '</pre>')
        try:
            self._window.evaluate_js(
                "document.getElementById('guile-app').innerHTML="
                + json.dumps(panel))
        except Exception:
            pass


class _Bridge:
    """
    Exposed to JavaScript as window.pywebview.api.

    IMPORTANT: Method names must NOT start with underscore.
    pywebview silently filters underscore methods from the JS API,
    making them unreachable from JavaScript.

    Public methods: handle() for events, silent_update() for
    render-free state updates. Both just enqueue and return — all real
    work happens on the app's single worker thread, which also keeps
    events and silent updates in arrival order (a multiselect's silent
    onchange is guaranteed to apply before its onblur render).
    """

    def __init__(self, app: _App):
        self._app = app

    def handle(self, cid: str, value=None):
        """
        Called by JS when the user interacts with a widget.
        Must return immediately — doing work here blocks the WebView
        message thread, which would deadlock evaluate_js().
        """
        self._app._queue.put(("event", cid, value))

    def silent_update(self, cid: str, value=None):
        """
        Called by JS to update state without triggering a re-render.
        Used by multiselect (and text inputs) while the user is
        mid-interaction: state stays current, DOM is left alone.
        """
        self._app._queue.put(("silent", cid, value))
