"""Native DOM regressions in a hidden pywebview window.

Run: python test_browser.py <temporary-browser-profile-directory>
The supplied directory is used only for WebView storage; no network is needed.
"""
import sys
import traceback
import time
from unittest.mock import patch

import webview
import guile as gui
import guile.ui as U
from guile._app import _App


CHECKS = r"""
(function() {
    function check(ok, message) { if (!ok) throw new Error(message); }
    function node(html) {
        var box = document.createElement('div'); box.innerHTML = html;
        return box.firstElementChild;
    }
    function mount(html) {
        document.body.innerHTML = html;
        var el = document.body.firstElementChild; el.focus(); return el;
    }
    var el = mount('<input type="checkbox">');
    el.checked = true;
    _guilePatch(el, node('<input type="checkbox">'));
    check(!el.checked, 'rejected checkbox still checked');

    el = mount('<input type="number" value="10">');
    el.value = '150'; el.dispatchEvent(new Event('input', {bubbles:true}));
    _guilePatch(el, node('<input type="number" value="100">'));
    check(el.value === '150', 'unfinished number overwritten');
    el.dispatchEvent(new Event('change', {bubbles:true}));
    _guilePatch(el, node('<input type="number" value="100">'));
    check(el.value === '100', 'committed number not clamped');

    el = mount('<input value="a">');
    el.value = 'abc'; el.setSelectionRange(2,2);
    el.dispatchEvent(new Event('input', {bubbles:true}));
    _guilePatch(el, node('<input value="old">'));
    check(el.value === 'abc' && el.selectionStart === 2, 'typing/caret lost');
    el.dispatchEvent(new Event('change', {bubbles:true}));
    _guilePatch(el, node('<input value="ABC">'));
    check(el.value === 'ABC', 'text correction ignored');

    el = mount('<textarea>before</textarea>');
    el.value = 'after'; el.dispatchEvent(new Event('input', {bubbles:true}));
    _guilePatch(el, node('<textarea>before</textarea>'));
    check(el.value === 'after', 'textarea edit lost');
    el.dispatchEvent(new Event('change', {bubbles:true}));
    _guilePatch(el, node('<textarea>AFTER</textarea>'));
    check(el.value === 'AFTER', 'textarea correction ignored');

    el = mount('<select><option value="a">A</option><option value="b">B</option></select>');
    el.value = 'b';
    _guilePatch(el, node('<select><option value="a" selected>A</option><option value="b">B</option></select>'));
    check(el.value === 'a', 'focused dropdown correction ignored');

    el = mount('<select multiple><option value="a">A</option><option value="b">B</option></select>');
    el.options[0].selected = true; el.options[1].selected = true;
    el.dispatchEvent(new Event('change', {bubbles:true}));
    _guilePatch(el, node('<select multiple><option value="a">A</option><option value="b">B</option></select>'));
    check(el.selectedOptions.length === 2, 'unfinished multiselect lost');
    el.blur();
    _guilePatch(el, node('<select multiple><option value="a">A</option><option value="b" selected>B</option></select>'));
    check(el.value === 'b' && el.selectedOptions.length === 1, 'multiselect commit ignored');
    return 'PASS: checkbox, number, text, textarea, select, multiselect, caret';
})();
"""


def main(profile):
    errors = []
    app = _App("Guile native regression tests")
    number = gui.state(10.0)
    checked = gui.state(False)
    text = gui.state("")
    live = gui.state("")
    live_calls = []
    batch = gui.state([])
    result = gui.state(None)
    def build():
        gui.number_input(value=number, max=100, key="number")
        gui.checkbox(value=checked, key="check", on_change=lambda v: checked.set(False))
        gui.input(value=text, key="text", on_change=lambda v: text.set(v.upper()))
        gui.input(value=live, key="live", live=True,
                  on_change=lambda v: (live_calls.append(v), live.set(v.upper())))
        gui.select({1: "One", 2: "Two"}, value=2, key="select")
        gui.button("Batch", key="batch", on_click=lambda v: batch.update(lambda old: old + [v]))
    original_loaded = app._on_loaded
    def loaded():
        original_loaded()
        window = app._window
        def wait_for(predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(0.01)
            raise AssertionError("native state/DOM did not converge")
        try:
            wait_for(lambda: window.evaluate_js("!!document.querySelector('#gk-number input')"))
            window.evaluate_js("""var el=document.querySelector('#gk-number input');
                el.focus(); el.value='150'; el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));""")
            wait_for(lambda: number.value == 100 and
                     window.evaluate_js("document.querySelector('#gk-number input').value") == '100')
            window.evaluate_js("""var el=document.querySelector('#gk-check input');
                el.focus(); el.checked=true; el.dispatchEvent(new Event('change',{bubbles:true}));""")
            wait_for(lambda: checked.value is False and
                     window.evaluate_js("document.querySelector('#gk-check input').checked") is False)
            window.evaluate_js("""var el=document.querySelector('#gk-text input'); el.focus();
                ['a','ab','abc'].forEach(function(v) {el.value=v; el.dispatchEvent(new Event('input',{bubbles:true}));});
                el.dispatchEvent(new Event('change',{bubbles:true}));""")
            wait_for(lambda: text.value == 'ABC' and
                     window.evaluate_js("document.querySelector('#gk-text input').value") == 'ABC')
            assert window.evaluate_js("document.querySelector('#gk-select select').value") == '2'
            window.evaluate_js("""var el=document.querySelector('#gk-live input'); el.focus();
                el.value='abc'; el.dispatchEvent(new Event('input',{bubbles:true}));""")
            wait_for(lambda: live.value == 'ABC')
            window.evaluate_js("document.querySelector('#gk-live input').dispatchEvent(new Event('change',{bubbles:true}))")
            wait_for(lambda: window.evaluate_js("document.querySelector('#gk-live input').value") == 'ABC')
            assert live_calls == ['abc'], "live commit repeated the callback"
            window.evaluate_js(f"window._guile.batch('gk-batch',[1,2,3,4,5],{U._live_generation})")
            wait_for(lambda: batch.value == [1, 2, 3, 4, 5])
            # A late DOM update must finish before the isolated DOM checks
            # replace the page's body.
            app._queue.put(("call", lambda: None, None))
            time.sleep(0.1)
            print("PASS: native bridge order, corrections, numeric dropdown, atomic batch", flush=True)
            print(window.evaluate_js(CHECKS), flush=True)
            gui.task(lambda: (time.sleep(0.2), 42)[1], on_done=result.set)
        except Exception:
            errors.append(traceback.format_exc())
            print(errors[-1], flush=True)
        finally:
            window.destroy()
    app._on_loaded = loaded
    create_window = webview.create_window
    start = webview.start
    with patch.object(webview, "create_window", side_effect=lambda **kw: create_window(hidden=True, **kw)), \
         patch.object(webview, "start", side_effect=lambda **kw: start(private_mode=False, storage_path=profile, **kw)):
        app.run(build)
    if not errors:
        assert result.value == 42, "run() returned before task completion"
        assert not app._worker.is_alive(), "worker survived run()"
        print("PASS: native shutdown waits for task completion and stops worker", flush=True)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
