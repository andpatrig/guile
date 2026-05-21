"""
examples/05_data_tools.py — Table, date input, and file picker.

Shows the three new widgets working together in a simple
data viewer: pick a CSV, pick a date range, see a table.

Run:
    python examples/05_data_tools.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
file_path  = gui.state("")
start_date = gui.state("")
end_date   = gui.state("")

# Sample data — replaced by real CSV if user picks one
SAMPLE = [
    {"name": "Alice",   "department": "Engineering", "start": "2021-03-15", "salary": 92000},
    {"name": "Bob",     "department": "Design",      "start": "2020-07-01", "salary": 78000},
    {"name": "Carol",   "department": "Engineering", "start": "2022-01-10", "salary": 95000},
    {"name": "David",   "department": "Marketing",   "start": "2019-11-20", "salary": 71000},
    {"name": "Eve",     "department": "Design",      "start": "2023-05-03", "salary": 82000},
]

def load_data():
    """Load CSV if a file was picked, otherwise use sample data."""
    path = file_path.value
    if not path:
        return SAMPLE
    try:
        import csv
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        return [{"error": str(e)}]

def filter_data(data):
    """Filter by date range if both dates are set."""
    s, e = start_date.value, end_date.value
    if not s and not e:
        return data
    key = next((k for k in (data[0] if data else {}) if "date" in k.lower() or "start" in k.lower()), None)
    if not key:
        return data
    return [
        row for row in data
        if (not s or row.get(key, "") >= s)
        and (not e or row.get(key, "") <= e)
    ]


@gui.app("Data Viewer", width=700, height=600)
def ui():
    data = load_data()
    visible = filter_data(data)

    with gui.col(padding=20, gap=16, style="min-height:100vh"):

        # ── Header
        with gui.row(justify="space-between", align="center"):
            gui.title("Data Viewer")
            gui.badge(f"{len(visible)} rows", variant="primary")

        # ── Controls
        with gui.card(gap=12, padding=14):
            with gui.row(gap=12, align="flex-end", style="flex-wrap:wrap"):

                # File picker
                fp = gui.file_picker(
                    "Load CSV",
                    value=file_path,
                    file_types=("CSV Files (*.csv)", "All files (*.*)"),
                    key="csv-picker",
                )

                # Date range
                gui.date_input("From", value=start_date, key="date-from",
                               style="flex:1;min-width:140px")
                gui.date_input("To",   value=end_date,   key="date-to",
                               style="flex:1;min-width:140px")

                # Clear filters
                if start_date.value or end_date.value:
                    gui.button("Clear", variant="ghost", size="sm",
                               on_click=lambda: (start_date.set(""), end_date.set("")))

            # Show selected file path
            if file_path.value:
                gui.text(f"File: {file_path.value}", muted=True, size="sm")
            else:
                gui.text("Showing sample data — pick a CSV to load your own.",
                         muted=True, size="sm")

        # ── Table
        with gui.card(padding=0):
            if visible:
                gui.table(visible, key="main-table")
            else:
                with gui.col(align="center", style="padding:32px"):
                    gui.text("No rows match the date filter.", muted=True)
