"""
examples/03_settings.py — A settings panel.

This example is deliberately about *style* not function —
it shows how layout props and style props are cleanly separated,
and how sliders/selects/checkboxes feel natural.

Notice:
    gap=, padding=, align=, justify=   → layout props (WHERE things go)
    color=, bold=, style="..."         → style props  (HOW they look)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

saved = gui.state(False)

@gui.app("Settings", width=500, height=640)
def ui():
    with gui.col(padding=24, gap=16, style="min-height:100vh"):

        # ── Page header
        with gui.row(justify="space-between", align="center"):
            gui.title("Settings")
            if saved.value:
                gui.badge("Saved ✓", variant="success")

        gui.divider()

        # ── Appearance section
        with gui.card(gap=14):
            gui.text("Appearance", bold=True, size="sm",
                   style="color:var(--text-2);text-transform:uppercase;letter-spacing:.06em")

            theme = gui.select(
                [("system","Follow system"), ("light","Light"), ("dark","Dark")],
                "Theme",
                key="theme",
            )
            font_size = gui.slider("Font size",
                                  min=12, max=24, step=1, value=15,
                                  key="font-size")
            gui.text(f"Preview text at {font_size.value:.0f}px",
                   style=f"font-size:{font_size.value:.0f}px;color:var(--text)")

        # ── Notifications section
        with gui.card(gap=14):
            gui.text("Notifications", bold=True, size="sm",
                   style="color:var(--text-2);text-transform:uppercase;letter-spacing:.06em")

            email_notif = gui.checkbox("Email notifications", value=True,
                                      key="email-notif")
            push_notif  = gui.checkbox("Push notifications",  value=False,
                                      key="push-notif")
            gui.checkbox("Weekly digest", value=True,
                        disabled=not email_notif.value,
                        key="weekly-digest")

            if not email_notif.value and not push_notif.value:
                gui.text("⚠ All notifications are off", muted=True, size="sm",
                       style="color:var(--warning)")

        # ── Account section
        with gui.card(gap=14):
            gui.text("Account", bold=True, size="sm",
                   style="color:var(--text-2);text-transform:uppercase;letter-spacing:.06em")

            username = gui.input("Username", placeholder="your-username", key="username")
            email    = gui.input("Email", placeholder="you@example.com",
                               type="email", key="email")

            # Live validation example
            if "@" not in email.value and email.value:
                gui.text("Enter a valid email address", size="sm",
                       style="color:var(--danger)")

        # ── Actions
        with gui.row(justify="flex-end", gap=8):
            gui.button("Cancel", variant="secondary",
                     on_click=lambda: saved.set(False))
            gui.button("Save changes",
                     on_click=lambda: saved.set(True))
