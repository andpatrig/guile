"""Release regression tests: python -m unittest test_regressions."""
import unittest

import guile as gui
import guile.ui as U
from guile._app import _App, _Bridge
from test_guile import make_app, drain


class ReleaseRegressions(unittest.TestCase):
    def test_live_commit_renders_without_repeating_callback(self):
        for factory in (gui.input, gui.textarea):
            value = gui.state("")
            calls = []
            def changed(v):
                calls.append(v); value.set(v.upper())
            app = make_app(lambda: factory(value=value, live=True, key="field", on_change=changed))
            app._queue.put(("render", None, None)); drain(app)
            bridge = _Bridge(app)
            bridge.handle("gk-field", "abc", U._live_generation, 1); drain(app)
            before = app._window.render_count()
            bridge.handle("gk-field-commit", None, U._live_generation, 2); drain(app)
            self.assertEqual(calls, ["abc"])
            self.assertEqual(value.value, "ABC")
            self.assertGreater(app._window.render_count(), before)

    def test_leaflet_save_emits_one_batch_per_operation(self):
        import json, shutil, subprocess
        from guile._template import _JS
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js required")
        prefix = r'''
global.window = global;
global.document = {addEventListener() {}};
const calls = [], handlers = {};
global.pywebview = {api: {handle_batch: (...args) => calls.push(args)}};
global.L = {Control: {Draw: function() {}}, FeatureGroup: function() {
    this.addTo = function() {return this;};
}};
const entry = {gen: 7, map: {on: (name, fn) => handlers[name] = fn,
    off() {}, addControl() {}}};
'''
        checks = r'''
_guileAttachMapEvents(entry, {draw:['marker'], on_shape_edit_cid:'edit', on_shape_delete_cid:'delete'});
const layers = [1,2,3].map(i => ({_guileId:String(i), _guileType:'marker',
    getLatLng:()=>({lat:i,lng:i})}));
const event = {layers:{eachLayer:fn=>layers.forEach(fn)}};
handlers['draw:edited'](event);
handlers['draw:deleted'](event);
console.log(JSON.stringify(calls));
'''
        result = subprocess.run([node, "-"], input=prefix + _JS + checks,
                                text=True, encoding="utf-8", capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = json.loads(result.stdout)
        self.assertEqual(len(calls), 2)
        for i, (cid, values, gen, seq) in enumerate(calls):
            self.assertEqual(cid, ["edit", "delete"][i])
            self.assertEqual([v["id"] for v in values], ["1", "2", "3"])
            self.assertEqual((gen, seq), (7, i + 1))

    def test_task_failure_does_not_block_shutdown(self):
        import threading
        errors = []
        gate = threading.Event()
        busy = gui.state(False)
        app = make_app(lambda: None)
        def fail():
            gate.wait(3)
            raise SystemExit("task stopped")
        gui.task(fail, busy=busy, on_error=lambda exc: errors.append(type(exc)))
        app._on_closed(); gate.set(); app._worker.join(3)
        self.assertFalse(app._worker.is_alive())
        self.assertEqual(errors, [SystemExit])
        self.assertFalse(busy.value)

    def test_development_watcher_stops_on_close(self):
        import threading
        from unittest.mock import patch
        from guile import _dev
        app = make_app(lambda: None)
        before = set(threading.enumerate())
        with patch.object(_dev.os.path, "getmtime", return_value=1):
            _dev.start_watcher(app, "test.py", interval=0.01)
            watchers = [t for t in threading.enumerate() if t not in before]
            app._on_closed(); app._worker.join(3)
            for watcher in watchers:
                watcher.join(3)
                self.assertFalse(watcher.is_alive())

    def tearDown(self):
        app = _App._current
        if app is not None:
            app._on_closed()
            app._worker.join(3)
            self.assertFalse(app._worker.is_alive())

    def test_close_finishes_tasks_and_stops_worker(self):
        import threading
        gate = threading.Event()
        value = gui.state("before")
        busy = gui.state(False)
        app = make_app(lambda: gui.text(value.value))
        gui.task(lambda: (gate.wait(3), "finished")[1], on_done=value.set, busy=busy)
        app._on_closed()
        self.assertTrue(app._worker.is_alive())
        self.assertEqual(value.value, "before")
        with self.assertRaises(RuntimeError):
            gui.task(lambda: None)
        gate.set(); app._worker.join(3)
        self.assertFalse(app._worker.is_alive())
        self.assertEqual(value.value, "finished")
        self.assertFalse(busy.value)
        self.assertIsNone(_App._current)
        self.assertIsNone(app._window)

    def test_run_waits_for_completion_even_on_close(self):
        import threading
        from unittest.mock import patch
        value = gui.state(None)
        app = _App("test")
        gate = threading.Event()
        def window(build):
            _App._current = app
            gui.task(lambda: (gate.wait(3), 42)[1], on_done=value.set)
            app._on_closed()
        finished = threading.Event()
        with patch.object(app, "_run_window", window):
            runner = threading.Thread(target=lambda: (app.run(lambda: None), finished.set()))
            runner.start()
            self.assertFalse(finished.wait(0.05))
            gate.set(); runner.join(3)
        self.assertTrue(finished.is_set())
        self.assertEqual(value.value, 42)
        self.assertFalse(app._worker.is_alive())

    def test_startup_failure_cleans_up(self):
        from unittest.mock import patch
        app = _App("test")
        with patch.object(app, "_run_window", side_effect=RuntimeError("startup")):
            with self.assertRaisesRegex(RuntimeError, "startup"):
                app.run(lambda: None)
        self.assertFalse(app._worker.is_alive())

    def test_static_figures_follow_object_and_render_options(self):
        import gc, weakref
        from matplotlib.figure import Figure
        from unittest.mock import patch
        U._Figure._cache.clear()
        first = Figure(); first.subplots().plot([0, 1], [0, 1])
        second = Figure(); second.subplots().plot([0, 1], [1, 0])
        def render(fig, **kwargs):
            U._reset_render()
            return gui.figure(fig, static=True, **kwargs).render()
        first_html = render(first)
        self.assertNotEqual(first_html, render(second))
        with patch.object(U._Figure, "_to_base64", side_effect=AssertionError("cache miss")):
            self.assertEqual(first_html, render(first))
        self.assertNotEqual(first_html, render(first, dpi=120))
        ref = weakref.ref(second)
        del second; gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(len(U._Figure._cache), 1)

    def test_numeric_dropdown_keys_and_falsy_values(self):
        from html.parser import HTMLParser
        class Options(HTMLParser):
            def __init__(self, markup):
                super().__init__(); self.selected = []; self.feed(markup)
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "option" and "selected" in attrs:
                    self.selected.append(attrs["value"])
        for initial in (0, 2, gui.state(2)):
            U._clear_state_store(); U._reset_render()
            widget = gui.select({1: "One", 0: "Zero", 2: "Two"}, value=initial)
            expected = str(initial.value if isinstance(initial, gui.State) else initial)
            self.assertEqual(Options(widget.render()).selected, [expected])
        U._clear_state_store(); U._reset_render()
        widget = gui.multiselect({0: "Zero", 2: "Two"}, value=[0, 2])
        self.assertEqual(Options(widget.render()).selected, ["0", "2"])
        U._clear_state_store(); U._reset_render()
        widget = gui.select(["default", ""], value="")
        self.assertEqual(widget.value, "")
        self.assertEqual(Options(widget.render()).selected, [""])

    def test_shape_batch_is_atomic_across_renders(self):
        for operation in ("edit", "delete"):
            changes = gui.state([])
            def build():
                gui.leaflet(key="map", **{
                    "on_shape_" + operation: lambda *args: changes.update(lambda old: old + [args])})
            app = make_app(build)
            app._queue.put(("render", None, None)); drain(app)
            gen = U._live_generation
            values = [{"id": str(i), "type": "marker", "coords": {"lat": i, "lng": i}}
                      for i in range(10)]
            bridge = _Bridge(app)
            bridge.handle_batch("gk-map-shape-" + operation, values, gen, 1)
            drain(app)
            self.assertEqual([row[0] for row in changes.value], [str(i) for i in range(10)])
            bridge.handle_batch("gk-map-shape-" + operation, values, gen, 2)
            drain(app)
            self.assertEqual(len(changes.value), 10)  # stale batch rejected in full

    def test_bridge_restores_browser_order(self):
        value = gui.state("")
        app = make_app(lambda: gui.input(value=value, key="field"))
        app._queue.put(("render", None, None)); drain(app)
        bridge = _Bridge(app)
        bridge.silent_update("gk-field", "ab", seq=2)
        drain(app)
        self.assertEqual(value.value, "")
        bridge.silent_update("gk-field", "a", seq=1)
        drain(app)
        self.assertEqual(value.value, "ab")
        bridge.handle("gk-field", "abc", seq=3)
        drain(app)
        self.assertEqual(value.value, "abc")
        bridge.silent_update("gk-field", "duplicate", seq=2)
        drain(app)
        self.assertEqual(value.value, "abc")


if __name__ == "__main__":
    unittest.main()
