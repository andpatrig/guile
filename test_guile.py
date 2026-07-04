"""
Headless tests for the guile worker-queue refactor.

No real WebView: we swap in a fake window that just records every
evaluate_js() call. That lets us count how many renders a sequence of
events produces and in what order state was applied — which is exactly
what the batching and race fixes are about.
"""
import sys, time, threading
sys.path.insert(0, ".")

import guile as gui
from guile._app import _App, _Bridge


class FakeWindow:
    """Stand-in for the pywebview window. Records evaluate_js payloads."""
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()
    def evaluate_js(self, js):
        with self._lock:
            self.calls.append(js)
    def render_count(self):
        # every _render() emits exactly one window._guile.update(...) call
        return sum(1 for c in self.calls if c.startswith("window._guile.update"))


def make_app(build_fn):
    """Wire an _App to a fake window and mark it ready, without a real WebView."""
    # Isolation: clear any listeners/state left by a previous test, so stale
    # apps don't steal render requests off the shared module-level registry.
    # (importlib because the state() function in __init__ shadows the
    # state submodule as an attribute of the package.)
    import importlib
    _state = importlib.import_module("guile.state")
    from guile.ui import _clear_state_store
    with _state._lock:
        _state._listeners.clear()
    _clear_state_store()

    app = _App("test")
    app._build  = build_fn
    app._window = FakeWindow()
    app._ready  = True
    _App._current = app
    _state.register(app._rerender)
    return app


def drain(app, timeout=2.0):
    """Block until the worker has emptied the queue."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app._queue.empty():
            time.sleep(0.02)          # let the worker finish the last batch
            if app._queue.empty():
                return
        time.sleep(0.005)
    raise TimeoutError("queue did not drain")


# ── Test 1: the soil-water scenario — 5 .set() calls → 1 render ────────────
def test_batching_one_render():
    soil = gui.state("Sandy loam")
    a = gui.state(0.0); b = gui.state(0.0); c = gui.state(0.0); d = gui.state(0.0)

    def sync(name):
        soil.set(name)
        a.set(0.045); b.set(0.430); c.set(0.145); d.set(2.68)

    def build():
        gui.select(["Sand", "Sandy loam"], value=soil,
                   key="soil", on_change=sync)

    app = make_app(build)
    bridge = _Bridge(app)

    app._queue.put(("render", None, None))   # initial render
    drain(app)
    base = app._window.render_count()
    assert base == 1, f"expected 1 initial render, got {base}"

    # Simulate the dropdown change arriving from JS
    bridge.handle("gk-soil", "Sand")
    drain(app)

    renders = app._window.render_count() - base
    assert renders == 1, f"dropdown change caused {renders} renders, expected 1"
    assert (a.value, b.value, c.value, d.value) == (0.045, 0.430, 0.145, 2.68)
    print(f"test_batching_one_render: OK (1 render, all 5 values applied)")


# ── Test 2: callback that raises TypeError runs exactly once ───────────────
def test_no_double_dispatch_on_typeerror():
    calls = []
    def handler(value):
        calls.append(value)
        raise TypeError("simulated bug deep inside the callback")

    def build():
        gui.button("go", on_click=lambda: handler("x"), key="btn")

    app = make_app(build)
    bridge = _Bridge(app)
    app._queue.put(("render", None, None)); drain(app)

    # The handler raises on purpose; guile prints that traceback. Suppress
    # stderr just for this call so the expected noise doesn't look like a
    # failure — we're testing that the handler runs ONCE, not that it succeeds.
    import io, contextlib
    with contextlib.redirect_stderr(io.StringIO()):
        bridge.handle("gk-btn", None)
        drain(app)
    assert len(calls) == 1, f"handler ran {len(calls)} times, expected exactly 1"
    print("test_no_double_dispatch_on_typeerror: OK (ran once, no re-dispatch)")


# ── Test 3: many concurrent events never corrupt a render / never crash ────
def test_concurrent_events_serialize():
    counter = gui.state(0)
    def build():
        gui.text(str(counter.value))
        gui.button("inc", on_click=lambda: counter.update(lambda x: x + 1),
                   key="inc")

    app = make_app(build)
    bridge = _Bridge(app)
    app._queue.put(("render", None, None)); drain(app)

    N = 200
    threads = [threading.Thread(target=bridge.handle, args=("gk-inc", None))
               for _ in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()
    drain(app)

    assert counter.value == N, f"lost updates: counter={counter.value}, expected {N}"
    # every recorded render payload must be valid (non-empty update call)
    for c in app._window.calls:
        assert c.startswith("window._guile.update("), "corrupt render payload"
    print(f"test_concurrent_events_serialize: OK ({N} events, no lost updates, "
          f"{app._window.render_count()} renders)")


# ── Test 4: silent update applies before the following render ──────────────
def test_silent_then_render_order():
    sel = gui.state([])
    def build():
        gui.multiselect(["a", "b", "c"], value=sel, key="ms")

    app = make_app(build)
    bridge = _Bridge(app)
    app._queue.put(("render", None, None)); drain(app)

    bridge.silent_update("gk-ms", '["a","b"]')   # onchange, no render
    bridge.handle("gk-ms", '["a","b"]')          # onblur, render
    drain(app)
    assert sel.value == ["a", "b"], f"got {sel.value}"
    print("test_silent_then_render_order: OK (silent applied, then rendered)")


# ── Test 5: a broken ui() shows an error panel, not a blank window ─────────
def test_build_error_surfaces_in_window():
    def build():
        raise ValueError("typo in the user's layout code")

    app = make_app(build)
    import io, contextlib
    with contextlib.redirect_stderr(io.StringIO()):   # swallow the printed tb
        app._queue.put(("render", None, None))
        drain(app)

    # The failed render should have pushed an innerHTML error panel.
    panels = [c for c in app._window.calls
              if "innerHTML" in c and "typo in the user" in c]
    assert panels, "broken ui() did not surface an error panel in the window"
    print("test_build_error_surfaces_in_window: OK (error shown, not blank)")


if __name__ == "__main__":
    test_batching_one_render()
    test_no_double_dispatch_on_typeerror()
    test_concurrent_events_serialize()
    test_silent_then_render_order()
    test_build_error_surfaces_in_window()
    print("\nAll tests passed.")
