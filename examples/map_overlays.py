"""
examples/map_overlays.py — Image overlay + GeoJSON on a map.

Drapes a georeferenced raster (here a synthetic "NDVI" image generated on
the fly, so the example needs no files) over satellite imagery, draws plot
boundaries from GeoJSON on top, and reacts when a plot is clicked.

For large drone mosaics, do NOT embed the image — pre-tile it and use
gui.TileOverlay instead (see the comment near the bottom).

Run from the project root:
    python examples/map_overlays.py
"""

import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
import guile as gui

# ── Field extent (a quarter-section near Manhattan, KS) ────────────────────
SOUTH, WEST, NORTH, EAST = 39.180, -96.600, 39.200, -96.575
BOUNDS = ((SOUTH, WEST), (NORTH, EAST))

# ── A stand-in raster: smooth "vegetation index" surface rendered to PNG ───
# In a real app this would be a PNG/JPG exported from your GeoTIFF, plus the
# lat/lon corners of that image.
def make_ndvi_png() -> bytes:
    y, x = np.mgrid[0:200, 0:250] / 100.0
    ndvi = 0.5 + 0.3 * np.sin(x * 2) * np.cos(y * 3) + 0.1 * np.random.rand(200, 250)
    buf = io.BytesIO()
    plt.imsave(buf, ndvi, cmap="RdYlGn", vmin=0, vmax=1, format="png")
    return buf.getvalue()

NDVI_PNG = make_ndvi_png()

# ── Plot boundaries as GeoJSON (a 3 × 2 grid of rectangles) ────────────────
def make_plots() -> dict:
    feats = []
    cols, rows = 3, 2
    dlon = (EAST - WEST) / cols
    dlat = (NORTH - SOUTH) / rows
    treatments = ["Control", "Low N", "High N"]
    for r in range(rows):
        for c in range(cols):
            w, e = WEST + c * dlon, WEST + (c + 1) * dlon
            s, n = SOUTH + r * dlat, SOUTH + (r + 1) * dlat
            feats.append({
                "type": "Feature",
                "properties": {"plot_id": f"P{r * cols + c + 1}",
                               "treatment": treatments[c],
                               "rep": r + 1},
                "geometry": {"type": "Polygon",
                             "coordinates": [[[w, s], [e, s], [e, n],
                                              [w, n], [w, s]]]},   # lon, lat
            })
    return {"type": "FeatureCollection", "features": feats}

PLOTS = make_plots()

# ── State ──────────────────────────────────────────────────────────────────
opacity    = gui.state(0.7)
show_image = gui.state(True)
selected   = gui.state(None)      # properties dict of the clicked plot

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Map Overlays", width=900, height=640)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.row(justify="space-between", align="center"):
            gui.title("Image overlay + GeoJSON")
            gui.text("Click a plot to select it", muted=True, size="sm")

        with gui.row(gap=14, fill=True):

            # ── Map ──────────────────────────────────────────────────────────
            with gui.col(fill=True):
                layers = []
                if show_image.value:
                    layers.append(gui.ImageOverlay(NDVI_PNG, bounds=BOUNDS,
                                                   opacity=opacity.value))
                layers.append(gui.GeoJSON(
                    PLOTS, color="#ffffff", weight=2, fill_opacity=0.05,
                    popup=lambda p: f"<b>{p['plot_id']}</b><br>{p['treatment']}",
                    on_click=selected.set,
                ))
                # For a large drone mosaic, replace the ImageOverlay with:
                #   gui.TileOverlay("http://localhost:8000/tiles/{z}/{x}/{y}.png",
                #                   max_zoom=21, bounds=BOUNDS)
                # after `gdal2tiles.py --xyz -z 14-21 mosaic.tif tiles/` and
                # `python -m http.server 8000` in the tiles' parent folder.
                with gui.card(padding=8):
                    gui.leaflet(center=((SOUTH + NORTH) / 2, (WEST + EAST) / 2),
                                zoom=15, height=500, tiles="satellite",
                                layers=layers, key="field-map")

            # ── Controls / selection ─────────────────────────────────────────
            with gui.col(gap=8, style="width:240px;flex-shrink:0"):
                with gui.card(gap=10, padding=14):
                    gui.text("Raster", bold=True, size="sm")
                    gui.checkbox("Show NDVI image", value=show_image,
                                 on_change=show_image.set, key="show-img")
                    gui.slider("Opacity", min=0, max=1, step=0.05,
                               value=opacity, on_change=opacity.set,
                               key="opacity")

                with gui.card(gap=6, padding=14):
                    gui.text("Selected plot", bold=True, size="sm")
                    props = selected.value if isinstance(selected.value, dict) else None
                    if not props:
                        gui.text("Nothing selected.", muted=True, size="sm")
                    else:
                        gui.badge(props.get("plot_id", "?"), variant="primary")
                        gui.text(f"Treatment: {props.get('treatment')}", size="sm")
                        gui.text(f"Rep: {props.get('rep')}", size="sm", muted=True)

gui.run()
