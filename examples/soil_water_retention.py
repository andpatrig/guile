"""
examples/soil_water_retention.py — Soil water retention curve explorer.

Demonstrates:
  - Dropdown that initialises sliders with soil-specific defaults
  - Sliders that update a matplotlib figure in real time
  - gui.state() coordinating multiple widgets

The van Genuchten (1980) model:
    θ(h) = θ_r + (θ_s - θ_r) / (1 + |α·h|^n)^m
    where m = 1 - 1/n

Run:
    pip install matplotlib numpy
    python examples/soil_water_retention.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import guile as gui


# ── Van Genuchten parameters for four textural classes ────────────────────
# Keys: θ_r, θ_s, α (1/cm), n
SOILS = {
    "Sand":        dict(theta_r=0.045, theta_s=0.430, alpha=0.145, n=2.68),
    "Sandy loam":  dict(theta_r=0.065, theta_s=0.410, alpha=0.075, n=1.89),
    "Silt loam":   dict(theta_r=0.067, theta_s=0.450, alpha=0.020, n=1.41),
    "Clay":        dict(theta_r=0.068, theta_s=0.380, alpha=0.008, n=1.09),
}

SOIL_NAMES = list(SOILS.keys())


# ── State ─────────────────────────────────────────────────────────────────
soil_name = gui.state("Sandy loam")

_def    = SOILS["Sandy loam"]
theta_r = gui.state(_def["theta_r"])
theta_s = gui.state(_def["theta_s"])
alpha   = gui.state(_def["alpha"])
n_param = gui.state(_def["n"])


def sync_sliders(name):
    """Reset all four slider states when a new soil class is selected."""
    p = SOILS[name]
    theta_r.set(round(p["theta_r"], 3))
    theta_s.set(round(p["theta_s"], 3))
    alpha.set(  round(p["alpha"],   3))
    n_param.set(round(p["n"],       2))


# ── Physics ───────────────────────────────────────────────────────────────
def van_genuchten(h, theta_r, theta_s, alpha, n):
    m = 1.0 - 1.0 / n
    return theta_r + (theta_s - theta_r) / (1.0 + (alpha * h) ** n) ** m


def make_figure():
    h = np.logspace(0, 5, 400)   # suction 1 → 100 000 cm
    θ = van_genuchten(h, theta_r.value, theta_s.value,
                      alpha.value, n_param.value)

    fig, ax = plt.subplots(figsize=(5, 4))
    fig.patch.set_alpha(0)
    ax.set_facecolor("#f9f9fb")

    ax.semilogx(h, θ, color="#6366f1", lw=2.5, label=soil_name.value)
    ax.axhline(theta_r.value, color="#94a3b8", lw=1.2,
               ls="--", label=f"θ_r = {theta_r.value:.3f}")
    ax.axhline(theta_s.value, color="#94a3b8", lw=1.2,
               ls=":",  label=f"θ_s = {theta_s.value:.3f}")

    ax.set_xlabel("Suction head |h|  (cm)", fontsize=11)
    ax.set_ylabel("Water content θ  (cm³ cm⁻³)", fontsize=11)
    ax.set_ylim(0, 0.65)
    ax.set_xlim(1, 1e5)
    ax.legend(fontsize=9, framealpha=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, which="both", ls="--", alpha=0.25)
    fig.tight_layout()
    return fig


# ── UI ────────────────────────────────────────────────────────────────────
@gui.app("Soil Water Retention", width=800, height=600)
def ui():

    with gui.col(padding=10, style="min-height:100vh"):
        with gui.card():
            gui.title("Soil Water Retention")
            gui.text("van Genuchten (1980) model  ·  adjust parameters below", muted=True, size="sm")

        with gui.row(gap=12, align="flex-start"):

            # ── Controls — proportional width (2 parts of 5)
            with gui.col(padding=10, gap=16, style="flex:2"):

                with gui.card(gap=14, padding=16):

                    gui.select(
                        SOIL_NAMES,
                        "Soil textural class",
                        value=soil_name,
                        key="soil-sel",
                        on_change=sync_sliders,
                    )

                    gui.divider()

                    gui.slider("θ_r  — residual water content",
                               min=0.010, max=0.150, step=0.001,
                               value=theta_r, key="sl-tr",
                               on_change=theta_r.set)

                    gui.slider("θ_s  — saturated water content",
                               min=0.200, max=0.650, step=0.001,
                               value=theta_s, key="sl-ts",
                               on_change=theta_s.set)

                    gui.slider("α  — inverse air-entry pressure (1/cm)",
                               min=0.001, max=0.300, step=0.001,
                               value=alpha, key="sl-al",
                               on_change=alpha.set)

                    gui.slider("n  — pore-size distribution index",
                               min=1.01, max=4.00, step=0.01,
                               value=n_param, key="sl-n",
                               on_change=n_param.set)

            # ── Chart — proportional width (3 parts of 5)
            with gui.col(padding=10, gap=12, style="flex:3"):

                with gui.card(padding=14):
                    gui.figure(make_figure(), dpi=110)
