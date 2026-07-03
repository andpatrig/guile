# guile — internals reference

A practical map of the codebase for when you need to extend or debug it.

---

## File overview

```
guile/
├── __init__.py     public API  — every gui.* function lives here
├── state.py        State class — reactive values + listener registry
├── ui.py           render engine + every widget class
├── _app.py         window lifecycle, pywebview bridge
└── _template.py    the embedded HTML page (CSS + JS DOM patcher)
```

Nothing in `__init__.py` does real work — it just wraps the classes from
`ui.py` in plain functions, keeping the public surface clean. All substance
is in the four files below it.

---

## How it all connects

```
  Your code
  ─────────
  @gui.app(...)          # __init__.py → _App.run()
  def ui():
      gui.state()        # state.py  → State object
      gui.button(...)    # ui.py     → _Button node, registers callback
      gui.text(...)      # ui.py     → _Text node

          │  on first load, and on every State.set()
          ▼
     _App._render()                              _app.py
       │  runs ui() inside a root Column
       │  collects the node tree
       │  calls root.render() → HTML string
       │  calls window.evaluate_js("_guile.update(html)")
          │
          ▼
     _guilePatch() in browser                   _template.py  (JS)
       walks old DOM vs new HTML string
       patches only what changed
       (preserves focus, preserves Leaflet map subtrees)

  User clicks a button
  ────────────────────
  browser → _guile.trigger(cid)                 _template.py  (JS)
          → window.pywebview.api.handle(cid)
          → _Bridge.handle()  spawns thread      _app.py
          → dispatch(cid)  finds callback        ui.py
          → your on_click lambda runs
          → State.set()  fires listeners         state.py
          → _App._rerender() → _App._render()    _app.py
          (loop repeats from top)
```

The thread dance in `_Bridge` exists because `evaluate_js()` and the
pywebview message thread share a lock. If `handle()` did work synchronously
it would deadlock. The daemon thread sidesteps that.

---

## `state.py` — reactive values

**One class: `State`.**

```python
count = gui.state(0)   # creates State(0)
count.set(42)          # sets ._v, calls _fire()
count.update(fn)       # shorthand: set(fn(value))
count.toggle()         # bool shorthand
count.set_silent(42)   # sets ._v without firing (used by multiselect)
```

`_fire()` calls every function in the module-level `_listeners` list.
`_App.run()` registers `self._rerender` as a listener, so every `State.set()`
anywhere in the app triggers a full re-render.

**Proxy operators** (`__str__`, `__add__`, `__eq__`, …) let you pass a
`State` directly to `gui.text(count)` or use it in f-strings and comparisons
without calling `.value` explicitly.

**Nothing to change here unless** you need a new mutation method (e.g.
`append`, `pop`) or want persistent/serialised state.

---

## `ui.py` — render engine + widgets

### Section 1: render engine (lines 1–260)

**Thread-local parent stack** — how `with gui.card():` works:

```
_push(Card)   ← __enter__
    _attach(Text)   ← Text.__init__ calls _attach(), adds itself to Card.children
    _attach(Button)
_pop(Card)    ← __exit__  attaches Card to its own parent
```

Each thread has its own stack, so concurrent renders don't interfere.

**Callback registry** — two dicts, not one:

| dict | role |
|---|---|
| `_callbacks` | scratch pad, rebuilt every render |
| `_live_callbacks` | committed snapshot, safe for `dispatch()` to read mid-render |

After `ui()` finishes, `_commit_callbacks()` copies `_callbacks →
_live_callbacks`. This means a click that arrives mid-render always finds
its handler in the previous completed render's table.

**`_state_store`** — widget-internal `State` objects keyed by `key=`. Input
widgets (`_Input`, `_Slider`, …) store their value here so typed text
survives re-renders without the user declaring `gui.state()`. Cleared on
window close.

**`_auto_key`** — when no `key=` is given, widgets get `_auto_1`, `_auto_2`,
… in order. Because `ui()` always runs top-to-bottom in the same order,
position N always maps to the same widget. Use explicit `key=` inside loops
or conditionals where that order can change.

### Section 2: widget classes (lines 263–1695)

**Two base classes:**

```
Node
├── _Container  (Column, Row, Card, Scroll, _Modal)
│     __enter__ / __exit__ push/pop the stack
│     render() calls _render_children()
└── _Leaf       (everything else)
      __init__ calls _attach() — no context manager needed
      render() returns an HTML string
```

**Adding a new widget:**

1. Subclass `_Leaf` (or `_Container` if it holds children).
2. Store your params, call `super().__init__(key)` last (this runs `_attach`).
3. If interactive: call `_reg(self.id, handler)` in `__init__`.
4. Implement `render(self) -> str` — return an HTML string with `id="{self.id}"`.
5. Add a thin wrapper function in `__init__.py`.

