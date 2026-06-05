"""
test_smoke.py — End-to-end headless smoke tests for all guile examples.

Runs from the project root:
    python test_smoke.py

What it tests:
  - Each example's ui() function renders without crashing
  - Every registered callback can be dispatched without crashing
  - No RecursionError, no listener errors
  - Re-render after every dispatch succeeds
  - State mutations inside ui() don't cause infinite loops
"""

import sys, os, io, traceback, importlib.util, types
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

import matplotlib
matplotlib.use("Agg")

import guile as gui
from guile.ui import (
    Column, _reset_render, _commit_callbacks,
    _live_callbacks, dispatch, _state_store,
)
from guile._app import _App


# ── Helpers ────────────────────────────────────────────────────────────────

def load_example(path):
    """
    Import an example file with @gui.app patched to a no-op.
    Also patches _App.run and _App._fallback_browser so no window
    or HTTP server is ever started during testing.
    """
    from guile._app import _App
    orig_app     = gui.app
    orig_run     = _App.run
    orig_browser = _App._fallback_browser

    gui.app                = lambda *a, **kw: (lambda fn: fn)
    _App.run               = lambda self, fn: None
    _App._fallback_browser = lambda self: None

    spec = importlib.util.spec_from_file_location("_ex", path)
    mod  = types.ModuleType("_ex")
    mod.__file__ = path
    try:
        spec.loader.exec_module(mod)
    finally:
        gui.app                = orig_app
        _App.run               = orig_run
        _App._fallback_browser = orig_browser
    return mod


def render(fn):
    """Run ui() and return (html, callback_ids)."""
    _reset_render()
    root = Column(fill=True)
    root.__enter__()
    fn()
    root.__exit__(None, None, None)
    _commit_callbacks()
    html = root.render()
    return html, list(_live_callbacks.keys())


def smoke(name, ui_fn):
    """
    Exercise a ui() function:
      1. Initial render
      2. Dispatch every callback with several plausible values
      3. Re-render after each dispatch
    Returns list of issue strings (empty = pass).
    """
    issues = []
    _state_store.clear()

    # Capture output so we can scan for errors
    buf = io.StringIO()
    old_out = sys.stdout
    sys.stdout = buf

    try:
        html, cids = render(ui_fn)

        # Try dispatching each callback with plausible values
        # The first value that doesn't crash wins
        TRIAL_VALUES = [None, "50", "0.5", "true", "false",
                        "2024-06-01", "hello", "option1"]
        for cid in cids:
            dispatched = False
            for val in TRIAL_VALUES:
                try:
                    dispatch(cid, val)
                    render(ui_fn)   # re-render after dispatch
                    dispatched = True
                    break
                except RecursionError:
                    issues.append(f"RecursionError dispatching {cid!r}")
                    dispatched = True
                    break
                except Exception:
                    continue       # try next value

            if not dispatched:
                issues.append(f"All dispatch values failed for {cid!r}")

    except RecursionError:
        issues.append("RecursionError during initial render")
    except Exception as e:
        issues.append(f"{type(e).__name__}: {e}")
    finally:
        sys.stdout = old_out

    output = buf.getvalue()
    if "RecursionError" in output:
        issues.append("RecursionError printed to stdout")
    if "listener error" in output:
        issues.append(f"listener error: {output.strip()[:120]}")

    return issues


# ── Test: recursion guard ──────────────────────────────────────────────────

def test_recursion_guard():
    """ui() that unconditionally calls state.set() must not recurse forever."""
    bad = gui.state("x")
    renders = [0]

    def bad_ui():
        renders[0] += 1
        bad.set(bad.value)          # sets state during render — the dangerous pattern
        gui.text("test", key="t")

    app = _App.__new__(_App)
    app._build     = bad_ui
    app._window    = type("W", (), {"evaluate_js": lambda self, js: None})()
    app._ready     = True
    app._rendering = False
    app._needs_render = False
    app._render()

    assert renders[0] <= 2, f"recursion guard failed: {renders[0]} renders"
    return renders[0]


# ── Test: state.set() inside ui() detection ────────────────────────────────

def check_for_set_in_ui(path):
    """
    Warn if a bare .set() call appears as a statement directly inside ui()
    rather than inside a callback lambda.

    A .set() is only dangerous when it runs unconditionally on every render.
    Inside a lambda (on_click, on_change) it is fine — lambdas only run
    when triggered by user interaction.
    """
    src = open(path).read()
    if "@gui.app" not in src:
        return []

    after_decorator = src[src.index("@gui.app"):]
    issues = []
    in_ui   = False
    depth   = 0   # indentation depth relative to ui() body

    for lineno, line in enumerate(after_decorator.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("def ui("):
            in_ui = True
            depth = len(line) - len(line.lstrip())
            continue
        if not in_ui:
            continue
        # Dedent past ui() means we left the function
        cur_indent = len(line) - len(line.lstrip())
        if cur_indent <= depth and stripped:
            in_ui = False
            continue
        # Flag .set() only when it is a bare statement (not inside a lambda
        # and not part of an on_click / on_change / on_change= argument)
        if (".set(" in line
                and "lambda" not in line
                and "on_click" not in line
                and "on_change" not in line
                and "sync_" not in line       # helper function calls are fine
                and not stripped.startswith("def ")):
            issues.append(f"  line {lineno}: {stripped[:80]}")
    return issues


# ── Run everything ─────────────────────────────────────────────────────────

EXAMPLES_DIR = os.path.join(_here, "examples")

EXAMPLES = [
    "01_counter.py",
    "02_todo.py",
    "03_settings.py",
    "06_soils_lab.py",
    "08_soil_water_retention.py",
]

passed = failed = 0
print("=" * 60)
print("Guile smoke tests")
print("=" * 60)
print()

# 1. Recursion guard
print("[ Recursion guard ]")
try:
    n = test_recursion_guard()
    print(f"  PASS  guard fires correctly ({n} renders, not infinite)")
    passed += 1
except AssertionError as e:
    print(f"  FAIL  {e}")
    failed += 1
print()

# 2. Examples
print("[ Examples ]")
for fname in EXAMPLES:
    path = os.path.join(EXAMPLES_DIR, fname)
    if not os.path.exists(path):
        print(f"  SKIP  {fname:30s} (file not found)")
        continue

    # Static check for .set() inside ui()
    set_issues = check_for_set_in_ui(path)
    if set_issues:
        print(f"  WARN  {fname:30s} — .set() inside ui():")
        for i in set_issues:
            print(i)

    # Load and render
    try:
        mod = load_example(path)
    except Exception as e:
        print(f"  FAIL  {fname:30s} — load error: {e}")
        failed += 1
        continue

    ui_fn = getattr(mod, "ui", None)
    if ui_fn is None:
        print(f"  SKIP  {fname:30s} — no ui() function")
        continue

    issues = smoke(fname, ui_fn)
    if issues:
        print(f"  FAIL  {fname:30s}")
        for i in issues:
            print(f"        {i}")
        failed += 1
    else:
        _, cids = render(ui_fn)
        print(f"  PASS  {fname:30s}  ({len(cids)} callbacks exercised)")
        passed += 1

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
