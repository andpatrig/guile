"""
examples/06_soils_lab.py — Soils laboratory sample tracker.

Log soil samples with a unique ID, county, and measured properties
(bulk density and pH). View all samples in a scrollable table,
then download as CSV.

Run:
    python examples/06_soils_lab.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guile as gui
import uuid

# ── State ──────────────────────────────────────────────────────────────────
samples       = gui.state([])   # list of dicts — one per sample
confirm_clear = gui.state(False)  # modal: confirm clear all

# Input fields
county       = gui.state("Riley")
sample_label = gui.state("")
bulk_density = gui.state(1.35)
ph           = gui.state(6.8)

COUNTIES = ["Riley", "Pottawatomie", "Wabaunsee", "Geary", "Morris"]


# ── Callbacks ──────────────────────────────────────────────────────────────
def add_sample():
    sample_id = str(uuid.uuid4())[:8].upper()
    row = {
        "ID":           sample_id,
        "Label":        sample_label.value.strip() or "—",
        "County":       county.value,
        "Bulk density": f"{bulk_density.value:.2f}",
        "pH":           f"{ph.value:.1f}",
    }
    samples.update(lambda s: s + [row])
    gui.notify(f"Sample {sample_id} added — {len(samples.value)} total.")


def request_clear():
    confirm_clear.set(True)

def do_clear():
    samples.set([])
    confirm_clear.set(False)
    gui.notify("All samples cleared.", variant="warning")


def download_csv(path):
    if not path or not samples.value:
        return
    import csv
    cols = ["ID", "Label", "County", "Bulk density", "pH"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(samples.value)
    gui.notify(f"Saved {len(samples.value)} samples to {os.path.basename(path)}")


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Soils Lab", width=700, height=620)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):

        with gui.row(justify="space-between", align="center"):
            gui.title("Soils Lab")
            gui.badge(f"{len(samples.value)} samples", variant="primary")

        # ── Entry form
        with gui.card(gap=12, padding=16):
            gui.text("New sample", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")

            with gui.row(gap=12, align="flex-end"):
                gui.select(COUNTIES, "County",
                           value=county, on_change=county.set, key="county")
                gui.input("Field label", placeholder="e.g. Plot-A",
                          value=sample_label, on_change=sample_label.set,
                          key="label", style="flex:1")

            with gui.row(gap=12, align="flex-end"):
                gui.number_input("Bulk density", value=bulk_density,
                                 min=0.5, max=2.5, step=0.01,
                                 unit="g/cm³",
                                 on_change=bulk_density.set, key="bd")
                gui.number_input("pH", value=ph,
                                 min=3.0, max=10.0, step=0.1,
                                 on_change=ph.set, key="ph")

            gui.button("Add sample", on_click=add_sample)

        # ── Samples table
        with gui.card(padding=0, style="overflow-y:auto;max-height:300px"):
            if samples.value:
                gui.table(samples.value,
                          columns=["ID","Label","County","Bulk density","pH"])
            else:
                with gui.col(align="center", style="padding:32px"):
                    gui.text("No samples yet.", muted=True)
                    gui.text("Fill in the form above and press Add sample.",
                             muted=True, size="sm")

        # ── Toolbar
        with gui.row(justify="flex-end", align="center", gap=8):
            gui.button("Clear all", variant="ghost",
                       disabled=len(samples.value) == 0,
                       on_click=request_clear)
            gui.file_picker("Download CSV", save=True,
                            file_types=("CSV Files (*.csv)",),
                            disabled=len(samples.value) == 0,
                            on_change=download_csv, key="dl")


        # ── Confirm clear modal
        with gui.modal("Clear all samples?",
                       visible=confirm_clear.value,
                       on_close=lambda: confirm_clear.set(False),
                       key="modal-clear"):
            gui.text("All samples will be permanently removed.")
            gui.spacer(h=4)
            with gui.row(gap=8, justify="flex-end"):
                gui.button("Cancel", variant="ghost",
                           on_click=lambda: confirm_clear.set(False))
                gui.button("Clear all", variant="danger",
                           on_click=do_clear)
