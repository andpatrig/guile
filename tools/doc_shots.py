"""
Regenerate the feature screenshots used by the docs (docs/screenshots/features/).

Each entry in SHOTS is a complete, runnable guile app — the exact code the docs
show next to the picture, so code and image never drift apart. For each one the
script runs ui() once without opening a window, writes a static HTML page (the
real guile template + the rendered UI), and screenshots it with headless
Microsoft Edge at 2x for crisp images on high-DPI screens.

It also rewrites the landing-page gallery (docs/index.html, between the
gallery markers) from SHOTS + GALLERY, so edit snippets here, not in the page.

Usage:
    python tools/doc_shots.py            # all shots + the landing gallery
    python tools/doc_shots.py tabs rail  # just these shots
    python tools/doc_shots.py --html     # just the landing gallery

Needs Microsoft Edge (preinstalled on Windows). Maps need network for tiles.
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
OUT = os.path.join(ROOT, "docs", "screenshots", "features")
sys.path.insert(0, ROOT)

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

SHOTS = {}

SHOTS["two_column"] = '''
import guile as gui

crop = gui.state("Wheat")
rate = gui.state(60)

@gui.app("Two columns", width=640, height=330)
def ui():
    with gui.row(gap=16, padding=16, align="flex-start"):
        with gui.card(gap=12, style="width:220px;flex-shrink:0"):
            gui.title("Inputs", size="lg")
            gui.select(["Wheat", "Corn", "Soybean"], "Crop",
                       value=crop, on_change=crop.set)
            gui.slider("N rate (kg/ha)", value=rate,
                       on_change=rate.set, min=0, max=200)
            gui.button("Run model")
        with gui.card(gap=10, fill=True):
            gui.title(f"{crop.value} at {rate.value} kg/ha", size="lg")
            gui.table([
                {"Month": "Apr", "Biomass": 1.2, "LAI": 0.8},
                {"Month": "May", "Biomass": 3.9, "LAI": 2.6},
                {"Month": "Jun", "Biomass": 7.4, "LAI": 4.1},
            ])

gui.run()
'''

SHOTS["tabs"] = '''
import guile as gui

records = [
    {"Station": "Manhattan", "Rain (mm)": 12.4, "Temp (C)": 24.1},
    {"Station": "Hays",      "Rain (mm)":  3.1, "Temp (C)": 27.8},
    {"Station": "Colby",     "Rain (mm)":  0.0, "Temp (C)": 29.5},
]

@gui.app("Tabs", width=560, height=300)
def ui():
    with gui.col(padding=20, gap=14):
        gui.title("Mesonet")
        tab = gui.tabs(["Overview", "Data", "Info"],
                       value="Data", key="tabs")
        if tab == "Overview":
            gui.text("Summary statistics here.")
        elif tab == "Data":
            gui.table(records)
        else:
            gui.text("Built with guile.", muted=True)

gui.run()
'''

SHOTS["rail"] = '''
import guile as gui

@gui.app("Button rail", width=600, height=330)
def ui():
    with gui.row(gap=0, align="stretch", style="height:100vh"):
        with gui.col(padding=10, style="background:var(--surface-2);"
                                        "border-right:1px solid var(--border)"):
            page = gui.rail([
                {"label": "Home",     "icon": gui.icon("home")},
                {"label": "Data",     "icon": gui.icon("table")},
                {"label": "Map",      "icon": gui.icon("map")},
                {"label": "Settings", "icon": gui.icon("settings")},
            ], value="Data", key="nav")

        with gui.col(padding=24, gap=14, fill=True):
            gui.title(page)
            gui.rail(["Bars", "Lines", "Table"], value="Lines",
                     orientation="horizontal", border=True, key="view")
            gui.text("Pick a view above; the panel is a plain if/elif.",
                     muted=True)

gui.run()
'''

SHOTS["widgets"] = '''
import guile as gui

@gui.app("Widgets", width=640, height=470)
def ui():
    with gui.row(gap=16, padding=16, align="flex-start"):
        with gui.card(gap=12, fill=True):
            gui.input("Site name", placeholder="e.g. Konza Prairie")
            gui.number_input("Depth (cm)", value=30, min=0, step=5)
            gui.select(["Silt loam", "Clay", "Sand"], "Soil texture")
            gui.date_input("Sampling date", value="2026-06-15")
            gui.slider("Moisture (%)", value=24, min=0, max=50)
        with gui.card(gap=12, fill=True):
            gui.checkbox("Irrigated", value=True)
            gui.textarea("Notes", placeholder="Field observations...")
            with gui.row(gap=8):
                gui.badge("Active")
                gui.badge("Pending", variant="warning")
                gui.badge("Error", variant="danger")
            gui.progress(65)
            with gui.row(gap=8):
                gui.button("Save")
                gui.button("Cancel", variant="ghost")

gui.run()
'''

SHOTS["dashboard"] = '''
import guile as gui

METRICS = [("Rainfall", "412 mm"), ("Mean temp", "18.4 °C"),
           ("Stations", "62"), ("Uptime", "99.8%")]

@gui.app("Dashboard", width=720, height=200)
def ui():
    with gui.row(gap=12, padding=16):
        for label, value in METRICS:
            with gui.card(fill=True, gap=4):
                gui.text(label, muted=True, size="sm")
                gui.text(value, size="2xl", bold=True)

gui.run()
'''

SHOTS["figure"] = '''
import math
import guile as gui
import matplotlib.pyplot as plt

days = list(range(1, 31))
temps = [24 + 4 * math.sin(d / 3) + d * 0.1 for d in days]

def make_plot():
    fig, ax = plt.subplots(figsize=(6, 2.6))
    ax.plot(days, temps, marker="o", markersize=3)
    ax.set_xlabel("Day of month")
    ax.set_ylabel("Air temp (°C)")
    fig.tight_layout()
    return fig

@gui.app("Figure", width=640, height=360)
def ui():
    with gui.card(gap=8, style="margin:16px"):
        gui.title("June air temperature", size="lg")
        gui.figure(make_plot())

gui.run()
'''


SHOTS["map"] = '''
import guile as gui

STATIONS = [("Manhattan", 39.21, -96.59), ("Hays", 38.85, -99.34),
            ("Colby", 39.39, -101.07), ("Garden City", 38.00, -100.82),
            ("Hutchinson", 37.93, -98.02), ("Cherokee", 37.20, -94.98)]

picked = gui.state("Click a station")

@gui.app("Map", width=720, height=380)
def ui():
    with gui.row(gap=16, padding=16, align="flex-start"):
        with gui.card(gap=12, style="width:190px;flex-shrink:0"):
            gui.title("Mesonet", size="lg")
            gui.badge(f"{len(STATIONS)} stations")
            gui.text(picked.value, muted=True, size="sm")
        with gui.card(padding=8, fill=True):
            gui.leaflet(center=(38.5, -98.3), zoom=6, height=320, key="map",
                        markers=[gui.Marker((lat, lon), tooltip=name,
                                     on_click=lambda n=name: picked.set(n))
                                 for name, lat, lon in STATIONS])

gui.run()
'''


def _render_page(src: str) -> tuple[str, int, int]:
    """Run the app source up to gui.run() and return (html, width, height)."""
    import guile as gui
    from guile._app import _App
    from guile.ui import _reset_render
    from guile._template import get_html

    gui._pending_app = None
    orig_run = gui.run
    gui.run = lambda *a, **k: None
    try:
        exec(compile(src, "<shot>", "exec"), {"__name__": "__main__", "__file__": os.path.join(ROOT, "examples", "shot.py")})
    finally:
        gui.run = orig_run
        gui._run_called = True
    fn, cfg = gui._pending_app

    app = _App(cfg["title"], width=cfg["width"], height=cfg["height"],
               center=cfg["center"])
    _App._current = app
    _reset_render()
    with app._make_root() as root:
        fn()
    body = root.render()
    page = get_html(cfg["title"], use_leaflet=app._use_leaflet,
                    use_leaflet_draw=app._use_leaflet_draw)
    boot = ("<script>window.addEventListener('load',function(){"
            f"window._guile.update({json.dumps(body)});}});</script>")
    page = page.replace("</body>", boot + "</body>")
    return page, cfg["width"], cfg["height"]


def _edge() -> str:
    for p in EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    found = shutil.which("msedge")
    if found:
        return found
    raise SystemExit("Microsoft Edge not found; it is needed for screenshots.")


def shoot(name: str, src: str, edge: str, tmp: str) -> str:
    page, w, h = _render_page(src)
    html_path = os.path.join(tmp, name + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    out = os.path.join(OUT, name + ".png")
    subprocess.run([
        edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=2", f"--window-size={w},{h}",
        "--virtual-time-budget=4000", f"--user-data-dir={os.path.join(tmp, 'profile')}",
        f"--screenshot={out}", "file:///" + html_path.replace("\\", "/"),
    ], check=True, capture_output=True)
    _trim_bottom(out)
    return out


def _trim_bottom(path: str, margin: int = 32) -> None:
    """Crop empty window background below the content (needs Pillow)."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 1, im.height - 1)))
    box = ImageChops.difference(im, bg).getbbox()
    if box and box[3] + margin < im.height:
        im.crop((0, 0, im.width, box[3] + margin)).save(path, optimize=True)


