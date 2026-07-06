"""
test_guile.py — combined test suite for the guile framework.

Run from the project root:
    python test_guile.py

Two layers, run in order:

  PART 1 — core unit tests
    Drive the worker-queue directly through a fake window that just records
    evaluate_js() calls. No real WebView. These pin down the behaviours the
    batching/threading refactor was about: one render per burst, exactly-once
    dispatch, safe concurrency, silent-before-render ordering, and errors
    surfacing in the window instead of a blank page.

  PART 2 — example smoke tests
    Import each example with @gui.app stubbed out, render its ui(), and
    dispatch every registered callback with a range of plausible values.
    Catches crashes and runaway renders in real app code. A static check
    also warns if an example calls .set() directly in ui() (see the note in
    check_for_set_in_ui — that pattern re-renders forever under the worker).
"""

import sys, os, io, time, threading, contextlib, importlib, importlib.util, types

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

import matplotlib
matplotlib.use("Agg")          # examples import matplotlib; keep it headless

import guile as gui
from guile._app import _App, _Bridge
from guile.ui import (
    Column, _reset_render, _commit_callbacks,
    _live_callbacks, dispatch, _state_store,
)

# The state() function in guile/__init__ shadows the state submodule as a
# package attribute, so reach the module (with its _lock / _listeners) via
# importlib rather than `guile.state`.
_state = importlib.import_module("guile.state")


# ── Shared helpers ──────────────────────────────────────────────────────────

class FakeWindow:
    """Stand-in for the pywebview window. Records evaluate_js payloads."""
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def evaluate_js(self, js):
        with self._lock:
            self.calls.append(js)

    def render_count(self):
        # Each _render() emits exactly one window._guile.update(...) call.
        return sum(1 for c in self.calls if c.startswith("window._guile.update"))


def reset_globals():
    """Clear the module-level listener/state registries between tests, so a
    stale app can't steal render requests off the shared registry."""
    with _state._lock:
        _state._listeners.clear()
    _state_store.clear()


def make_app(build_fn):
    """Wire an _App to a fake window and mark it ready, without a real WebView.
    Starts the app's worker thread (via _App.__init__), so events dispatched
    through the bridge are processed exactly as they are in production."""
    reset_globals()
    app = _App("test")
    app._build  = build_fn
    app._window = FakeWindow()
    app._ready  = True
    _App._current = app
    _state.register(app._rerender)
    return app


