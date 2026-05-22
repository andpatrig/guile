"""
examples/08_dynamic_table.py — Build a table row by row, then download it.

Demonstrates the core pattern for dynamic data in guile:
  - State holds the table data (starts empty)
  - Callbacks add/clear rows — never mutate state inside ui()
  - ui() only reads state and renders widgets

Run:
    python examples/08_dynamic_table.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
# The table data lives here. Start with an empty list.
# Every render reads rows.value and passes it to gui.table().
rows   = gui.state([])
status = gui.state("")


# ── Callbacks ──────────────────────────────────────────────────────────────
# All data mutation happens here — never inside ui().

def add_row(name, crop, value):
    """Append one row to the table."""
    if not name.strip():
        status.set("Name is required.")
        return
    rows.update(lambda r: r + [{"Name": name, "Crop": crop, "Value (mm)": value}])
    status.set(f"{len(rows.value)} rows in table.")

def clear_table():
    rows.set([])
    status.set("Table cleared.")

def download_csv(path):
    """Write the table to a CSV file at the path chosen by the file dialog."""
    if not path or not rows.value:
        return
    import csv
    cols = ["Name", "Crop", "Value (mm)"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows.value)
    status.set(f"Saved to {os.path.basename(path)}")


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Dynamic table", width=640, height=560)
def ui():
    with gui.col(padding=20, gap=16, style="min-height:100vh"):

        gui.title("Field measurements")
        gui.text("Add rows one at a time, then download as CSV.",
                 muted=True, size="sm")

        # ── Input form
        with gui.card(gap=12, padding=16):
            with gui.row(gap=12, align="flex-end"):
                name  = gui.input("Site name", placeholder="e.g. KSU-01",
                                  key="inp-name", style="flex:2")
                crop  = gui.select(
                    ["Maize", "Wheat", "Soybean", "Sorghum"],
                    "Crop", key="sel-crop", style="flex:1"
                )
                val   = gui.number_input("ET value", value=0.0,
                                         step=0.1, unit="mm",
                                         key="inp-val",
                                         style="flex:1")

            gui.button(
                "Add row",
                on_click=lambda: add_row(name.value, crop.value, val.value),
                style="align-self:flex-start",
            )

        # ── Table (empty list → shows "No data" placeholder)
        with gui.card(padding=0, style="overflow-y:auto;max-height:280px"):
            gui.table(rows.value, columns=["Name", "Crop", "Value (mm)"])

        # ── Toolbar
        with gui.row(justify="space-between", align="center"):
            gui.text(status, size="sm", muted=True)
            with gui.row(gap=8):
                gui.button(
                    "Clear",
                    variant="ghost",
                    disabled=len(rows.value) == 0,
                    on_click=clear_table,
                )
                gui.file_picker(
                    "Download CSV",
                    save=True,
                    file_types=("CSV Files (*.csv)",),
                    on_change=download_csv,
                    key="save-csv",
                )