```python
# Minimal new widget example — a styled code block
class _Code(_Leaf):
    def __init__(self, text: str, *, key=None):
        self._text = text
        super().__init__(key)          # _attach() runs here

    def render(self) -> str:
        safe = _txt(self._text)        # HTML-escape
        return (f'<pre id="{self.id}" '
                f'style="background:var(--surface-2);padding:12px;'
                f'border-radius:var(--r-sm);font-family:var(--mono);'
                f'font-size:13px;overflow-x:auto">{safe}</pre>')

# in __init__.py:
def code(text: str, *, key=None) -> _Code:
    return _Code(text, key=key)
```

**Interactive widget — wiring the callback:**

```python
class _Counter(_Leaf):
    def __init__(self, *, on_click=None, key=None):
        self._state = _get_or_create_state(_auto_key(key), 0)
        super().__init__(key)
        # register: browser click → this handler → state update → re-render
        _reg(self.id, lambda: self._state.update(lambda x: x + 1))
        if on_click:
            _reg(self.id + "-ext", on_click)

    def render(self) -> str:
        js = f"window._guile.trigger('{self.id}', null)"
        return (f'<button id="{self.id}" onclick="{js}">'
                f'{self._state.value}</button>')
```

The JS always calls `window._guile.trigger(id, value)`. For inputs, `value`
is `this.value`; for buttons it's `null`. `dispatch()` in `ui.py` handles
both shapes.

---

## `_app.py` — window + bridge

**`_App`** manages the pywebview window:

| method | what it does |
|---|---|
| `run(build_fn)` | silent probe run, opens window, starts event loop |
| `_on_loaded()` | fires when page loads → triggers first real render |
| `_on_closed()` | cleans up listeners and state store |
| `_render()` | runs `ui()`, serialises to HTML, pushes via `evaluate_js` |
| `_rerender()` | registered as a `State` listener; calls `_render()` |
| `_make_root()` | builds the root `Column` (centered or default) |

`_render()` is a loop, not recursion. If a state change arrives mid-render
it sets `_needs_render = True` and the loop runs one more time. It stops
after that — two renders is enough to stabilise.

**`_Bridge`** is the object pywebview exposes as `window.pywebview.api`.
Its methods **must not** start with `_` (pywebview filters them). `handle()`
spawns a daemon thread immediately and returns — blocking here deadlocks
`evaluate_js`.

**`_fallback_browser()`** — when pywebview is absent, a local HTTP server
serves the app and opens the browser. POST requests dispatch callbacks; GET
`/` returns the page HTML and GET anything else returns a fresh render.

---

## `_template.py` — the embedded page

This file is one long Python string. It has three sections:

### `_CSS` — design tokens and component styles

All colours are CSS custom properties (`--bg`, `--surface`, `--primary`, …)
defined on `:root`. Dark mode overrides a subset via
`@media (prefers-color-scheme: dark)`. `gui.theme()` overrides the same
variables at runtime by injecting a `<style>` tag.

**Adding CSS for a new widget:**

Append to `_CSS`. Follow the `.guile-<name>` convention. Use `var(--token)`
for colours so dark mode and themes work for free.

```css
/* example: code block added above */
.guile-code {
    background: var(--surface-2);
    border-radius: var(--r-sm);
    font-family: var(--mono);
    font-size: 13px;
    padding: 12px;
    overflow-x: auto;
}
```

**Design tokens quick reference:**

| token | meaning |
|---|---|
| `--bg` | window/page background |
| `--surface` | card / input background |
| `--surface-2` | hover rows, secondary surfaces |
| `--primary` | accent: buttons, sliders, focus rings |
| `--primary-h` | darker accent for hover |
| `--primary-light` | tinted accent for badge backgrounds |
| `--text` | primary text |
| `--text-2` | muted / secondary text |
| `--border` | borders and dividers |
| `--border-focus` | focus ring colour |
| `--danger / --success / --warning` | status colours |
| `--r / --r-sm / --r-lg` | border radii |
| `--shadow / --shadow-sm / --shadow-lg` | box shadows |
| `--mono` | monospace font stack |
| `--t` | transition duration/easing (`0.15s ease`) |

### `_JS` — incremental DOM patcher + bridge

**`_guilePatch(oldNode, newNode)`** walks both trees and updates only
attributes and text that differ. Key behaviours:
- Saves and restores `document.activeElement.value` so focused inputs don't
  lose the cursor on every keystroke.
- Skips children of `.guile-map` elements — Leaflet owns that subtree.

**`window._guile`** is the client-side API:

| method | purpose |
|---|---|
| `_guile.update(html)` | called by Python after each render |
| `_guile.trigger(cid, value)` | called by widget event handlers → Python |
| `_guile.silent(cid, value)` | like trigger but no re-render (multiselect) |

**Leaflet map registry (`_guileMaps`)** — maps are long-lived imperative
objects. The patcher skips their DOM subtrees, but `_guileSyncMaps()` re-runs
after every update to apply marker/config changes detected by comparing
serialised `cfgJson`.