def drain(app, timeout=2.0):
    """Block until the worker has emptied the queue (best-effort)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app._queue.empty():
            time.sleep(0.02)          # let the worker finish the last batch
            if app._queue.empty():
                return
        time.sleep(0.005)
    raise TimeoutError("queue did not drain")


# ── PART 1: worker-queue core unit tests ────────────────────────────────────

def test_batching_one_render():
    """A callback that sets five states → a single render with all five."""
    soil = gui.state("Sandy loam")
    a = gui.state(0.0); b = gui.state(0.0); c = gui.state(0.0); d = gui.state(0.0)

    def sync(name):
        soil.set(name)
        a.set(0.045); b.set(0.430); c.set(0.145); d.set(2.68)

    def build():
        gui.select(["Sand", "Sandy loam"], value=soil, key="soil", on_change=sync)

    app = make_app(build)
    bridge = _Bridge(app)

    app._queue.put(("render", None, None))   # initial render
    drain(app)
    base = app._window.render_count()
    assert base == 1, f"expected 1 initial render, got {base}"

    bridge.handle("gk-soil", "Sand")         # dropdown change from JS
    drain(app)

    renders = app._window.render_count() - base
    assert renders == 1, f"dropdown change caused {renders} renders, expected 1"
    assert (a.value, b.value, c.value, d.value) == (0.045, 0.430, 0.145, 2.68)
    return "1 render, all 5 values applied"


def test_no_double_dispatch_on_typeerror():
    """A handler that raises TypeError internally must run exactly once
    (the old try fn(v)/except fn() shape could run it twice)."""
    calls = []
    def handler(value):
        calls.append(value)
        raise TypeError("simulated bug deep inside the callback")

    def build():
        gui.button("go", on_click=lambda: handler("x"), key="btn")

    app = make_app(build)
    bridge = _Bridge(app)
    app._queue.put(("render", None, None)); drain(app)

    with contextlib.redirect_stderr(io.StringIO()):   # swallow the expected tb
        bridge.handle("gk-btn", None)
        drain(app)
    assert len(calls) == 1, f"handler ran {len(calls)} times, expected exactly 1"
    return "ran once, no re-dispatch"


def test_concurrent_events_serialize():
    """Many events fired from many threads: no lost updates, no corrupt
    render payloads (the worker serialises everything)."""
    counter = gui.state(0)
    def build():
        gui.text(str(counter.value))
        gui.button("inc", on_click=lambda: counter.update(lambda x: x + 1), key="inc")

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
    for c in app._window.calls:
        assert c.startswith("window._guile.update("), "corrupt render payload"
    return f"{N} events, no lost updates, {app._window.render_count()} renders"


def test_silent_then_render_order():
    """A silent update (multiselect onchange) applies before the render that
    follows it (onblur), because the worker keeps arrival order."""
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
    return "silent applied, then rendered"


def test_build_error_surfaces_in_window():
    """A ui() that raises shows an error panel instead of a blank window."""
    def build():
        raise ValueError("typo in the user's layout code")

    app = make_app(build)
    with contextlib.redirect_stderr(io.StringIO()):
        app._queue.put(("render", None, None))
        drain(app)

    panels = [c for c in app._window.calls
              if "innerHTML" in c and "typo in the user" in c]
    assert panels, "broken ui() did not surface an error panel in the window"
    return "error shown, not blank"


CORE_TESTS = [
    test_batching_one_render,
    test_no_double_dispatch_on_typeerror,
    test_concurrent_events_serialize,
    test_silent_then_render_order,
    test_build_error_surfaces_in_window,
]


# ── PART 2: example smoke tests ─────────────────────────────────────────────

def load_example(path):
    """Import an example with @gui.app patched to a no-op and _App.run
    stubbed, so importing it never opens a window."""
    orig_app = gui.app
    orig_run = _App.run
    gui.app  = lambda *a, **kw: (lambda fn: fn)
    _App.run = lambda self, fn: None
    try:
        mod = types.ModuleType("_ex")
        mod.__file__ = path
        src = open(path, encoding="utf-8").read()
        exec(compile(src, path, "exec"), mod.__dict__)
    finally:
        gui.app  = orig_app
        _App.run = orig_run
    return mod


def render_ui(fn):
    """Run a ui() function once and return (html, live_callback_ids)."""
    _reset_render()
    root = Column(fill=True)
    root.__enter__()
    fn()
    root.__exit__(None, None, None)
    _commit_callbacks()
    return root.render(), list(_live_callbacks.keys())


def smoke(ui_fn):
    """Render ui(), then fire every callback with a range of fuzz values.

    This asserts *framework* robustness, not app correctness. Fuzz values are
    usually nonsense for a given widget ("hello" into a numeric slider, a bogus
    key into a colormap select), so the app's own code rejecting them — a
    KeyError in a dict lookup, a float() ValueError, an absent optional
    dependency in a file dialog — is expected and ignored. What we do care
    about is that the framework never recurses forever and that ui() builds.

    Returns (issues, n_callbacks); issues == [] means pass.
    """
    reset_globals()
    issues = []

    # Suppress the tracebacks guile prints when a handler rejects a fuzz value.
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        try:
            _, cids = render_ui(ui_fn)                 # initial render
        except RecursionError:
            return ["RecursionError during initial render"], 0
        except Exception as e:
            return [f"initial render failed: {type(e).__name__}: {e}"], 0

        fuzz = [None, "50", "0.5", "1", "true", "hello", "2024-06-01"]
        for cid in cids:
            for val in fuzz:
                try:
                    dispatch(cid, val)
                except RecursionError:
                    issues.append(f"RecursionError dispatching {cid!r}")
                    break
                except Exception:
                    pass                              # app rejected fuzz — fine

        try:
            render_ui(ui_fn)                           # tree still builds
        except RecursionError:
            issues.append("RecursionError on final render")
        except Exception:
            pass         # state may hold a fuzz value now; not a framework fault

    return issues, len(cids)


def check_for_set_in_ui(path):
    """Static warning: a bare .set() as a statement directly inside ui() runs
    on every render, and under the worker each render queues another render —
    an infinite loop. Inside a callback (lambda/on_click/on_change) it's fine,
    since callbacks only run on user interaction."""
    src = open(path, encoding="utf-8").read()
    if "@gui.app" not in src:
        return []

    lines = src[src.index("@gui.app"):].splitlines()
    issues = []
    in_ui  = False
    depth  = 0
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("def ui("):
            in_ui = True
            depth = len(line) - len(line.lstrip())
            continue
        if not in_ui:
            continue
        if len(line) - len(line.lstrip()) <= depth:      # dedent → left ui()
            in_ui = False
            continue
        if (".set(" in line and "lambda" not in line
                and "on_click" not in line and "on_change" not in line
                and "sync_" not in line
                and not stripped.startswith("def ")):
            issues.append(f"line {lineno}: {stripped[:80]}")
    return issues


EXAMPLES = [
    "01_counter.py",
    "02_todo.py",
    "03_settings.py",
    "06_soils_lab.py",
    "08_soil_water_retention.py",
]


# ── Runner ──────────────────────────────────────────────────────────────────

def main():
    passed = failed = 0

    print("=" * 60)
    print("guile — core unit tests")
    print("=" * 60)
    for test in CORE_TESTS:
        try:
            detail = test()
            print(f"  PASS  {test.__name__:38s} ({detail})")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__:38s} {type(e).__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print("guile — example smoke tests")
    print("=" * 60)
    examples_dir = os.path.join(_here, "examples")
    for fname in EXAMPLES:
        path = os.path.join(examples_dir, fname)
        if not os.path.exists(path):
            print(f"  SKIP  {fname:38s} (file not found)")
            continue

        for warn in check_for_set_in_ui(path):
            print(f"  WARN  {fname:38s} .set() in ui(): {warn}")

        try:
            mod = load_example(path)
        except Exception as e:
            print(f"  FAIL  {fname:38s} load error: {e}")
            failed += 1
            continue

        ui_fn = getattr(mod, "ui", None)
        if ui_fn is None:
            print(f"  SKIP  {fname:38s} (no ui() function)")
            continue

        issues, n_cb = smoke(ui_fn)
        if issues:
            print(f"  FAIL  {fname:38s}")
            for i in issues:
                print(f"          {i}")
            failed += 1
        else:
            print(f"  PASS  {fname:38s} ({n_cb} callbacks exercised)")
            passed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