# ── Landing-page gallery ──────────────────────────────────────────────────────
# (shot, tab label, one-line caption, docs link, link text). The tool rewrites
# the block between the gallery markers in docs/index.html from these + SHOTS.
GALLERY = [
    ("two_column", "Two columns",
     "A fixed-width input card next to a results card that fills the rest.",
     "guile_howto.html#layout-common", "How-to: common layouts"),
    ("widgets", "Widgets",
     "Inputs, selects, dates, sliders, badges, progress and buttons.",
     "guile_reference.html", "Reference: all widgets"),
    ("tabs", "Tabs",
     "gui.tabs() returns the active label; the panel is a plain if/elif.",
     "guile_howto.html#pattern-tabs", "How-to: tabs"),
    ("rail", "Button rail",
     "Icon + label rails for sidebars and toolbars, with ~2100 bundled icons.",
     "guile_howto.html#pattern-rail", "How-to: button rails"),
    ("map", "Maps",
     "Interactive Leaflet maps on OpenStreetMap, with markers, overlays and drawing.",
     "guile_howto.html#map-basics", "How-to: maps"),
    ("dashboard", "Metric cards",
     "Equal-width cards from a plain for loop: give each one fill=True.",
     "guile_howto.html#layout-common", "How-to: common layouts"),
    ("figure", "Figures",
     "Any matplotlib figure, rendered in place with gui.figure().",
     "guile_reference.html#w-figure", "Reference: gui.figure()"),
]
GALLERY_START = "<!-- gallery:start (generated by tools/doc_shots.py) -->"
GALLERY_END = "<!-- gallery:end -->"


