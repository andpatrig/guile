"""
examples/mesonet_map.py — Kansas Mesonet station map.

Shows ~25 KS Mesonet stations on an interactive Leaflet map.
Click a marker to see the station name and county.
Use the multiselect to filter by region — the map updates immediately,
without losing sight of the filter controls.

Run:
    python examples/mesonet_map.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── Station data (name, county, lat, lon) ─────────────────────────────────
# Selected from https://mesonet.k-state.edu/rest/stationnames/
# covering all four quadrants of Kansas
STATIONS = [
    # Northeast
    ("Manhattan",        "Riley",      39.2086,  -96.5917),
    ("Konza Prairie",    "Riley",      39.0884,  -96.5458),
    ("Ashland Bottoms",  "Riley",      39.1258,  -96.6365),
    ("Hiawatha",         "Brown",      39.8424,  -95.4819),
    ("Miami",            "Miami",      38.5923,  -94.8479),
    ("Clay",             "Clay",       39.4180,  -97.1398),
    # Northwest
    ("Colby",            "Thomas",     39.3925, -101.0686),
    ("Cheyenne",         "Cheyenne",   39.6265, -101.8075),
    ("Hill City",        "Graham",     39.3741,  -99.8299),
    ("Hays",             "Ellis",      38.8495,  -99.3446),
    ("Jewell",           "Jewell",     39.6834,  -98.2131),
    ("Belleville 2W",    "Republic",   39.8141,  -97.6751),
    # Southeast
    ("Cherokee",         "Cherokee",   37.1990,  -94.9809),
    ("Butler",           "Butler",     37.8043,  -96.8831),
    ("Howard 14NW",      "Elk",        37.5501,  -96.4913),
    ("Haysville",        "Sedgwick",   37.5198,  -97.3121),
    ("Hutchinson 10SW",  "Reno",       37.9310,  -98.0200),
    ("Harper",           "Harper",     37.0648,  -98.0847),
    # Southwest
    ("Garden City",      "Finney",     37.9973, -100.8151),
    ("Grant",            "Grant",      37.6496, -101.3664),
    ("Meade",            "Meade",      37.1348, -100.3956),
    ("Hamilton",         "Hamilton",   37.9764, -101.7690),
    ("Lakin",            "Kearny",     37.8937, -101.2326),
    ("Ashland 8S",       "Clark",      37.0648,  -99.7511),
    ("Greensburg",       "Kiowa",      37.6028,  -99.2926),
]

REGIONS = {
    "Northeast": ["Manhattan","Konza Prairie","Ashland Bottoms","Hiawatha","Miami","Clay"],
    "Northwest": ["Colby","Cheyenne","Hill City","Hays","Jewell","Belleville 2W"],
    "Southeast": ["Cherokee","Butler","Howard 14NW","Haysville","Hutchinson 10SW","Harper"],
    "Southwest": ["Garden City","Grant","Meade","Hamilton","Lakin","Ashland 8S","Greensburg"],
}
ALL_REGIONS = list(REGIONS.keys())

# ── State ──────────────────────────────────────────────────────────────────
selected_regions = gui.state(ALL_REGIONS)

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("KS Mesonet Stations", width=860, height=640)
def ui():
    with gui.row(gap=0, style="min-height:100vh"):

        active_names = {
            name
            for region in selected_regions.value
            for name in REGIONS.get(region, [])
        }
        visible = [s for s in STATIONS if s[0] in active_names]

        # ── Sidebar — filter controls ───────────────────────────────
        with gui.col(
            padding=16, gap=12,
            style="width:220px;flex-shrink:0;"
                  "border-right:1px solid var(--border);"
                  "background:var(--surface)"
        ):
            gui.title("Kansas Mesonet", size="lg")
            gui.text("Weather station network", muted=True, size="sm")
            gui.divider()

            gui.multiselect(
                ALL_REGIONS, "Show regions",
                value=selected_regions, on_change=selected_regions.set,
                rows=4, key="regions"
            )

            gui.spacer(h=4)
            gui.badge(f"{len(visible)} stations", variant="primary")
            for region in selected_regions.value:
                gui.badge(region, variant="neutral")

        # ── Main — map ──────────────────────────────────────────────
        with gui.col(padding=16, fill=True):
            with gui.card(padding=8, fill=True):
                markers = [
                    gui.Marker(
                        (lat, lon),
                        popup=f"<b>{name}</b><br>{county} County",
                        tooltip=name,
                    )
                    for name, county, lat, lon in visible
                ]
                gui.leaflet(
                    center=(38.5, -98.5),
                    zoom=6,
                    height=560,
                    markers=markers,
                    key="ks-map",
                )
