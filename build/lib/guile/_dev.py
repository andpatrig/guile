"""
guile._dev — hot reload for development (gui.run(dev=True)).

How it works:

  1. A daemon thread polls the app script's modification time (~2x/second).
     stdlib only — no file-watcher dependency.
  2. When the file changes, the watcher does NOT reload anything itself.
     It enqueues the reload as a ("call", fn, None) item on the app's
     worker queue — the same delivery mechanism gui.task() uses — so the
     reload runs on the worker thread, serialized with callbacks and
     renders. No races by construction.
  3. The reload re-executes the script's source with gui.run patched to
     raise _ReloadStop, so execution halts at the gui.run() line: code
     after gui.run() (save-on-exit etc.) does not fire mid-session.
  4. The freshly registered ui() function is swapped into the running
     _App, the widget-state store is cleared, and a render is queued
     into the OPEN window. The window never closes.

Semantics — each reload is a fresh start: module-level code re-runs and
gui.state() values reset to their initial values, exactly as if you had
re-run the script, except the window stays put. There is deliberately no
state-migration magic.

Errors: a SyntaxError or crash during re-execution shows in the
in-window error panel; the previous UI keeps running and the watcher
keeps watching, so you just fix the file and save again.
"""

from __future__ import annotations

import os
import threading
import time
import traceback


class _ReloadStop(Exception):
    """Raised by the patched gui.run() to halt script re-execution at the
    gui.run() line during a dev reload."""


def _execute(path: str):
    """
    Re-run the user's script from source, stopping at gui.run().
    Returns the freshly registered (ui_fn, config) from @gui.app.
    Raises on syntax errors or exceptions in the script's module code.
    """
    import guile as gui

    with open(path, encoding="utf-8") as f:
        src = f.read()
    code = compile(src, path, "exec")      # SyntaxError propagates

    def _stop(*_a, **_kw):
        raise _ReloadStop

    orig_run = gui.run
    gui.run = _stop
    try:
        # __name__ == "__main__" so the script runs exactly as it does
        # from the command line (if __name__ == "__main__" guards included).
        ns = {"__name__": "__main__", "__file__": path}
        try:
            exec(code, ns)
        except _ReloadStop:
            pass
    finally:
        gui.run = orig_run
        gui._run_called = True             # keep the atexit hint quiet

    if gui._pending_app is None:
        raise RuntimeError(
            f"Reloaded script defines no @gui.app function: {path}")
    return gui._pending_app


def reload_app(app, path: str) -> None:
    """
    Swap the running app for the current contents of `path`.
    Runs on the worker thread (delivered via a "call" queue item), so it
    cannot interleave with a callback or a render.
    """
    import guile as gui
    from .ui import _clear_state_store

    try:
        fn, cfg = _execute(path)
    except Exception:
        # Bad save: show the error in the window, keep the old UI alive.
        app._show_error(traceback.format_exc())
        return

    app._build = fn
    _clear_state_store()                   # fresh start for widget state

    # Apply window title/size changes from the @gui.app() line, best-effort.
    try:
        if app._window is not None:
            if cfg["title"] != app.title:
                app.title = cfg["title"]
                app._window.set_title(cfg["title"])
            if (cfg["width"], cfg["height"]) != (app.width, app.height):
                app.width, app.height = cfg["width"], cfg["height"]
                app._window.resize(cfg["width"], cfg["height"])
    except Exception:
        pass

    app._queue.put(("render", None, None))
    try:
        gui.notify(f"Reloaded {os.path.basename(path)}",
                   variant="primary", duration=2)
    except Exception:
        pass


def start_watcher(app, path: str, interval: float = 0.5) -> None:
    """Start the mtime-polling daemon thread for `path`."""
    path = os.path.abspath(path)

    def _loop():
        try:
            last = os.path.getmtime(path)
        except OSError:
            last = 0.0
        while True:
            time.sleep(interval)
            try:
                m = os.path.getmtime(path)
            except OSError:
                continue                   # editor mid-save; retry next tick
            if m != last:
                last = m
                app._queue.put(("call", lambda: reload_app(app, path), None))

    threading.Thread(target=_loop, daemon=True,
                     name="guile-dev-watch").start()
    print(f"[guile] dev mode - watching {path} (save the file to reload; "
          f"state resets to initial values on each reload)")