def highlight(src: str) -> str:
    """Python source -> HTML spans using the landing page's pre.code classes."""
    import io
    import html
    import keyword
    import tokenize

    lines = src.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    pos = lambda rc: offsets[rc[0] - 1] + rc[1]

    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    out, last, depth, fstart = [], 0, 0, None
    for i, t in enumerate(toks):
        name = tokenize.tok_name[t.type]
        if name == "FSTRING_START":          # Python 3.12+: f-string pieces
            if depth == 0:
                fstart = t.start
            depth += 1
            continue
        if name == "FSTRING_END":
            depth -= 1
            if depth == 0:
                a, b = pos(fstart), pos(t.end)
                out.append(html.escape(src[last:a]))
                out.append(f'<span class="str">{html.escape(src[a:b])}</span>')
                last = b
            continue
        if depth or name in ("NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER"):
            continue
        a, b = pos(t.start), pos(t.end)
        text = src[a:b]
        if name == "NAME":
            nxt = toks[i + 1].string if i + 1 < len(toks) else ""
            cls = ("kw" if keyword.iskeyword(text) else
                   "fn" if nxt == "(" else "id")
        else:
            cls = {"STRING": "str", "NUMBER": "num", "COMMENT": "com",
                   "OP": "punct"}.get(name, "id")
        out.append(html.escape(src[last:a]))
        out.append(f'<span class="{cls}">{html.escape(text)}</span>')
        last = b
    out.append(html.escape(src[last:]))
    return "".join(out)


def gallery_html() -> str:
    import html
    import re
    tabs, panels = [], []
    for i, (name, label, caption, href, link) in enumerate(GALLERY):
        src = SHOTS[name].strip()
        title = re.search(r'@gui\.app\("([^"]+)"', src).group(1)
        sel = "true" if i == 0 else "false"
        tabs.append(
            f'<button class="gal-tab" role="tab" id="gal-tab-{name}" '
            f'aria-controls="gal-{name}" aria-selected="{sel}">{label}</button>')
        panels.append(f'''<div class="gal-panel" role="tabpanel" id="gal-{name}" aria-labelledby="gal-tab-{name}"{'' if i == 0 else ' hidden'}>
      <p class="gal-caption">{html.escape(caption)} <a href="{href}">{link} <span class="arrow">→</span></a></p>
      <div class="qs-grid">
        <div class="code-window">
          <div class="win-bar">
            <div class="win-dots"><i></i><i></i><i></i></div>
            <div class="win-title">{name}.py</div>
          </div>
<pre class="code"><code>{highlight(src)}</code></pre>
        </div>
        <div class="preview-window">
          <div class="win-bar">
            <div class="win-dots"><i></i><i></i><i></i></div>
            <div class="win-title">{html.escape(title)}</div>
            <div class="win-tabs"><span class="win-tab">screenshot</span></div>
          </div>
          <div class="gal-shot"><img src="screenshots/features/{name}.png" alt="{html.escape(label)} example rendered by guile" loading="lazy"></div>
        </div>
      </div>
    </div>''')
    return (GALLERY_START + "\n    <div class=\"gal-tabs\" role=\"tablist\" aria-label=\"Gallery\">\n      "
            + "\n      ".join(tabs) + "\n    </div>\n    " + "\n    ".join(panels)
            + "\n    " + GALLERY_END)


def write_gallery() -> None:
    path = os.path.join(ROOT, "docs", "index.html")
    with open(path, encoding="utf-8") as f:
        page = f.read()
    a, b = page.find(GALLERY_START), page.find(GALLERY_END)
    if a < 0 or b < 0:
        raise SystemExit("gallery markers not found in docs/index.html")
    page = page[:a] + gallery_html() + page[b + len(GALLERY_END):]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("gallery -> docs/index.html")


def main(names):
    if names == ["--html"]:
        write_gallery()
        return
    os.makedirs(OUT, exist_ok=True)
    edge = _edge()
    names = names or list(SHOTS)
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            print("shot", name, "->", os.path.relpath(shoot(name, SHOTS[name], edge, tmp), ROOT))
    if not sys.argv[1:]:
        write_gallery()


if __name__ == "__main__":
    main(sys.argv[1:])