### `get_html(title, use_leaflet, use_leaflet_draw)`

Assembles the full page string. Leaflet `<link>` and `<script>` tags are
injected only when `_App._use_leaflet` was set to `True` during the silent
probe run (before the window opens). That's why `gui.leaflet()` sets a flag
on `_App._current` rather than just returning an element.

---

## Design notes — what's novel and why

A brief account of the ideas behind guile, for when you need to explain it to
someone (or to yourself, six months later).

### The `with` block layout — borrowed, but the right fit

Context managers for UI trees aren't new. But most Python desktop frameworks
(Tkinter, Qt, wxPython) still use imperative `.pack()`/`.grid()` calls or
external XML files, and the two things rarely look like each other. Here, the
indentation of the code *is* the layout. You look at the source and you see the
window:

```python
with gui.card():
    gui.title("Settings")
    with gui.row():
        gui.button("Cancel", variant="ghost")
        gui.button("Save")
```

The implementation is about 15 lines: `__enter__` pushes a node onto a
thread-local stack, every leaf widget attaches itself to whatever is on top,
`__exit__` pops and attaches the container to its own parent. Simple enough to
read in one sitting, solid enough that it never needs to change.

### The reactive state model — the right idea, stripped down

`gui.state()` is React's `useState` translated to Python, and that's not a
criticism. React's model is a good one. What's worth noting is what was *left
out*: no virtual DOM library, no component tree, no `useEffect`, no dependency
tracking. Just one rule — any `State.set()` rerenders everything.

That sounds expensive. For a single-window desktop app with a few dozen
widgets it's essentially free, and it means there are zero rules to learn about
when things update. The tradeoff was made consciously.

The proxy operators on `State` (`__str__`, `__add__`, `__eq__`, …) are a
Python-specific improvement over the React original. You can write
`gui.text(count)` or use a State in an f-string and it just works. That's not
possible in JavaScript.

### Widget-internal state — one fewer declaration

In React, every piece of state must be declared. In guile, input widgets own
their state internally, keyed by position counter or explicit `key=`:

```python
name = gui.input("Name", key="name")
gui.text(f"Hello, {name.value}")
```

No `gui.state()` needed. You reach for it only when state outlives a single
widget or is shared between several. For a data scientist who thinks in
variables and values rather than component lifecycle, this matches how you
actually work.

### The DOM patcher — rerender everything, patch only what changed

This is the part most worth explaining. When state changes, guile re-runs your
entire `ui()` function, serialises the result to an HTML string, sends it to
the WebView, and a small JS function (`_guilePatch`, ~40 lines of vanilla JS)
walks the old and new DOM trees and updates only what changed — preserving
focus, preserving the input cursor, preserving Leaflet map subtrees that
Leaflet itself owns.

The elegant part is what this avoids: no virtual DOM library, no diffing
algorithm dependency, no shadow tree. The "virtual DOM" is just the HTML string
you already produced. Python re-renders; JS patches. The boundary is clean and
the moving parts are few.

### The two-callback-dicts pattern — a small solution to a real problem

Every render rebuilds the callback table from scratch. But a click can arrive
mid-render when the table is half-empty. The solution: one scratch dict being
built, one committed snapshot always safe to read — classic double-buffering at
very small scale. Four lines of code, and a whole class of race condition
disappears.

### What was left out — the harder decision

No XML. No signals. No layout managers. No component lifecycle. No build step.
No server. Every existing Python desktop GUI framework was designed by and for
software engineers building software. Streamlit went the other direction — it's
designed for data scientists, but it runs in a browser and requires a server,
which means you can't ship a standalone tool.

The innovation in guile isn't any single idea — most of them exist somewhere.
It's the combination, and the decision about what not to include. That's usually
the harder engineering call, and the one that's hardest to see from the outside.

---

## Where to go for common tasks

| task | file | what to look for |
|---|---|---|
| Add a new widget | `ui.py` | subclass `_Leaf`, implement `render()` |
| Add widget CSS | `_template.py` | append to `_CSS` string |
| Add a JS behaviour (e.g. drag, debounce) | `_template.py` | append to `_JS` string; call `_guile.trigger()` to send events back |
| Change the render loop | `_app.py` | `_render()` method |
| Change how the window is created | `_app.py` | `_App.run()` |
| Add a new built-in theme | `ui.py` | `THEMES` dict at the bottom of the file |
| Change how themes compute derived colours | `ui.py` | `_Theme.render()` (lines ~507–558) |
| Change default design tokens | `_template.py` | `:root { … }` block in `_CSS` |
| Change dark-mode tokens | `_template.py` | `@media (prefers-color-scheme: dark)` block |
| Add a new State mutation method | `state.py` | add to `State` class |
| Expose a new `gui.*` function | `__init__.py` | thin wrapper, import the class from `ui.py` |
| Add a new `@gui.app()` option | `__init__.py` + `_app.py` | add param to both `app()` and `_App.__init__` |
