"""
examples/07_fao56_dual_kc.py — FAO-56 Dual Crop Coefficient Model

A soil water balance app built around a pandas DataFrame.
Load a CSV, set parameters, run the model, explore results.

CSV format (column names are flexible — positional order is used):
    column 1 — date       YYYY-MM-DD
    column 2 — precip     mm/day
    column 3 — ETo        mm/day

Run:
    pip install matplotlib numpy pandas
    python examples/07_fao56_dual_kc.py
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


# ══════════════════════════════════════════════════════════════════════════
# State
# ══════════════════════════════════════════════════════════════════════════

tab        = gui.state("Inputs")
status_msg = gui.state("Load a CSV file and press Run.")
results_df = gui.state(None)

file_path  = gui.state("")
plant_date = gui.state("")
date_range = gui.state("")   # filled when a CSV is loaded

# Growth stage lengths (days) — stored as floats via number_input
L_ini  = gui.state(30.0)
L_dev  = gui.state(40.0)
L_mid  = gui.state(50.0)
L_late = gui.state(30.0)

# Crop parameters
Kcb_ini = gui.state(0.15)
Kcb_mid = gui.state(1.10)
Kcb_end = gui.state(0.50)
h_max   = gui.state(1.50)

# Soil parameters
FC        = gui.state(0.36)
WP        = gui.state(0.18)
theta_ini = gui.state(0.30)
Zr_min    = gui.state(0.20)
Zr_max    = gui.state(2.00)
p_frac    = gui.state(0.50)
CN        = gui.state(75.0)


# ══════════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════════

def load_csv(path: str) -> pd.DataFrame:
    """Read weather CSV. Column names ignored; positional order used."""
    df = pd.read_csv(path, parse_dates=[0])
    df.columns = ["date", "precip_mm", "eto_mm"]
    return df.sort_values("date").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════
# FAO-56 model
# ══════════════════════════════════════════════════════════════════════════

def cn_runoff(precip: pd.Series, cn: float) -> pd.Series:
    """SCS curve number surface runoff (mm)."""
    S         = 25400.0 / cn - 254.0
    threshold = 0.2 * S
    ro        = (precip - threshold) ** 2 / (precip + 0.8 * S)
    return ro.where(precip > threshold, 0.0).clip(lower=0.0)


def build_time_series(n, Lini, Ldev, Lmid, Llate,
                      Ki, Km, Kend, hmax, zr_min, zr_max):
    """
    Piecewise-linear Kcb, crop height, canopy fraction, and root depth.

    Crop height (FAO-56 section 5.3):
        0 during initial stage, rises linearly to hmax during development,
        stays at hmax through mid and late season.

    Canopy cover fraction (FAO-56 Eq. 98):
        fc = ((Kcb - Kcb_min) / (Kcmax - Kcb_min)) ^ (1 + 0.5 * h)
        Kcmax = min(1.0 + 0.1 * h, 1.2),  Kcb_min = 0.15
    """
    idx      = np.arange(n)
    t1, t2   = Lini, Lini + Ldev
    t3, t4   = t2 + Lmid, t2 + Lmid + Llate

    Kcb = np.where(idx < t1, Ki,
          np.where(idx < t2, Ki + (Km - Ki) * (idx - t1) / max(Ldev, 1),
          np.where(idx < t3, Km,
          np.where(idx < t4, Km + (Kend - Km) * (idx - t3) / max(Llate, 1),
          Kend))))

    h = np.where(idx < t1, 0.0,
        np.where(idx < t2, hmax * (idx - t1) / max(Ldev, 1),
        hmax))

    Kcb_min = 0.15
    Kcmax   = np.minimum(1.0 + 0.1 * h, 1.2)
    ratio   = np.clip((Kcb - Kcb_min) / np.maximum(Kcmax - Kcb_min, 1e-6),
                      0.0, 1.0)
    fc      = ratio ** (1.0 + 0.5 * h)

    Zr = np.where(idx < t1, zr_min,
         np.where(idx < t2,
                  zr_min + (zr_max - zr_min) * (idx - t1) / max(Ldev, 1),
                  zr_max))

    return Kcb, h, fc, Zr


def run_fao56(df, plant_dt,
              Lini, Ldev, Lmid, Llate,
              Ki, Km, Kend, hmax,
              fc_soil, wp, th_ini,
              zr_min, zr_max, p, cn):
    """
    FAO-56 Dual Kc root-zone water balance.

    Simulation window: planting date → planting date + total season length.
    Returns a DataFrame with all drivers and computed outputs.
    """
    season_days = int(Lini + Ldev + Lmid + Llate)
    end_dt      = pd.Timestamp(plant_dt) + pd.Timedelta(days=season_days - 1)

    df = (df[(df["date"] >= pd.Timestamp(plant_dt)) &
             (df["date"] <= end_dt)]
          .reset_index(drop=True))

    if df.empty:
        raise ValueError("No weather data covers the specified growing season.")

    n               = len(df)
    Kcb, h, fc_veg, Zr = build_time_series(
        n, Lini, Ldev, Lmid, Llate, Ki, Km, Kend, hmax, zr_min, zr_max)

    df              = df.copy()
    df["runoff_mm"] = cn_runoff(df["precip_mm"], cn).values
    df["Kcb"]       = Kcb
    df["h_m"]       = h.round(3)
    df["fc_veg"]    = fc_veg.round(3)
    df["Zr_m"]      = Zr
    df["FC_mm"]     = fc_soil * Zr * 1000
    df["WP_mm"]     = wp      * Zr * 1000
    df["TAW_mm"]    = (fc_soil - wp) * Zr * 1000
    df["RAW_mm"]    = df["FC_mm"] - p * df["TAW_mm"]

    Ze  = 0.1
    TEW = (fc_soil - 0.5 * wp) * Ze * 1000
    REW = min(8.0, TEW)

    SWC_arr = np.zeros(n)
    Dr_arr  = np.zeros(n)
    ETc_arr = np.zeros(n)
    E_arr   = np.zeros(n)
    T_arr   = np.zeros(n)
    Ks_arr  = np.zeros(n)

    Dr_prev = (fc_soil - th_ini) * zr_min * 1000
    De_prev = 0.0

    for i, row in df.iterrows():
        TAW   = row["TAW_mm"]
        kcb   = row["Kcb"]
        fc_v  = max(row["fc_veg"], 0.01)
        few   = max(1.0 - fc_v, 0.01)
        eto   = row["eto_mm"]
        P_net = row["precip_mm"] - row["runoff_mm"]

        Kcmax = max(1.2, kcb + 0.05)
        Kr    = (1.0 if De_prev <= REW else
                 float(np.clip((TEW - De_prev) / max(TEW - REW, 1e-6),
                               0.0, 1.0)))
        Ke    = min(Kr * (Kcmax - kcb), few * Kcmax)

        Ks    = (1.0 if Dr_prev <= p * TAW else
                 float(np.clip((TAW - Dr_prev) / max(TAW - p * TAW, 1e-6),
                               0.0, 1.0)))

        E_soil = Ke  * eto
        T_soil = Ks  * kcb * eto
        ETc_d  = E_soil + T_soil

        Dr_new  = float(np.clip(Dr_prev - P_net + ETc_d,         0.0, TAW))
        De_new  = float(np.clip(De_prev - P_net + E_soil / few,  0.0, TEW))

        SWC_arr[i] = row["FC_mm"] - Dr_new
        Dr_arr[i]  = Dr_new
        ETc_arr[i] = ETc_d
        E_arr[i]   = E_soil
        T_arr[i]   = T_soil
        Ks_arr[i]  = Ks
        Dr_prev, De_prev = Dr_new, De_new

    df["ETc_mm"] = ETc_arr.round(2)
    df["E_mm"]   = E_arr.round(2)
    df["T_mm"]   = T_arr.round(2)
    df["Ks"]     = Ks_arr.round(3)
    df["SWC_mm"] = SWC_arr.round(2)
    df["Dr_mm"]  = Dr_arr.round(2)

    return df.drop(columns=["TAW_mm"])


def _on_file_loaded(path: str):
    """Set date_range as soon as a file is picked."""
    if not path:
        date_range.set("")
        return
    try:
        df = load_csv(path)
        d0 = df["date"].iloc[0].strftime("%Y-%m-%d")
        d1 = df["date"].iloc[-1].strftime("%Y-%m-%d")
        date_range.set(f"{d0}  →  {d1}  ({len(df)} days)")
    except Exception:
        date_range.set("Could not read dates from file")


def do_run():
    try:
        if not file_path.value:
            status_msg.set("No file loaded."); return
        if not plant_date.value:
            status_msg.set("No planting date selected."); return

        df  = load_csv(file_path.value)
        res = run_fao56(
            df, plant_date.value,
            int(L_ini.value), int(L_dev.value),
            int(L_mid.value), int(L_late.value),
            Kcb_ini.value, Kcb_mid.value, Kcb_end.value, h_max.value,
            FC.value, WP.value, theta_ini.value,
            Zr_min.value, Zr_max.value, p_frac.value, CN.value,
        )
        results_df.set(res)
        d0, d1 = res["date"].iloc[0], res["date"].iloc[-1]
        status_msg.set(
            f"{len(res)} days  ·  "
            f"{d0.strftime('%Y-%m-%d')} → {d1.strftime('%Y-%m-%d')}  ·  "
            f"ET {res['ETc_mm'].sum():.0f} mm  ·  "
            f"Stress days {int((res['Ks'] < 1).sum())}"
        )
        tab.set("Results")

    except Exception as e:
        status_msg.set(f"Error: {e}")
        results_df.set(None)


# ══════════════════════════════════════════════════════════════════════════
# Figure
# ══════════════════════════════════════════════════════════════════════════

def make_figure(df: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(
        3, 1, figsize=(9, 7.5),
        gridspec_kw={"height_ratios": [3, 1.4, 1], "hspace": 0.08},
        sharex=True,
    )
    ax1, ax2, ax3 = axes
    fig.patch.set_alpha(0)
    dates = df["date"]

    # Panel 1 — soil water content
    ax1.set_facecolor("#f9f9fb")
    ax1.plot(dates, df["SWC_mm"], color="#3b82f6", lw=2.0, zorder=3,
             label="Soil water content")
    ax1.plot(dates, df["FC_mm"],  color="#16a34a", lw=1.2, ls="--",
             label="Field capacity")
    ax1.plot(dates, df["WP_mm"],  color="#dc2626", lw=1.2, ls="--",
             label="Wilting point")
    ax1.plot(dates, df["RAW_mm"], color="#f59e0b", lw=1.2, ls=":",
             label="RAW threshold")
    ax1.fill_between(dates, df["SWC_mm"], df["RAW_mm"],
                     where=df["SWC_mm"] < df["RAW_mm"],
                     color="#fca5a5", alpha=0.40, label="Water stress")
    ax1.set_ylabel("Root-zone water (mm)", fontsize=10)
    ax1.legend(fontsize=8, loc="upper right", framealpha=0.8)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", ls="--", alpha=0.3)

    # Panel 2 — crop height and canopy cover (dual y-axis)
    ax2.set_facecolor("#f9f9fb")
    ax2b = ax2.twinx()
    ax2.plot(dates, df["h_m"],         color="#8b5cf6", lw=1.8,
             label="Crop height (m)")
    ax2b.plot(dates, df["fc_veg"] * 100, color="#10b981", lw=1.8,
              ls="--", label="Canopy cover (%)")
    ax2.set_ylabel("h (m)",  fontsize=10, color="#8b5cf6")
    ax2b.set_ylabel("fc (%)", fontsize=10, color="#10b981")
    ax2.set_ylim(bottom=0);  ax2b.set_ylim(bottom=0)
    ax2.spines[["top"]].set_visible(False)
    ax2b.spines[["top"]].set_visible(False)
    lines  = ax2.get_lines() + ax2b.get_lines()
    ax2.legend(lines, [l.get_label() for l in lines],
               fontsize=8, loc="upper left", framealpha=0.8)

    # Panel 3 — precipitation (inverted)
    ax3.set_facecolor("#f9f9fb")
    ax3.bar(dates, df["precip_mm"], color="#60a5fa", width=1.0, alpha=0.80)
    ax3.set_ylabel("P (mm/day)", fontsize=10)
    ax3.invert_yaxis()
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax3.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30, ha="right")

    return fig


# ══════════════════════════════════════════════════════════════════════════
# UI helpers
# ══════════════════════════════════════════════════════════════════════════

def section_label(text):
    gui.text(text, bold=True, size="sm", muted=True,
             style="letter-spacing:.07em;text-transform:uppercase")


def tab_btn(label, target):
    gui.button(
        label,
        variant="primary" if tab.value == target else "secondary",
        on_click=lambda t=target: tab.set(t),
        style="border-radius:6px 6px 0 0",
    )


# ══════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════

@gui.app("FAO-56 Dual Kc", width=900, height=760)
def ui():
    with gui.col(padding=20, gap=12, style="min-height:100vh"):

        gui.title("FAO-56 Dual Crop Coefficient", size="lg")
        gui.text("Allen et al. (1998)  ·  root-zone water balance",
                 muted=True, size="sm")
        gui.spacer(h=4)

        with gui.row(gap=4, style="border-bottom:2px solid var(--border)"):
            tab_btn("⚙  Inputs",  "Inputs")
            tab_btn("📈 Results", "Results")
            tab_btn("📋 Table",   "Table")

        gui.spacer(h=12)

        # ══════════════════════════════════════════════════════════════════
        # TAB 1 — Inputs
        # ══════════════════════════════════════════════════════════════════
        if tab.value == "Inputs":

            # File and date — full width
            with gui.card(gap=10, padding=16):
                section_label("Data")
                with gui.row(gap=16, align="flex-end"):
                    with gui.col(style="flex:2"):
                        gui.file_picker(
                            "Load CSV  (date, precip_mm, eto_mm)",
                            value=file_path, key="csv-file",
                            file_types=("CSV Files (*.csv)",
                                        "All files (*.*)"),
                            on_change=_on_file_loaded,
                        )
                        if date_range.value:
                            gui.text(date_range, size="sm",
                                     muted=True)
                    with gui.col(style="flex:1"):
                        gui.date_input("Planting date",
                                       value=plant_date,
                                       key="plant-date",
                                       on_change=plant_date.set)

            # Two-column parameter section
            with gui.row(gap=12, align="flex-start"):

                # Left: growth stages + crop coefficients
                with gui.col(style="flex:1", gap=12):
                    with gui.card(gap=10, padding=16):
                        section_label("Growth stage lengths")
                        gui.number_input("Initial  (L_ini)",
                            step=1, unit="days",
                            value=L_ini,  key="l-ini",
                            on_change=L_ini.set)
                        gui.number_input("Development  (L_dev)",
                            step=1, unit="days",
                            value=L_dev,  key="l-dev",
                            on_change=L_dev.set)
                        gui.number_input("Mid-season  (L_mid)",
                            step=1, unit="days",
                            value=L_mid,  key="l-mid",
                            on_change=L_mid.set)
                        gui.number_input("Late season  (L_late)",
                            step=1, unit="days",
                            value=L_late, key="l-late",
                            on_change=L_late.set)

                    with gui.card(gap=10, padding=16):
                        section_label("Crop coefficients & height")
                        gui.number_input("Kcb  initial",
                            step=0.01,
                            value=Kcb_ini, key="kcb-ini",
                            on_change=Kcb_ini.set)
                        gui.number_input("Kcb  mid-season",
                            step=0.01,
                            value=Kcb_mid, key="kcb-mid",
                            on_change=Kcb_mid.set)
                        gui.number_input("Kcb  end-season",
                            step=0.01,
                            value=Kcb_end, key="kcb-end",
                            on_change=Kcb_end.set)
                        gui.number_input("Max crop height  (h_max)",
                            step=0.05, unit="m",
                            value=h_max, key="hmax",
                            on_change=h_max.set)

                # Right: soil parameters
                with gui.col(style="flex:1", gap=12):
                    with gui.card(gap=10, padding=16):
                        section_label("Soil water parameters")
                        gui.number_input("Field capacity  (FC)",
                            step=0.01, unit="m³/m³",
                            value=FC, key="fc", on_change=FC.set)
                        gui.number_input("Wilting point  (WP)",
                            step=0.01, unit="m³/m³",
                            value=WP, key="wp", on_change=WP.set)
                        gui.number_input("Initial moisture  (θ_ini)",
                            step=0.01, unit="m³/m³",
                            value=theta_ini, key="th",
                            on_change=theta_ini.set)
                        gui.number_input("Min root depth  (Zr_min)",
                            step=0.05, unit="m",
                            value=Zr_min, key="zrmin",
                            on_change=Zr_min.set)
                        gui.number_input("Max root depth  (Zr_max)",
                            step=0.10, unit="m",
                            value=Zr_max, key="zrmax",
                            on_change=Zr_max.set)
                        gui.number_input("Depletion fraction  (p)",
                            step=0.05,
                            value=p_frac, key="pfrac",
                            on_change=p_frac.set)
                        gui.number_input("Runoff curve number  (CN)",
                            step=1, min=1, max=100,
                            value=CN, key="cn", on_change=CN.set)

            gui.spacer(h=4)
            with gui.row(justify="space-between", align="center"):
                gui.text(status_msg, size="sm", muted=True)
                gui.button("▶  Run model", on_click=do_run, size="lg")

        # ══════════════════════════════════════════════════════════════════
        # TAB 2 — Results figure
        # ══════════════════════════════════════════════════════════════════
        elif tab.value == "Results":
            df = results_df.value
            if df is None:
                with gui.col(align="center", style="padding:60px 0"):
                    gui.text("No results yet.", muted=True)
                    gui.text("Go to Inputs, load a CSV, and press Run.",
                             muted=True, size="sm")
            else:
                gui.text(status_msg, size="sm", muted=True)
                gui.spacer(h=4)
                with gui.card(padding=12):
                    gui.figure(make_figure(df), dpi=110)

        # ══════════════════════════════════════════════════════════════════
        # TAB 3 — Daily output table
        # ══════════════════════════════════════════════════════════════════
        else:
            df = results_df.value
            if df is None:
                with gui.col(align="center", style="padding:60px 0"):
                    gui.text("No results yet.", muted=True)
                    gui.text("Go to Inputs, load a CSV, and press Run.",
                             muted=True, size="sm")
            else:
                gui.text(status_msg, size="sm", muted=True)
                gui.spacer(h=4)

                # Summary row
                with gui.row(gap=10):
                    for label, val in [
                        ("Total precip",
                         f"{df['precip_mm'].sum():.0f} mm"),
                        ("Total ET",
                         f"{df['ETc_mm'].sum():.0f} mm"),
                        ("Transpiration",
                         f"{df['T_mm'].sum():.0f} mm"),
                        ("Stress days",
                         f"{int((df['Ks'] < 1).sum())}"),
                        ("Peak canopy",
                         f"{df['fc_veg'].max():.0%}"),
                    ]:
                        with gui.card(padding=12, style="flex:1"):
                            gui.text(label, muted=True, size="sm")
                            gui.title(val, size="lg")

                gui.spacer(h=4)

                cols = ["date", "precip_mm", "eto_mm", "runoff_mm",
                        "Kcb", "h_m", "fc_veg",
                        "ETc_mm", "E_mm", "T_mm", "Ks",
                        "SWC_mm", "Dr_mm", "FC_mm", "WP_mm"]

                with gui.card(padding=0,
                              style="overflow-y:auto;max-height:420px"):
                    records = (
                        df[cols]
                        .assign(date=df["date"].dt.strftime("%Y-%m-%d"))
                        .round(3)
                        .to_dict("records")
                    )
                    gui.table(records, columns=cols)
