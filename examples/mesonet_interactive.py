"""
examples/mesonet_interactive.py — Bidirectional Leaflet map demo.

Demonstrates all map callback types:
  • Marker.on_click  — click a station → show station details in a sidebar
  • leaflet on_click — click map background → display lat/lon
  • leaflet on_move  — pan/zoom → keep view state in sync

Run from the project root:
    python mesonet_interactive.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── Station data ───────────────────────────────────────────────────────────
STATIONS = [
    ("Manhattan",        "Riley",      39.2086,  -96.5917),
    ("Konza Prairie",    "Riley",      39.0884,  -96.5458),
    ("Ashland Bottoms",  "Riley",      39.1258,  -96.6365),
    ("Hiawatha",         "Brown",      39.8424,  -95.4819),
    ("Miami",            "Miami",      38.5923,  -94.8479),
    ("Clay",             "Clay",       39.4180,  -97.1398),
    ("Colby",            "Thomas",     39.3925, -101.0686),
    ("Cheyenne",         "Cheyenne",   39.6265, -101.8075),
    ("Hill City",        "Graham",     39.3741,  -99.8299),
    ("Hays",             "Ellis",      38.8495,  -99.3446),
    ("Jewell",           "Jewell",     39.6834,  -98.2131),
    ("Belleville 2W",    "Republic",   39.8141,  -97.6751),
    ("Cherokee",         "Cherokee",   37.1990,  -94.9809),
    ("Butler",           "Butler",     37.8043,  -96.8831),
    ("Howard 14NW",      "Elk",        37.5501,  -96.4913),
    ("Haysville",        "Sedgwick",   37.5198,  -97.3121),
    ("Hutchinson 10SW",  "Reno",       37.9310,  -98.0200),
    ("Harper",           "Harper",     37.0648,  -98.0847),
    ("Garden City",      "Finney",     37.9973, -100.8151),
    ("Grant",            "Grant",      37.6496, -101.3664),
    ("Meade",            "Meade",      37.1348, -100.3956),
    ("Hamilton",         "Hamilton",   37.9764, -101.7690),
    ("Lakin",            "Kearny",     37.8937, -101.2326),
    ("Ashland 8S",       "Clark",      37.0648,  -99.7511),
    ("Greensburg",       "Kiowa",      37.6028,  -99.2926),
]

# ── State ──────────────────────────────────────────────────────────────────
selected_station = gui.state(None)
map_click        = gui.state(None)
map_view         = gui.state({"center": (38.5, -98.5), "zoom": 6})

# ── Callbacks ──────────────────────────────────────────────────────────────
def on_station_click(name, county, lat, lon):
    selected_station.set({"name": name, "county": county, "lat": lat, "lon": lon})
    map_click.set(None)

def on_map_click(lat, lon):
    map_click.set((lat, lon))
    selected_station.set(None)

def on_map_move(center, zoom):
    map_view.set({"center": center, "zoom": zoom})

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("KS Mesonet — Interactive", width=860, height=680)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.row(justify="space-between", align="center"):
            gui.title("Kansas Mesonet")
            gui.text("Interactive map demo", muted=True, size="sm")

        with gui.row(gap=14, fill=True):

            # ── Map ─────────────────────────────────────────────────────────
            with gui.col(gap=8, fill=True):
                with gui.card(padding=8):
                    markers = [
                        gui.Marker(
                            (lat, lon),
                            tooltip=name,
                            popup=f"<b>{name}</b><br>{county} County<br>"
                                  f"{lat:.4f}°N, {abs(lon):.4f}°W",
                            on_click=(lambda n=name, c=county, la=lat, lo=lon:
                                      on_station_click(n, c, la, lo)),
                        )
                        for name, county, lat, lon in STATIONS
                    ]
                    gui.leaflet(
                        center=map_view.value["center"],
                        zoom=map_view.value["zoom"],
                        height=500,
                        markers=markers,
                        on_click=on_map_click,
                        on_move=on_map_move,
                        key="ks-map",
                    )
                c = map_view.value["center"]
                z = map_view.value["zoom"]
                gui.text(
                    f"View  {c[0]:.4f}°N, {abs(c[1]):.4f}°W  ·  zoom {z}",
                    muted=True, size="sm", style="text-align:center",
                )

            # ── Sidebar ──────────────────────────────────────────────────────
            with gui.col(gap=8, style="width:220px;flex-shrink:0"):
                s = selected_station.value
                if s:
                    with gui.card(gap=10, padding=14):
                        gui.text("Station", muted=True, size="sm",
                                 style="text-transform:uppercase;letter-spacing:.06em")
                        gui.title(s["name"], style="font-size:17px")
                        gui.divider()
                        gui.text(f"County:  {s['county']}", size="sm")
                        gui.text(f"Lat:     {s['lat']:.4f}°N", size="sm")
                        gui.text(f"Lon:     {abs(s['lon']):.4f}°W", size="sm")
                        gui.button("Clear", variant="ghost", size="sm",
                                   on_click=lambda: selected_station.set(None),
                                   key="clear-station")

                mc = map_click.value
                if mc:
                    with gui.card(gap=8, padding=14):
                        gui.text("Map click", muted=True, size="sm",
                                 style="text-transform:uppercase;letter-spacing:.06em")
                        gui.text(f"{mc[0]:.5f}°N", bold=True)
                        gui.text(f"{abs(mc[1]):.5f}°W", bold=True)
                        gui.button("Clear", variant="ghost", size="sm",
                                   on_click=lambda: map_click.set(None),
                                   key="clear-click")

                if not s and not mc:
                    with gui.card(gap=6, padding=14):
                        gui.text("Click a marker or the map to see details.",
                                 muted=True, size="sm")
