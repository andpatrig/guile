"""
examples/05_weather_explorer.py — Synthetic weather data explorer.

Generates a year of daily air temperature and solar radiation data
using a noisy sine wave. Filter by date range, view the table,
and see a chart of the selected window.

Run:
    pip install matplotlib numpy pandas
    python examples/05_weather_explorer.py
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
@gui.app("Weather Explorer", width=820, height=700)
def ui():
    df = filtered_df()

    with gui.col(padding=20, gap=14, style="min-height:100vh"):

        with gui.row(justify="space-between", align="center"):
            gui.title("Weather Explorer")
            gui.badge(f"{len(df)} days selected", variant="primary")

        # ── Controls
        with gui.card(gap=12, padding=14):
            with gui.row(gap=16, align="flex-end"):
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
                with gui.row(gap=20):
                    gui.text(f"Mean:  {df[col].mean():.2f}", bold=True)
                    gui.text(f"Min:   {df[col].min():.2f}", muted=True)
                    gui.text(f"Max:   {df[col].max():.2f}", muted=True)

        # ── Chart
        if len(df) > 1:
            with gui.card(padding=12):
                gui.figure(make_figure(df), dpi=110)

        # ── Table
        with gui.card(padding=0, style="overflow-y:auto;max-height:260px"):
            gui.table(
                df.assign(date=df["date"].dt.strftime("%Y-%m-%d")),
                columns=["date","temp_c","solar_mj"]
            )
