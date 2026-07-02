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
    3. _Bridge.handle() spawns a daemon thread and returns immediately
       (returning quickly is mandatory — blocking the WebView thread
       would deadlock evaluate_js, which also needs that thread)
    4. Daemon thread: dispatch(cid) → callback → State.set() → _render()
    5. _render() calls evaluate_js(js) to push new HTML to the browser
    6. JS patcher updates only the changed DOM nodes
"""

from __future__ import annotations
import json
import threading
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
        self._rendering        = False  # True while a render is in progress
        self._needs_render     = False  # True if a render arrived while busy

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
        self._build = build_fn
        _App._current = self
        _reg_listener(self._rerender)  # re-render on every State change

        # Run ui() once before the window exists so flag-setting side effects
        # (e.g. gui.leaflet() → _use_leaflet) are captured before get_html()
        # decides which <script>/<link> tags to include. Errors are swallowed;
        # the real render surfaces them later.
        try:
            _reset_render()
            root = self._make_root()
            root.__enter__()
            self._build()
            root.__exit__(None, None, None)
        except Exception:
            pass

        try:
            import webview
        except ImportError:
            print("[guile] pywebview not installed — opening in browser instead.")
            print("[guile] Install for desktop window:  pip install pywebview")
            self._fallback_browser()
            return

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
        self._render()

    def _on_closed(self):
        """Fires when the user closes the window. Clean up."""
        self._ready = False
        _set_window(None)
        _unreg_listener(self._rerender)
        _clear_state_store()

    # ── Render ────────────────────────────────────────────────────────────

    def _rerender(self):
        """Called by State whenever a value changes."""
        if self._ready:
            self._render()

    def _render(self):
        """
        Run ui(), serialize to HTML, and push it to the browser via evaluate_js.

        A render that arrives mid-render sets _needs_render instead of
        recursing; the loop then runs at most once more. Note: ui() must not
        call state.set() unconditionally — that would fire _rerender() during
        a render and loop forever. Use on_change=/on_click= callbacks instead.
        """
        if not self._build or not self._window or not self._ready:
            return
        if self._rendering:
            self._needs_render = True
            return
        while True:
            self._rendering    = True
            self._needs_render = False
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
                import traceback
                traceback.print_exc()
            finally:
                self._rendering = False
            # One follow-up render is enough to absorb a state change that
            # arrived mid-render; a second would risk an infinite loop.
            if self._needs_render:
                self._needs_render = False
            else:
                break

    # ── Browser fallback ───────────────────────────────────────────────────

    def _fallback_browser(self):
        """
        When pywebview is not installed: serve the app via a local HTTP server
        and open it in the default browser. Good for development.
        """
        import http.server, webbrowser, socket

        s = socket.socket()
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()
        app_ref = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body = get_html(app_ref.title,
                                    use_leaflet=app_ref._use_leaflet,
                                    use_leaflet_draw=app_ref._use_leaflet_draw).encode()
                else:
                    _reset_render()
                    root = app_ref._make_root()
                    root.__enter__()
                    app_ref._build()
                    root.__exit__(None, None, None)
                    _commit_callbacks()
                    body = root.render().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                data   = json.loads(self.rfile.read(length))
                _dispatch(data["cid"], data.get("value"))
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, *_):
                pass

        srv = http.server.HTTPServer(("localhost", port), _Handler)
        url = f"http://localhost:{port}/"
        print(f"[guile] dev mode → {url}")
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        srv.serve_forever()


class _Bridge:
    """
    Exposed to JavaScript as window.pywebview.api.

    IMPORTANT: Method names must NOT start with underscore.
    pywebview silently filters underscore methods from the JS API,
    making them unreachable from JavaScript.

    Only public methods here: handle() for events.
    """

    def __init__(self, app: _App):
        self._app = app

    def handle(self, cid: str, value=None):
        """
        Called by JS when the user interacts with a widget.
        Must return immediately — doing work here blocks the WebView
        message thread, which would deadlock evaluate_js().
        All real work happens on a daemon thread.
        """
        threading.Thread(
            target=self._run, args=(cid, value), daemon=True
        ).start()

    def silent_update(self, cid: str, value=None):
        """
        Called by JS to update state without triggering a re-render.
        Used by multiselect onchange: state is updated immediately on
        every click so it's always current, but the DOM is only replaced
        on onblur (via the normal handle() path) after the user finishes.
        """
        threading.Thread(
            target=_dispatch_silent, args=(cid, value), daemon=True
        ).start()

    def _run(self, cid: str, value):
        """Dispatch the event and re-render. Runs on a background thread."""
        _dispatch(cid, value)
        self._app._render()
