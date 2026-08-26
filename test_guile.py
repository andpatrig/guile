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


def test_set_in_ui_is_caught_not_looped():
    """A .set() inside ui() must not render forever: the loop is broken and a
    clear error panel is shown instead."""
    bad = gui.state("x")
    def build():
        bad.set("y")                 # the footgun: state change during render
        gui.text("hi")

    app = make_app(build)
    with contextlib.redirect_stderr(io.StringIO()):   # swallow the printed tb
        app._queue.put(("render", None, None))
        drain(app)

    # No successful render was pushed, and an error panel naming ui() was.
    assert app._window.render_count() == 0, \
        f"expected no runaway renders, got {app._window.render_count()}"
    panels = [c for c in app._window.calls
              if "innerHTML" in c and "inside ui()" in c]
    assert panels, "set() in ui() did not surface an error panel"
    return "loop prevented, error shown"


def test_task_keeps_ui_responsive():
    """gui.task runs work off the worker thread: clicks are handled while
    the task runs; on_done, on_error and busy land back on the worker."""
    gate    = threading.Event()
    started = threading.Event()
    busy    = gui.state(False)
    result  = gui.state(None)
    clicks  = []

    def slow():
        started.set()
        gate.wait(2.0)
        return 42

    def build():
        gui.button("go", key="go", on_click=lambda: gui.task(
            slow, on_done=result.set, busy=busy))
        gui.button("ping", key="ping", on_click=lambda: clicks.append(1))

    app = make_app(build)
    bridge = _Bridge(app)
    app._queue.put(("render", None, None)); drain(app)

    bridge.handle("gk-go", None)
    assert started.wait(2.0), "task never started"
    drain(app)
    assert busy.value is True, "busy flag not set while task runs"

    bridge.handle("gk-ping", None)          # click while the task is running
    drain(app)
    assert clicks == [1], "UI event was not handled while task ran"

    gate.set()
    deadline = time.time() + 2.0
    while time.time() < deadline and result.value != 42:
        time.sleep(0.01)
    drain(app)
    assert result.value == 42, f"on_done not delivered: {result.value}"
    assert busy.value is False, "busy flag not cleared after task"

    errors = []
    gui.task(lambda: 1 / 0, on_error=lambda e: errors.append(type(e).__name__))
    deadline = time.time() + 2.0
    while time.time() < deadline and not errors:
        time.sleep(0.01)
    drain(app)
    assert errors == ["ZeroDivisionError"], f"on_error not delivered: {errors}"
    return "clicks handled mid-task; on_done, on_error, busy delivered"


def test_dev_hot_reload():
    """Saving a changed script swaps ui() into the open window, resets
    state, stops at gui.run() (after-run code must NOT execute), and a
    broken save shows an error while keeping the old UI alive."""
    import tempfile
    from guile import _dev

    V1 = (
        "import guile as gui\n"
        "count = gui.state(1)\n"
        "@gui.app('T')\n"
        "def ui():\n"
        "    gui.text(f'version-one-{count.value}')\n"
        "gui.run()\n"
        "raise RuntimeError('after-run code executed during reload')\n"
    )
    V2 = V1.replace("version-one", "version-two").replace("gui.state(1)",
                                                          "gui.state(7)")
    V_BROKEN = "def oops(:\n"

    fd, path = tempfile.mkstemp(suffix=".py")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(V1)

        fn1, _cfg = _dev._execute(path)     # would raise if after-run ran
        app = make_app(fn1)
        app._queue.put(("render", None, None)); drain(app)
        assert "version-one-1" in app._window.calls[-1]

        with open(path, "w", encoding="utf-8") as f:
            f.write(V2)
        with contextlib.redirect_stdout(io.StringIO()):
            _dev.reload_app(app, path)      # what the watcher enqueues
        drain(app)
        renders = [c for c in app._window.calls
                   if c.startswith("window._guile.update")]
        assert "version-two-7" in renders[-1], "reload did not swap ui()"

        with open(path, "w", encoding="utf-8") as f:
            f.write(V_BROKEN)
        with contextlib.redirect_stderr(io.StringIO()):
            _dev.reload_app(app, path)
        drain(app)
        assert any("innerHTML" in c and "SyntaxError" in c
                   for c in app._window.calls), "broken save showed no error"
        assert app._build is not fn1 and app._build is not None
        # old UI still renderable after the bad save
        app._queue.put(("render", None, None)); drain(app)
        renders = [c for c in app._window.calls
                   if c.startswith("window._guile.update")]
        assert "version-two-7" in renders[-1], "old UI lost after bad save"
    finally:
        os.unlink(path)
        gui._pending_app = None             # don't leak into other tests
    return "swap + state reset + stop-at-run + broken-save recovery"


CORE_TESTS = [
    test_batching_one_render,
    test_no_double_dispatch_on_typeerror,
    test_concurrent_events_serialize,
    test_silent_then_render_order,
    test_build_error_surfaces_in_window,
    test_set_in_ui_is_caught_not_looped,
    test_task_keeps_ui_responsive,
    test_dev_hot_reload,
]


# ── PART 2: example smoke tests ─────────────────────────────────────────────

def load_example(path):
    """Import an example with gui.run() stubbed so no window opens.
    Since 0.7 the @gui.app decorator only registers the app, so it needs
    no patching — importing an example is safe by design; only the
    explicit gui.run() call at the bottom must be neutralised."""
    def _fake_run(*_a, **_kw):    # accept run()'s signature, e.g. dev=True
        gui._run_called = True    # keep the atexit "forgot gui.run()?" hint quiet
    orig_run = gui.run
    gui.run  = _fake_run
    try:
        mod = types.ModuleType("_ex")
        mod.__file__ = path
        src = open(path, encoding="utf-8").read()
        # Suppress import-time prints (e.g. the after-run summary in
        # field_notes.py, which executes here because gui.run is stubbed).
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(src, path, "exec"), mod.__dict__)
    finally:
        gui.run = orig_run
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
    """Static warning: a .set()/.update()/.toggle() executed directly inside
    ui() runs on every render, and under the worker each render queues another
    render — an infinite loop. Inside a lambda or nested def (an on_click/
    on_change callback) it's fine, since callbacks only run on user
    interaction. AST-based so multi-line lambdas don't false-positive."""
    import ast

    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    def _is_gui_app_decorated(fn):
        for dec in fn.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "app":
                return True
            if isinstance(target, ast.Name) and target.id == "app":
                return True
        return False

    def _walk_own_body(node):
        """Walk descendants, but never descend into lambdas or nested defs —
        code there only runs when the callback fires, not during render."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Lambda, ast.FunctionDef,
                                  ast.AsyncFunctionDef)):
                continue
            yield child
            yield from _walk_own_body(child)

    lines  = src.splitlines()
    issues = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and _is_gui_app_decorated(node)):
            continue
        for sub in _walk_own_body(node):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr in ("set", "update", "toggle",
                                          "set_silent")):
                snippet = lines[sub.lineno - 1].strip()[:80]
                issues.append(f"line {sub.lineno}: {snippet}")
    return issues


EXAMPLES = [
    "counter.py",
    "todo.py",
    "settings.py",
    "soils_lab.py",
    "soil_water_retention.py",
    "field_notes.py",
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
