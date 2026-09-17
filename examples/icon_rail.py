"""
examples/icon_rail.py — showcase for gui.rail() and gui.icon().

A button rail packs many destinations into a narrow space by stacking a
Lucide icon over a one- or two-word label. This app demonstrates:

  * a VERTICAL rail as a sidebar (the common case) that switches the main panel
  * a HORIZONTAL rail used as an in-page sub-toolbar
  * gui.icon() — the bundled ~2100-icon Lucide set — in a gallery, and at
    different sizes and colours (icons stroke in currentColor, so they inherit
    the surrounding text colour)

gui.rail() works like gui.tabs(): it returns the active item's value as a
plain string and manages its own state — just give it a key=.

Run:
    python examples/icon_rail.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── The sidebar rail: gui.icon(name) returns inline SVG for any Lucide icon ──
NAV = [
    {"label": "Rails",  "icon": gui.icon("layout-dashboard")},
    {"label": "Icons",  "icon": gui.icon("shapes")},
    {"label": "Sizing", "icon": gui.icon("ruler")},
    {"label": "About",  "icon": gui.icon("info")},
]

# ── A representative slice of the icon set for the gallery, grouped ───────────
GALLERY = {
    "Navigation & layout": [
        "home", "layout-dashboard", "layers", "sliders-horizontal",
        "settings", "search", "filter", "menu",
    ],
    "Data & charts": [
        "table", "database", "bar-chart-3", "line-chart",
        "area-chart", "pie-chart", "activity", "trending-up",
    ],
    "Files & actions": [
        "folder", "file-text", "save", "download",
        "upload", "pencil", "trash-2", "refresh-cw",
    ],
    "Maps & science": [
        "map", "map-pin", "globe", "thermometer",
        "droplet", "leaf", "flask-conical", "microscope",
    ],
}

SAMPLE = [
    {"Station": "Manhattan", "Rain (mm)": 12.4, "Temp (C)": 24.1},
    {"Station": "Hays",      "Rain (mm)":  3.1, "Temp (C)": 27.8},
    {"Station": "Colby",     "Rain (mm)":  0.0, "Temp (C)": 29.5},
]


def icon_grid(names) -> str:
    """A responsive grid of icon + name cells, built as raw HTML."""
    cells = "".join(
        f'<div style="display:flex;flex-direction:column;align-items:center;'
        f'gap:8px;padding:14px 6px;border:1px solid var(--border);'
        f'border-radius:10px;background:var(--surface)">'
        f'{gui.icon(n, size=26)}'
        f'<code style="font-size:11px;color:var(--text-2)">{n}</code>'
        f'</div>'
        for n in names
    )
    return (f'<div style="display:grid;gap:10px;'
            f'grid-template-columns:repeat(auto-fill,minmax(104px,1fr))">'
            f'{cells}</div>')


@gui.app("Rail & Icon Showcase", width=860, height=620)
def ui():
    with gui.row(gap=0, style="height:100vh"):

        # ── Vertical rail: a compact sidebar ───────────────────────────────
        with gui.col(padding=10, style="background:var(--surface-2);"
                                        "border-right:1px solid var(--border)"):
            page = gui.rail(NAV, key="nav")   # vertical is the default

        # ── Main panel switches on the active rail item ────────────────────
        with gui.scroll(max_height=600):
          with gui.col(padding=24, gap=16, fill=True):

            if page == "Rails":
                gui.title("Button rails")
                gui.text("The strip on the left is a vertical rail — it fits "
                         "four destinations in the width one tab label would "
                         "need. Below is a horizontal rail used as a sub-toolbar.",
                         muted=True)

                # A horizontal rail makes a neat in-page sub-toolbar.
                view = gui.rail(
                    [
                        {"label": "Bars",  "icon": gui.icon("bar-chart-3")},
                        {"label": "Lines", "icon": gui.icon("line-chart")},
                        {"label": "Area",  "icon": gui.icon("area-chart")},
                        {"label": "Table", "icon": gui.icon("table")},
                    ],
                    orientation="horizontal", border=True, key="chart-view",
                )

                with gui.card(gap=10):
                    if view == "Table":
                        gui.table(SAMPLE)
                    else:
                        gui.text(f"Showing the {view} view.", bold=True,
                                 style="color:var(--primary)")
                        gui.text("(Swap in gui.figure() here in a real app.)",
                                 muted=True, size="sm")

            elif page == "Icons":
                gui.title("Icon gallery")
                gui.text("gui.icon(\"name\") returns inline SVG for any of ~2100 "
                         "Lucide icons. Browse them all at lucide.dev/icons.",
                         muted=True)
                for group, names in GALLERY.items():
                    gui.text(group, bold=True, size="sm", muted=True,
                             style="text-transform:uppercase;letter-spacing:.06em")
                    gui.html(icon_grid(names))

            elif page == "Sizing":
                gui.title("Sizes & colour")
                gui.text("Pass size= for pixels; icons stroke in currentColor, "
                         "so a style= colour (or a coloured parent) recolours them.",
                         muted=True)

                with gui.card(gap=12):
                    gui.text("size = 16 / 24 / 32 / 48", bold=True, size="sm")
                    gui.html(
                        '<div style="display:flex;align-items:center;gap:20px;'
                        'color:var(--text)">'
                        + gui.icon("activity", size=16)
                        + gui.icon("activity", size=24)
                        + gui.icon("activity", size=32)
                        + gui.icon("activity", size=48)
                        + '</div>'
                    )

                with gui.card(gap=12):
                    gui.text("colour via style=", bold=True, size="sm")
                    gui.html(
                        '<div style="display:flex;align-items:center;gap:20px">'
                        + gui.icon("droplet",  size=32, style="color:var(--primary)")
                        + gui.icon("sun",      size=32, style="color:#f59e0b")
                        + gui.icon("leaf",     size=32, style="color:#16a34a")
                        + gui.icon("triangle-alert", size=32, style="color:var(--danger)")
                        + '</div>'
                    )

                with gui.card(gap=12):
                    gui.text("stroke = 1 / 1.5 / 2 / 3", bold=True, size="sm")
                    gui.html(
                        '<div style="display:flex;align-items:center;gap:20px;'
                        'color:var(--text)">'
                        + gui.icon("settings", size=32, stroke=1)
                        + gui.icon("settings", size=32, stroke=1.5)
                        + gui.icon("settings", size=32, stroke=2)
                        + gui.icon("settings", size=32, stroke=3)
                        + '</div>'
                    )

            elif page == "About":
                gui.title("About")
                gui.text("gui.icon() renders only where raw markup is allowed: "
                         "inside a gui.rail() item, or wrapped in gui.html(). "
                         "Text widgets like gui.button()/gui.text() escape their "
                         "content, so an icon passed there would show as markup.",
                         muted=True)
                gui.text("You can always pass your own <svg>…</svg> string "
                         "anywhere an icon is expected — the bundled set is a "
                         "convenience, not a requirement.", muted=True)


gui.run()
