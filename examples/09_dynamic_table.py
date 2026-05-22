"""
examples/08_dynamic_table.py — Load a DataFrame, display it, download it.

The pattern:
  - df = gui.state(None)        — None means no data yet
  - Load button sets df.set()   — triggers a re-render showing the table
  - ui() reads df.value         — shows placeholder or table, nothing else

Run:
    pip install pandas
    python examples/08_dynamic_table.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
df     = gui.state(None)   # None = no data loaded; DataFrame = ready to show
status = gui.state("")


# ── Callbacks ──────────────────────────────────────────────────────────────

def load_file(path):
    """Read a CSV or Excel file into a DataFrame and store it in state."""
    if not path:
        return
    try:
        import pandas as pd
        if path.endswith(".xlsx") or path.endswith(".xls"):
            data = pd.read_excel(path)
        else:
            data = pd.read_csv(path)
        df.set(data)
        status.set(
            f"{len(data):,} rows × {len(data.columns)} columns  ·  "
            f"{', '.join(data.columns[:4].tolist())}"
            + (" …" if len(data.columns) > 4 else "")
        )
    except Exception as e:
        status.set(f"Error: {e}")
        df.set(None)


def save_file(path):
    """Write the current DataFrame to a CSV file."""
    if not path or df.value is None:
        return
    try:
        df.value.to_csv(path, index=False)
        status.set(f"Saved to {os.path.basename(path)}")
    except Exception as e:
        status.set(f"Save error: {e}")


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("DataFrame viewer", width=780, height=600)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):

        # Header
        with gui.row(justify="space-between", align="center"):
            gui.title("DataFrame viewer")
            if df.value is not None:
                gui.badge(
                    f"{len(df.value):,} rows",
                    variant="primary",
                )

        # File controls
        with gui.card(gap=10, padding=14):
            with gui.row(gap=10, align="center"):
                gui.file_picker(
                    "Load file",
                    file_types=(
                        "CSV Files (*.csv)",
                        "Excel Files (*.xlsx *.xls)",
                        "All files (*.*)",
                    ),
                    on_change=load_file,
                    key="load",
                )
                gui.file_picker(
                    "Save CSV",
                    save=True,
                    file_types=("CSV Files (*.csv)",),
                    on_change=save_file,
                    disabled=df.value is None,
                    key="save",
                )
                if status.value:
                    gui.text(status, size="sm", muted=True)

        # Table — placeholder when no data, full table when loaded
        if df.value is None:
            with gui.card(padding=32):
                with gui.col(align="center", gap=6):
                    gui.text("No data loaded", muted=True)
                    gui.text("Pick a CSV or Excel file above.",
                             muted=True, size="sm")
        else:
            with gui.card(padding=0,
                          style="overflow-y:auto;max-height:420px"):
                gui.table(df.value)
