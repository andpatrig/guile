"""
examples/07_ks_mesonet.py — Kansas Mesonet data downloader.

Sidebar with controls, scrollable table of results, download button.
Queries the live KS Mesonet REST API.

Run:
    pip install pandas
    python examples/07_ks_mesonet.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui
import pandas as pd

# ── Station list ──────────────────────────────────────────────────────────
STATIONS = [
    "Manhattan", "Ashland Bottoms", "Konza Prairie",
    "Colby", "Hays", "Hill City",
    "Garden City", "Dodge City", "Liberal",
    "Wichita", "Hutchinson 10SW", "Haysville",
    "Topeka", "Lawrence", "Emporia",
    "Salina", "Great Bend", "Pratt",
]

VARIABLES = [
    ("TEMP2MAVG", "Air temp (°C)"),
    ("TEMP2MMAX", "Max temp (°C)"),
    ("TEMP2MMIN", "Min temp (°C)"),
    ("SRAVG",     "Solar radiation"),
    ("PRECIP",    "Precipitation"),
    ("RELHUM",    "Relative humidity"),
    ("WSPD10AVG", "Wind speed"),
]

# ── State ──────────────────────────────────────────────────────────────────
station    = gui.state("Manhattan")
start_date = gui.state("2026-01-01")
end_date   = gui.state("2026-05-01")
variables  = gui.state(["TEMP2MAVG"])
interval   = gui.state("day")
data       = gui.state(None)
status     = gui.state("Select options and press Request.")


# ── Callbacks ──────────────────────────────────────────────────────────────
def fetch():
    if not variables.value:
        status.set("Select at least one variable.")
        return
    try:
        fmt   = "%Y%m%d%H%M%S"
        start = pd.to_datetime(start_date.value).strftime(fmt)
        end   = pd.to_datetime(end_date.value).strftime(fmt)
        vars_ = ",".join(variables.value)
        url   = (
            f"http://mesonet.k-state.edu/rest/stationdata/"
            f"?stn={station.value}&int={interval.value}"
            f"&t_start={start}&t_end={end}&vars={vars_}"
        ).replace(" ", "%20")
        df = pd.read_csv(url, na_values="M")
        data.set(df)
        status.set(
            f"{len(df):,} rows  ·  {len(df.columns)} columns  ·  "
            f"{station.value}  ·  "
            f"{start_date.value} → {end_date.value}"
        )
    except Exception as e:
        status.set(f"Error: {e}")
        data.set(None)


def save_csv(path):
    if path and data.value is not None:
        data.value.to_csv(path, index=False)
        status.set(f"Saved to {os.path.basename(path)}")


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("KS Mesonet", width=920, height=620)
def ui():
    with gui.row(gap=0, style="min-height:100vh"):

        # ── Sidebar ────────────────────────────────────────────────────────
        with gui.col(
            padding=16, gap=12,
            style="width:240px;flex-shrink:0;"
                  "border-right:1px solid var(--border);"
                  "background:var(--surface);"
                  "overflow-y:auto"
        ):
            gui.title("KS Mesonet", size="lg")
            gui.text("Kansas State University", muted=True, size="sm")
            gui.divider()

            gui.select(STATIONS, "Station",
                       value=station, on_change=station.set, key="stn")
            gui.date_input("Start date", value=start_date,
                           on_change=start_date.set, key="start")
            gui.date_input("End date", value=end_date,
                           on_change=end_date.set, key="end")
            gui.multiselect(
                VARIABLES, "Variables",
                value=variables, on_change=variables.set,
                rows=5, key="vars"
            )
            gui.select(
                [("day","Daily"), ("hour","Hourly")],
                "Interval",
                value=interval, on_change=interval.set, key="intv"
            )

            gui.spacer(h=4)
            gui.button("▶  Request", on_click=fetch,
                       style="width:100%")
            gui.file_picker(
                "Save CSV", save=True,
                file_types=("CSV Files (*.csv)",),
                disabled=data.value is None,
                on_change=save_csv, key="save"
            )

            gui.spacer(h=8)
            gui.text(status, size="sm", muted=True)

        # ── Main content ───────────────────────────────────────────────────
        with gui.col(padding=16, gap=12, fill=True):
            if data.value is None:
                with gui.col(
                    align="center", justify="center",
                    style="height:100%;min-height:400px"
                ):
                    gui.text("No data yet.", muted=True)
                    gui.text("Select options in the sidebar and press Request.",
                             muted=True, size="sm")
            else:
                with gui.row(justify="space-between", align="center"):
                    gui.badge(f"{len(data.value):,} rows", variant="primary")
                    gui.badge(
                        f"{len(data.value.columns)} columns",
                        variant="neutral"
                    )
                with gui.scroll(max_height=500):
                    gui.table(data.value)
