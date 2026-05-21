"""
examples/04_geo_data.py — Matplotlib plots + interactive Leaflet map.

A small seismicity explorer:
  - Slider to filter earthquakes by minimum magnitude
  - Matplotlib scatter plot of magnitudes vs depth
  - Leaflet map showing epicentres as markers

Run:
    pip install matplotlib
    python examples/04_geo_data.py

Note: map tiles require an internet connection.
      matplotlib is the only extra dependency.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

# ── Fake seismicity dataset (lat, lon, mag, depth_km) ─────────────────────
import random
random.seed(42)

import matplotlib
matplotlib.use("Agg")  # set non-interactive backend once at module level

QUAKES = [
    {"lat": 35.6 + random.uniform(-2, 2),
     "lon": 139.7 + random.uniform(-3, 3),
     "mag": round(random.uniform(1.5, 6.5), 1),
     "depth": round(random.uniform(5, 200), 1)}
    for _ in range(120)
]

# ── App state ─────────────────────────────────────────────────────────────
min_mag = gui.state(2.5)


# ── Helpers ───────────────────────────────────────────────────────────────
def filtered():
    return [q for q in QUAKES if q["mag"] >= min_mag.value]


def make_scatter(quakes):
    """Magnitude vs depth scatter, coloured by magnitude."""
    import matplotlib.pyplot as plt

    mags   = [q["mag"]   for q in quakes]
    depths = [q["depth"] for q in quakes]

    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    fig.patch.set_alpha(0)           # transparent background → blends with theme
    ax.set_facecolor("#f9f9fb")

    sc = ax.scatter(mags, depths,
                    c=mags, cmap="plasma",
                    s=[m**2.5 * 6 for m in mags],
                    alpha=0.75, edgecolors="none")
    plt.colorbar(sc, ax=ax, label="Magnitude")
    ax.set_xlabel("Magnitude")
    ax.set_ylabel("Depth (km)")
    ax.invert_yaxis()   # shallow at top
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def make_markers(quakes):
    return [
        gui.Marker(
            (q["lat"], q["lon"]),
            popup=f"M {q['mag']} — {q['depth']} km deep",
            tooltip=f"M {q['mag']}",
        )
        for q in quakes
    ]


# ── UI ────────────────────────────────────────────────────────────────────
@gui.app("Seismicity Explorer", width=680, height=760)
def ui():
    quakes = filtered()

    with gui.col(padding=20, gap=16, style="min-height:100vh"):

        # ── Header
        with gui.row(justify="space-between", align="center"):
            gui.title("Seismicity Explorer")
            gui.badge(f"{len(quakes)} events", variant="primary")

        # ── Filter
        with gui.card(gap=10, padding=14):
            mag_filter = gui.slider(
                "Minimum magnitude",
                min=1.5, max=6.0, step=0.1,
                value=min_mag,        # bound to our State
                key="mag-filter",
            )
            with gui.row(gap=8):
                gui.badge(f"M ≥ {mag_filter.value:.1f}", variant="warning")
                gui.text(f"showing {len(quakes)} of {len(QUAKES)}",
                       muted=True, size="sm")

        # ── Scatter plot
        with gui.card(gap=8, padding=14):
            gui.text("Magnitude vs. Depth", bold=True, size="sm",
                   style="color:var(--text-2)")
            if quakes:
                fig = make_scatter(quakes)
                gui.figure(fig, dpi=110, caption="Shallow events (top) vs. deep")
            else:
                with gui.col(align="center", style="padding:24px"):
                    gui.text("No events match the filter.", muted=True)

        # ── Map
        with gui.card(gap=8, padding=14):
            gui.text("Epicentres", bold=True, size="sm",
                   style="color:var(--text-2)")
            gui.leaflet(
                center=(35.6, 139.7),
                zoom=6,
                height=340,
                markers=make_markers(quakes),
                key="quake-map",
            )
