"""
examples/weather_explorer.py — Synthetic weather data explorer.

Generates a year of daily air temperature and solar radiation data
using a noisy sine wave. Filter by date range, view the table,
and see a chart of the selected window — controls live in a sidebar
so adjusting them doesn't scroll the chart and table out of view.

Run:
    pip install matplotlib numpy pandas
    python examples/weather_explorer.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

import guile as gui

# ── Generate synthetic dataset once at startup ────────────────────────────
_rng   = np.random.default_rng(42)
_dates = pd.date_range("2024-01-01", periods=365, freq="D")
_doy   = np.arange(1, 366)

# Air temperature: seasonal sine + daily noise (°C)
_temp  = 10 + 18 * np.sin(2 * np.pi * (_doy - 80) / 365) + _rng.normal(0, 2.5, 365)

# Solar radiation: seasonal sine (always positive) + noise (MJ/m²/day)
_sr    = 15 + 10 * np.sin(2 * np.pi * (_doy - 80) / 365) + _rng.normal(0, 1.5, 365)
_sr    = np.clip(_sr, 1.0, 35.0)

FULL_DF = pd.DataFrame({
    "date":       _dates,
    "temp_c":     _temp.round(1),
    "solar_mj":   _sr.round(2),
})

# ── State ──────────────────────────────────────────────────────────────────
start_date = gui.state("2024-01-01")
end_date   = gui.state("2024-12-31")
show_var   = gui.state("temp_c")

# ── Helpers ───────────────────────────────────────────────────────────────
def filtered_df():
    mask = (
        (FULL_DF["date"] >= pd.Timestamp(start_date.value)) &
        (FULL_DF["date"] <= pd.Timestamp(end_date.value))
    ) if start_date.value and end_date.value else pd.Series(True, index=FULL_DF.index)
    return FULL_DF[mask].reset_index(drop=True)


def make_figure(df):
    col   = show_var.value
    label = "Air Temperature (°C)" if col == "temp_c" else "Solar Radiation (MJ/m²/day)"
    color = "#ef4444" if col == "temp_c" else "#f59e0b"

    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor("#f9f9fb")

    ax.plot(df["date"], df[col], color=color, lw=1.5, alpha=0.9)
    ax.fill_between(df["date"], df[col], df[col].min(),
                    color=color, alpha=0.12)
    ax.set_ylabel(label, fontsize=10)
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y", ls="--", alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    return fig


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Weather Explorer", width=980, height=680)
def ui():
    df = filtered_df()

    with gui.row(gap=0, style="min-height:100vh"):

        # ── Sidebar — controls ───────────────────────────────────────
        with gui.col(
            padding=16, gap=14,
            style="width:240px;flex-shrink:0;"
                  "border-right:1px solid var(--border);"
                  "background:var(--surface)"
        ):
            gui.title("Weather Explorer", size="lg")
            gui.badge(f"{len(df)} days selected", variant="primary")
            gui.divider()

            gui.date_input("From", value=start_date,
                           on_change=start_date.set, key="from")
            gui.date_input("To",   value=end_date,
                           on_change=end_date.set,   key="to")
            gui.select(
                [("temp_c",   "Air temperature (°C)"),
                 ("solar_mj", "Solar radiation (MJ/m²/day)")],
                "Variable",
                value=show_var, on_change=show_var.set, key="var"
            )

            if len(df) > 0:
                col = show_var.value
                gui.divider()
                gui.text(f"Mean:  {df[col].mean():.2f}", bold=True)
                gui.text(f"Min:   {df[col].min():.2f}", muted=True)
                gui.text(f"Max:   {df[col].max():.2f}", muted=True)

        # ── Main — chart + table ────────────────────────────────────
        with gui.col(padding=16, gap=14, fill=True):
            if len(df) > 1:
                with gui.card(padding=12):
                    gui.figure(make_figure(df), dpi=110)

            with gui.card(padding=0, fill=True, style="overflow-y:auto"):
                gui.table(
                    df.assign(date=df["date"].dt.strftime("%Y-%m-%d")),
                    columns=["date","temp_c","solar_mj"]
                )
