"""
examples/03_settings.py — Widget showcase.

One card per input widget, each showing an immediate visual result
so the user can see exactly what each widget does.

Run:
    python examples/03_settings.py
"""

import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
theme_name  = gui.state("light")
font_size   = gui.state(15.0)
opacity     = gui.state(100.0)
agree       = gui.state(False)
color_mode  = gui.state("Indigo")
tags        = gui.state(["Python"])
note_text   = gui.state("")
priority    = gui.state(3.0)
start_date  = gui.state("")

# ── File I/O state ─────────────────────────────────────────────────────────
file_text   = gui.state("")
file_path   = gui.state("")
file_status = gui.state("")

# Two-column demo state
img_cmap    = gui.state("viridis")
img_freq    = gui.state(3.0)
img_noise   = gui.state(0.10)
map_regions = gui.state(["Northeast","Northwest","Southeast","Southwest"])

COLOR_MAP = {
    "Indigo": "#6366f1",
    "Rose":   "#f43f5e",
    "Teal":   "#14b8a6",
    "Amber":  "#f59e0b",
}

# ── Sample table data (wide + tall → forces both scroll axes) ──────────────
# Generated once at import time so the table is stable across re-renders.
random.seed(42)
_STATIONS = ["Manhattan", "Hays", "Colby", "Garden City", "Dodge City",
             "Liberal", "Hutchinson", "Salina", "Abilene", "Emporia"]
TABLE_DATA = [
    {
        "Station":        _STATIONS[i % len(_STATIONS)],
        "Date":           f"2024-06-{i + 1:02d}",
        "Temp Max (°C)":  round(20 + random.uniform(-4, 14), 1),
        "Temp Min (°C)":  round(10 + random.uniform(-4, 9),  1),
        "Wind (m/s)":     round(random.uniform(0, 12),        1),
        "Gust (m/s)":     round(random.uniform(5, 18),        1),
        "Rain (mm)":      round(random.uniform(0, 30),        1),
        "Humidity (%)":   round(random.uniform(30, 95),       1),
        "Pressure (hPa)": round(1000 + random.uniform(-20, 20), 1),
        "Solar (W/m²)":   int(random.uniform(80, 820)),
        "ET₀ (mm)":       round(random.uniform(0, 8),         2),
    }
    for i in range(30)
]

# ── KS Mesonet stations ───────────────────────────────────────────────────
STATIONS = [
    ("Manhattan",       "Northeast",  39.2086,  -96.5917),
    ("Konza Prairie",   "Northeast",  39.0884,  -96.5458),
    ("Ashland Bottoms", "Northeast",  39.1258,  -96.6365),
    ("Hiawatha",        "Northeast",  39.8424,  -95.4819),
    ("Colby",           "Northwest",  39.3925, -101.0686),
    ("Hays",            "Northwest",  38.8495,  -99.3446),
    ("Hill City",       "Northwest",  39.3741,  -99.8299),
    ("Cheyenne",        "Northwest",  39.6265, -101.8075),
    ("Cherokee",        "Southeast",  37.1990,  -94.9809),
    ("Haysville",       "Southeast",  37.5198,  -97.3121),
    ("Hutchinson 10SW", "Southeast",  37.9310,  -98.0200),
    ("Harper",          "Southeast",  37.0648,  -98.0847),
    ("Garden City",     "Southwest",  37.9973, -100.8151),
    ("Meade",           "Southwest",  37.1348, -100.3956),
    ("Lakin",           "Southwest",  37.8937, -101.2326),
    ("Greensburg",      "Southwest",  37.6028,  -99.2926),
]


# ── Pure functions ─────────────────────────────────────────────────────────
def make_surface_figure() -> plt.Figure:
    """2-D sine surface — updates when colormap, frequency or noise changes."""
    rng  = np.random.default_rng(0)
    x    = np.linspace(0, 2 * np.pi, 120)
    X, Y = np.meshgrid(x, x)
    f    = img_freq.value
    Z    = (np.sin(f * X) * np.cos(f * Y)
            + img_noise.value * rng.standard_normal((120, 120)))
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    fig.patch.set_alpha(0)
    im = ax.imshow(Z, cmap=img_cmap.value, origin="lower",
                   aspect="auto", interpolation="bilinear")
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(
        f"cmap={img_cmap.value}  ·  freq={f:.1f}  ·  "
        f"noise={img_noise.value:.2f}",
        fontsize=9, color="#666"
    )
    fig.tight_layout()
    return fig


