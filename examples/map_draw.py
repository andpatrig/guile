"""
examples/map_draw.py — Map drawing tools demo.

Shows how to use draw= to enable polygon/rectangle/circle drawing,
and how on_shape= receives each completed shape in Python.

Run from the project root:
    python map_draw.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
shapes = gui.state([])   # list of {"type": str, "coords": ...}

def on_shape(shape_type, coords):
    def fmt(c):
        if isinstance(c, list):
            return f"{len(c)} points"
        if isinstance(c, dict) and "radius" in c:
            return f"r={c['radius']:.0f} m @ {c['lat']:.4f},{c['lng']:.4f}"
        return f"{c['lat']:.4f},{c['lng']:.4f}"
    shapes.update(lambda s: s + [{"type": shape_type, "summary": fmt(coords)}])

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Map Draw Tools", width=860, height=640)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.row(justify="space-between", align="center"):
            gui.title("Map Drawing Tools")
            gui.text("Use the toolbar on the map to draw shapes",
                     muted=True, size="sm")

        with gui.row(gap=14, fill=True):

            # ── Map ──────────────────────────────────────────────────────────
            with gui.col(fill=True):
                with gui.card(padding=8):
                    gui.leaflet(
                        center=(38.5, -98.5),
                        zoom=6,
                        height=500,
                        draw=["rectangle", "polygon", "polyline",
                              "circle", "marker"],
                        on_shape=on_shape,
                        key="draw-map",
                    )

            # ── Shape log ────────────────────────────────────────────────────
            with gui.col(gap=8, style="width:220px;flex-shrink:0"):
                with gui.card(gap=10, padding=14):
                    with gui.row(justify="space-between", align="center"):
                        gui.text("Drawn shapes", bold=True, size="sm")
                        if shapes.value:
                            gui.button("Clear", variant="ghost", size="sm",
                                       on_click=lambda: shapes.set([]),
                                       key="clear-shapes")

                    if not shapes.value:
                        gui.text("Nothing drawn yet.", muted=True, size="sm")
                    else:
                        for i, s in enumerate(shapes.value):
                            with gui.card(gap=4, padding=10,
                                          style="background:var(--surface-2)"):
                                gui.badge(s["type"], variant="primary")
                                gui.text(s["summary"], size="sm", muted=True)
