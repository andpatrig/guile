# Guile — How the code is organised

This document explains what each file does and how they work together.
It's aimed at someone comfortable with Python who wants to understand
or extend the framework.

---

## The five files

### `state.py` — reactive values

This is the simplest file and the heart of the whole framework.

It defines one class: `State`. A `State` is just a wrapper around any
Python value — a number, a string, a list, anything. The special thing
is that whenever you change the value (via `.set()`, `.update()`, or
assigning to `.value`), it automatically tells the app to redraw the
screen.

```python
count = gui.state(0)
count.set(count.value + 1)   # triggers a re-render
```

Internally, `state.py` keeps a list of listener functions. When a value
changes, it calls all of them. In practice there is only ever one
listener: the app's render function, registered by `_app.py`.

**Nothing in `state.py` knows about widgets, HTML, or windows.**
It is pure Python and has no dependencies on the rest of guile.

---

### `ui.py` — render engine + all widgets

This is the largest file and does two jobs. They are separated into
clearly labelled sections at the top of the file.

**Section 1 — Render engine (~150 lines)**

This is the machinery that makes `with gui.card():` work. The key idea
is a *thread-local stack*: a hidden list that tracks which container
you are currently inside.

When you write `with gui.col():`, a Column node is pushed onto the
stack. Every `gui.text()`, `gui.button()` etc. that runs inside the
block automatically attaches itself to that Column. When the `with`
block ends, the Column pops off the stack and attaches to whatever was
above it.

The result: you write flat, top-to-bottom Python code, and guile
assembles it into a proper tree — just like how indentation in a Python
`if` block groups statements, indentation in a guile `with` block
groups widgets.

Section 1 also manages the **callback registry**: a dictionary that maps
each widget's unique ID to the function that should be called when the
user interacts with it (clicks a button, moves a slider, etc.).

**Section 2 — Widget classes (~750 lines)**

Every widget you can use — `Column`, `Row`, `Card`, `_Button`,
`_Input`, `_Slider`, `_Table`, `_Figure`, `_Map`, and so on — is
defined here as a Python class. Each class has:

- An `__init__` that stores the widget's settings
- A `render()` method that returns an HTML string

When guile needs to update the screen, it calls `render()` on every
widget in the tree and sends the result to the browser.

---

### `_app.py` — window lifecycle and bridge

This file creates and manages the native desktop window using
[pywebview](https://pywebview.flowrl.com/). It contains two classes.

**`_App`** — the main app runner. It:

1. Creates the pywebview window with the HTML page from `_template.py`
2. Registers a listener in `state.py` so any state change triggers a
   re-render
3. On `_on_loaded` (page is ready): calls `_render()` for the first time
4. On `_render()`: runs the user's `ui()` function, collects all the
   widgets into a tree, serialises them to HTML, and sends the HTML to
   the browser via `evaluate_js()`
5. On `_on_closed`: cleans up listeners and resets input states

**`_Bridge`** — the object exposed to JavaScript as
`window.pywebview.api`. When the user clicks a button, the browser
calls `window.pywebview.api.handle(id, value)`, which routes to this
class.

One important detail: `handle()` must return *immediately* without
doing any real work. This is because pywebview calls it on its internal
WebView thread, and if that thread is busy, it cannot also run
`evaluate_js()` — causing a deadlock. So `handle()` instantly spawns
a background thread that does the actual dispatch and re-render.

If pywebview is not installed, `_App` falls back to running a tiny
local HTTP server and opening the app in your default browser — useful
for development.

---

### `_template.py` — the HTML page

This file contains the HTML page that is injected into the pywebview
window at startup. It is a single Python string with three parts
embedded inside it:

**CSS** (~200 lines) — a complete design system with:
- CSS custom properties (variables) for colours, spacing, and fonts
- Light and dark mode via `prefers-color-scheme`
- Styles for every widget class (`guile-btn`, `guile-card`, etc.)

**JavaScript** (~100 lines) — two functions:
- `_guilePatch(oldNode, newNode)` — an incremental DOM patcher. Instead
  of replacing the entire page on every re-render, it walks the old
  and new HTML trees and only changes what actually differs. This is
  why inputs keep focus and sliders don't jump when state changes.
- The Leaflet map registry — manages interactive map instances across
  re-renders so the map doesn't reset when you move a slider.

**`get_html(title, use_leaflet)`** — the function that assembles the
full page. If a map widget is in use, it also loads Leaflet's CSS and
JS from a CDN.

---

### `__init__.py` — the public API

This is the file you import: `import guile as gui`. It is intentionally
thin — just 24 short functions and no classes of its own.

Every function here is a one-to-three line wrapper that creates the
corresponding widget class from `ui.py`. For example:

```python
def button(label, *, on_click=None, variant="primary", ...):
    return _Button(label, on_click=on_click, variant=variant, ...)
```

The point of this file is to give users a clean, stable API surface.
The internal classes (`_Button`, `_Input`, `_App`, etc.) can change
their internals without affecting user code, as long as the functions
here stay the same.

It also re-exports `Marker` (for map markers) and the `@gui.app()`
decorator, which is the entry point that launches the window.

---

## How the files connect

```
Your app.py
    │
    ▼
__init__.py        ← you call gui.button(), gui.state(), etc.
    │
    ├─── state.py  ← gui.state() lives here
    │
    ├─── ui.py     ← all widget classes + render engine
    │        │
    │        └── state.py  (widgets read/write State)
    │
    ├─── _app.py   ← creates the window, drives re-renders
    │        │
    │        ├── ui.py       (runs ui(), calls render())
    │        └── _template.py (gets the HTML page)
    │
    └─── _template.py  ← embedded HTML/CSS/JS (static, loaded once)
```

The flow for a button click:

```
User clicks button
  → browser JS calls window.pywebview.api.handle(id, value)
  → _Bridge.handle() in _app.py spawns a background thread
  → background thread calls dispatch(id) from ui.py
  → the button's on_click lambda runs
  → lambda calls count.set(...) in state.py
  → state.py fires its listeners
  → _App._render() in _app.py runs
  → ui() function re-executes top to bottom
  → all widgets call render() and produce HTML
  → evaluate_js() sends the HTML to the browser
  → _guilePatch() in _template.py updates only what changed
```

---

## Adding a new widget

1. Add a class to `ui.py` (Section 2) that inherits from `_Leaf`
2. Implement `__init__` and `render()` — `render()` returns an HTML string
3. Add the CSS for your widget to `_template.py`
4. Add a factory function to `__init__.py` that constructs the class

That's it. No registration, no plugin system, no configuration.
The widget automatically appears in the render tree the moment it is
constructed inside a `with` block.