def make_map_markers():
    active = set(map_regions.value)
    return [
        gui.Marker(
            (lat, lon),
            popup=f"<b>{name}</b><br>{region}",
            tooltip=name,
        )
        for name, region, lat, lon in STATIONS
        if region in active
    ]


# ── File I/O callbacks ─────────────────────────────────────────────────────
def open_file(path):
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as f:
            file_text.set(f.read())
        file_path.set(path)
        file_status.set(f"Opened  {os.path.basename(path)}")
    except Exception as e:
        file_status.set(f"Error: {e}")

def save_file(path):
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(file_text.value)
        file_status.set(f"Saved  {os.path.basename(path)}")
    except Exception as e:
        file_status.set(f"Save error: {e}")


# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Widget Showcase", width=560, height=800)
def ui():
    gui.theme(theme_name.value)

    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        gui.title("Widget Showcase")
        gui.text("Each card shows a widget and its live output.",
                 muted=True, size="sm")

        # ── select → changes the app theme live ────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.select()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.select(
                list(gui.THEMES.keys()), "Theme",
                value=theme_name, on_change=theme_name.set, key="theme"
            )
            gui.text(
                f"Active theme: {theme_name.value}",
                bold=True, style="color:var(--primary)"
            )

        # ── slider → live font size preview ────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.slider()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.slider("Font size", min=10, max=32, step=1,
                       value=font_size, on_change=font_size.set, key="font-sl")
            gui.text(
                f"The quick brown fox — {font_size.value:.0f}px",
                style=f"font-size:{font_size.value:.0f}px"
            )

        # ── number_input → opacity bar ──────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.number_input()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.number_input("Opacity", value=opacity,
                             min=0, max=100, step=5, unit="%",
                             on_change=opacity.set, key="opacity")
            gui.html(
                f'<div style="height:36px;border-radius:6px;'
                f'background:var(--primary);'
                f'opacity:{opacity.value/100:.2f};'
                f'transition:opacity .2s"></div>'
            )

        # ── checkbox → live toggle ──────────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.checkbox()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.checkbox("I agree to the terms", value=agree,
                         on_change=agree.set, key="agree")
            if agree.value:
                gui.badge("Access granted ✓", variant="success")
            else:
                gui.badge("Access denied", variant="danger")

        # ── select with color preview ───────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.select()  — colour picker", bold=True, size="sm",
                     muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.select(
                list(COLOR_MAP.keys()), "Accent colour",
                value=color_mode, on_change=color_mode.set, key="color"
            )
            hex_val = COLOR_MAP[color_mode.value]
            gui.html(
                f'<div style="display:flex;align-items:center;gap:10px">'
                f'<div style="width:32px;height:32px;border-radius:50%;'
                f'background:{hex_val}"></div>'
                f'<code style="font-size:13px">{hex_val}</code>'
                f'</div>'
            )

        # ── multiselect → tag cloud ─────────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.multiselect()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.multiselect(
                ["Python", "Pandas", "NumPy", "Matplotlib",
                 "SciPy", "Guile"],
                "Skills",
                value=tags, on_change=tags.set, rows=4, key="tags"
            )
            if tags.value:
                badges = "".join(
                    f'<span style="display:inline-block;background:var(--primary-light);'
                    f'color:var(--primary);border-radius:99px;padding:2px 10px;'
                    f'font-size:12px;margin:2px">{t}</span>'
                    for t in tags.value
                )
                gui.html(f'<div style="display:flex;flex-wrap:wrap;gap:4px">{badges}</div>')
            else:
                gui.text("No skills selected", muted=True, size="sm")

        # ── textarea → character count ──────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.textarea()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.textarea("Note", placeholder="Start typing…",
                         value=note_text, on_change=note_text.set, key="note")
            n = len(note_text.value)
            gui.text(f"{n} character{'s' if n != 1 else ''}",
                     muted=True, size="sm")

        # ── date_input → days from today ────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.date_input()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.date_input("Pick a date", value=start_date,
                           on_change=start_date.set, key="start")
            if start_date.value:
                from datetime import date
                try:
                    picked = date.fromisoformat(start_date.value)
                    delta  = (picked - date.today()).days
                    if delta == 0:
                        msg = "That's today!"
                    elif delta > 0:
                        msg = f"{delta} day{'s' if delta!=1 else ''} from today"
                    else:
                        msg = f"{abs(delta)} day{'s' if abs(delta)!=1 else ''} ago"
                    gui.text(msg, bold=True, style="color:var(--primary)")
                except ValueError:
                    pass

        # ── progress bar ────────────────────────────────────────────────────
        with gui.card(gap=10):
            gui.text("gui.progress()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.slider("Progress", min=0, max=100, step=1,
                       value=priority, on_change=priority.set, key="prog-sl")
            gui.progress(priority.value, max=100)
            gui.text(f"{priority.value:.0f}%", bold=True,
                     style="color:var(--primary)")

        # ── tabs ─────────────────────────────────────────────────────────────
        # gui.tabs() manages its own state — no module-level gui.state() needed.
        # Returns the active label as a plain string; use it in if/elif.
        with gui.card(gap=12):
            gui.text("gui.tabs()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")

            tab = gui.tabs(["Overview", "Stats", "Info"], key="showcase-tabs")

            if tab == "Overview":
                gui.text("Current widget values", bold=True)
                gui.text(f"Theme: {theme_name.value}  ·  "
                         f"Font: {font_size.value:.0f}px  ·  "
                         f"Opacity: {opacity.value:.0f}%", size="sm")
                gui.text(f"Agreed: {agree.value}  ·  "
                         f"Colour: {color_mode.value}  ·  "
                         f"Tags: {len(tags.value)}", size="sm")

            elif tab == "Stats":
                with gui.row(gap=12):
                    for label, val in [
                        ("Font",    f"{font_size.value:.0f}px"),
                        ("Opacity", f"{opacity.value:.0f}%"),
                        ("Tags",    str(len(tags.value))),
                        ("Note",    f"{len(note_text.value)} ch"),
                    ]:
                        with gui.card(gap=4, padding=12,
                                      style="flex:1;text-align:center;"
                                            "background:var(--surface-2)"):
                            gui.text(val, bold=True, size="lg",
                                     style="color:var(--primary)")
                            gui.text(label, muted=True, size="sm")

            elif tab == "Info":
                gui.text(
                    "gui.tabs() returns the active label as a plain string. "
                    "Use it directly in if/elif — no .value needed.",
                    size="sm",
                )
                gui.text(
                    'tab = gui.tabs(["A","B","C"], key="t")\nif tab == "A": ...',
                    size="sm", mono=True, style="color:var(--primary)",
                )

        # ── table with both scroll axes ────────────────────────────────────
        # The table wrap scrolls horizontally on its own; constraining the
        # card height with overflow-y gives vertical scroll too.
        with gui.card(gap=10):
            gui.text("gui.table()  — horizontal + vertical scroll",
                     bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.text(
                f"{len(TABLE_DATA)} rows × {len(TABLE_DATA[0])} columns  "
                f"— scroll right for more columns, down for more rows.",
                size="sm", muted=True,
            )

            with gui.card(padding=0,
                          style="overflow-y:auto;max-height:240px"):
                gui.table(TABLE_DATA)

        # ── file picker — read and save ────────────────────────────────────
        # on_change receives the chosen path; the actual file I/O below is
        # plain Python.
        with gui.card(gap=12):
            gui.text("gui.file_picker()  — read & save",
                     bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")

            with gui.row(gap=8, align="center"):
                gui.file_picker(
                    "Open file",
                    file_types=("Text files (*.txt)", "All files (*.*)"),
                    on_change=open_file,
                    key="fp-open",
                )
                gui.file_picker(
                    "Save as…",
                    save=True,
                    file_types=("Text files (*.txt)", "All files (*.*)"),
                    disabled=not file_text.value,
                    on_change=save_file,
                    key="fp-save",
                )

            if file_status.value:
                gui.text(file_status.value, muted=True, size="sm")

            # The textarea is always visible so the user can type freely
            # and save without opening a file first.
            gui.textarea(
                "Content",
                placeholder="Open a file above, or type here and save…",
                value=file_text,
                on_change=file_text.set,
                rows=6,
                key="fp-text",
            )

        # ── Two-column layout: controls + live image ────────────────────────
        with gui.card(gap=12, padding=16):
            gui.text("gui.figure()  — two-column layout", bold=True,
                     size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            with gui.row(gap=16, align="flex-start"):
                with gui.col(gap=10, style="width:190px;flex-shrink:0"):
                    gui.select(
                        ["viridis","plasma","inferno","magma",
                         "cividis","RdYlGn","coolwarm"],
                        "Colormap",
                        value=img_cmap, on_change=img_cmap.set,
                        key="cmap"
                    )
                    gui.slider("Frequency", min=1, max=8, step=0.5,
                               value=img_freq, on_change=img_freq.set,
                               key="freq")
                    gui.slider("Noise", min=0, max=0.5, step=0.05,
                               value=img_noise, on_change=img_noise.set,
                               key="noise")
                with gui.col(style="flex:1"):
                    gui.figure(make_surface_figure(), dpi=110)


