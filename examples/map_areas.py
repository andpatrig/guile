"""
examples/map_areas.py — Python-owned drawn areas with labels and selection.

One list of "areas" drives everything: shapes drawn with the toolbar are
appended to it, the edit/delete toolbars update it, clicking selects, and
the same list can be exported as GeoJSON (so a user can draw plot
boundaries once and load the file next time).

Run from the project root:
    python examples/map_areas.py
"""

import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
areas    = gui.state([])      # [{"id", "type", "coords"}, ...]
selected = gui.state(None)    # id of the selected area
hovered  = gui.state(None)
_ids     = itertools.count(1)

# ── Callbacks: create / edit / delete come from the map toolbar ────────────
def add_area(shape_type, coords):
    areas.update(lambda a: a + [{"id": f"A{next(_ids)}",
                                 "type": shape_type, "coords": coords}])

def edit_area(area_id, shape_type, coords):
    areas.update(lambda a: [dict(x, coords=coords) if x["id"] == area_id else x
                            for x in a])

def delete_area(area_id):
    areas.update(lambda a: [x for x in a if x["id"] != area_id])
    if selected.value == area_id:
        selected.set(None)

def to_geojson(area_list):
    """Drawn areas → GeoJSON FeatureCollection (lon/lat order)."""
    feats = []
    for a in area_list:
        c = a["coords"]
        if a["type"] in ("polygon", "rectangle"):
            ring = [[lon, lat] for lat, lon in c] + [[c[0][1], c[0][0]]]
            geom = {"type": "Polygon", "coordinates": [ring]}
        elif a["type"] == "polyline":
            geom = {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in c]}
        else:                                       # circle / marker → point
            geom = {"type": "Point", "coordinates": [c["lng"], c["lat"]]}
        props = {"id": a["id"]}
        if a["type"] == "circle":
            props["radius_m"] = c["radius"]
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Map Areas", width=940, height=660)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.row(justify="space-between", align="center"):
            gui.title("Draw, edit and select areas")
            gui.text("Draw with the toolbar; use its edit/delete tools to change shapes",
                     muted=True, size="sm")

        with gui.row(gap=14, fill=True):

            # ── Map ──────────────────────────────────────────────────────────
            with gui.col(fill=True):
                # Neon outline for all areas; the selected / hovered one
                # gets a per-shape style override and every shape a label.
                shapes = []
                for a in areas.value:
                    s = dict(a, label=a["id"])
                    if a["id"] == selected.value:
                        s["style"] = {"color": "#ffdd00", "weight": 4, "fill_opacity": 0.25}
                    elif a["id"] == hovered.value:
                        s["style"] = {"weight": 5}
                    shapes.append(s)
                with gui.card(padding=8):
                    gui.leaflet(center=(39.19, -96.58), zoom=15, height=520,
                                tiles="satellite",
                                draw=["polygon", "rectangle", "circle"],
                                drawn=shapes,
                                draw_style={"color": "#39ff14", "weight": 3,
                                            "fill_opacity": 0.05},
                                on_shape=add_area,
                                on_shape_edit=edit_area,
                                on_shape_delete=delete_area,
                                on_shape_click=selected.set,
                                on_shape_hover=hovered.set,
                                key="areas-map")

            # ── Sidebar ─────────────────────────────────────────────────────
            with gui.col(gap=8, style="width:250px;flex-shrink:0"):
                with gui.card(gap=8, padding=14):
                    with gui.row(justify="space-between", align="center"):
                        gui.text("Areas", bold=True, size="sm")
                        if areas.value:
                            gui.button("Clear all", variant="ghost", size="sm",
                                       on_click=lambda: (areas.set([]), selected.set(None)),
                                       key="clear")
                    if not areas.value:
                        gui.text("Nothing drawn yet.", muted=True, size="sm")
                    for a in areas.value:
                        is_sel = a["id"] == selected.value
                        with gui.row(justify="space-between", align="center",
                                     style="background:var(--surface-2);"
                                           "border-radius:6px;padding:6px 10px;"
                                           + ("outline:2px solid #ffdd00;" if is_sel else "")):
                            gui.text(f"{a['id']} · {a['type']}", size="sm",
                                     bold=is_sel)
                            gui.button("Select", variant="ghost", size="sm",
                                       on_click=lambda i=a["id"]: selected.set(i),
                                       key=f"sel-{a['id']}")

                with gui.card(gap=6, padding=14):
                    gui.text("Export", bold=True, size="sm")
                    n = len(to_geojson(areas.value)["features"])
                    gui.text(f"{n} feature(s) ready as GeoJSON — "
                             "json.dump(to_geojson(areas.value), f) writes the "
                             "plot file for next time.", size="sm", muted=True)

gui.run()
