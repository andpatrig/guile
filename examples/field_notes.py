"""
examples/field_notes.py — Field notebook with automatic save on exit.

Highlights the gui.run() lifecycle (new in 0.7):

  1. Code ABOVE gui.run() runs at import — load last session from disk.
  2. gui.run() opens the window and blocks while the app is used.
  3. Code BELOW gui.run() runs when the window closes — save the session
     and print a summary. No "Save" button needed: closing the app IS
     saving. Your gui.state() values still hold whatever the user left
     in them.
"""

import sys, os, csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

NOTES_FILE = os.path.join(os.path.dirname(__file__), "field_notes.csv")


# ── 1. Before the window: load the previous session ───────────────────────
def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

notes = gui.state(load_notes())


def add_note(_=None):
    text = entry.value.strip()
    if not text:
        return
    notes.set(notes.value + [{"date": when.value or str(date.today()),
                              "plot": plot.value, "note": text}])
    entry.set("")


@gui.app("Field notes", width=560, height=560)
def ui():
    global entry, when, plot
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.card(gap=12):
            with gui.row(justify="space-between", align="center"):
                gui.title("Field notes")
                gui.badge(f"{len(notes.value)} notes", variant="primary")

            with gui.row(gap=8):
                when = gui.date_input("Date", value=str(date.today()),
                                      key="when")
                plot = gui.select(["North", "South", "East", "West"],
                                  "Plot", key="plot")
            with gui.row(gap=8, align="flex-end"):
                entry = gui.input("Observation",
                                  placeholder="e.g. maize at V6, slight N deficiency",
                                  key="entry", style="flex:1")
                gui.button("Add", on_click=add_note)

            if notes.value:
                gui.divider()
                with gui.scroll(max_height=280):
                    gui.table(notes.value)

            gui.text("Notes are saved automatically when you close the window "
                     "and loaded back the next time you open it.",
                     size="sm", muted=True)


# ── 2. Open the window; blocks until the user closes it ───────────────────
gui.run()


# ── 3. After the window closes: persist and summarise ─────────────────────
if notes.value:
    with open(NOTES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "plot", "note"])
        writer.writeheader()
        writer.writerows(notes.value)
    print(f"[field notes] {len(notes.value)} notes saved to {NOTES_FILE}")
else:
    print("[field notes] nothing to save")
