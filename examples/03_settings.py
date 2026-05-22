"""
examples/03_settings.py — Widget showcase.

One card per input widget, each showing an immediate visual result
so the user can see exactly what each widget does.

Run:
    python examples/03_settings.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

COLOR_MAP = {
    "Indigo": "#6366f1",
    "Rose":   "#f43f5e",
    "Teal":   "#14b8a6",
    "Amber":  "#f59e0b",
}

# ── App ────────────────────────────────────────────────────────────────────
@gui.app("Widget Showcase", width=560, height=900)
def ui():
    gui.theme(theme_name.value)

    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        gui.title("Widget Showcase")
        gui.text("Each card shows a widget and its live output.",
                 muted=True, size="sm")

        # ── select → changes the app theme live
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

        # ── slider → live font size preview
        with gui.card(gap=10):
            gui.text("gui.slider()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.slider("Font size", min=10, max=32, step=1,
                       value=font_size, on_change=font_size.set, key="font-sl")
            gui.text(
                f"The quick brown fox — {font_size.value:.0f}px",
                style=f"font-size:{font_size.value:.0f}px"
            )

        # ── number_input → opacity bar
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

        # ── checkbox → live toggle
        with gui.card(gap=10):
            gui.text("gui.checkbox()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.checkbox("I agree to the terms", value=agree,
                         on_change=agree.set, key="agree")
            if agree.value:
                gui.badge("Access granted ✓", variant="success")
            else:
                gui.badge("Access denied", variant="danger")

        # ── select with color preview
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

        # ── multiselect → tag cloud
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

        # ── textarea → character count
        with gui.card(gap=10):
            gui.text("gui.textarea()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.textarea("Note", placeholder="Start typing…",
                         value=note_text, on_change=note_text.set, key="note")
            n = len(note_text.value)
            gui.text(f"{n} character{'s' if n != 1 else ''}",
                     muted=True, size="sm")

        # ── date_input → days from today
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

        # ── progress bar
        with gui.card(gap=10):
            gui.text("gui.progress()", bold=True, size="sm", muted=True,
                     style="text-transform:uppercase;letter-spacing:.06em")
            gui.slider("Progress", min=0, max=100, step=1,
                       value=priority, on_change=priority.set, key="prog-sl")
            gui.progress(priority.value, max=100)
            gui.text(f"{priority.value:.0f}%", bold=True,
                     style="color:var(--primary)")
