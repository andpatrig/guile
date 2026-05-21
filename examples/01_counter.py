"""
examples/01_counter.py — Counter in the new context-manager style.

Compare to v1:
    # v1 — nesting hell
    Column(Card(Title("Counter"), Row(Button("−"), Text(count), Button("+"))))

    # v2 — top to bottom, like reading a document
    with gui.card():
        gui.title("Counter")
        with gui.row(gap=12, align="center"):
            gui.button("−", ...)
            gui.text(count, size="2xl")
            gui.button("+", ...)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

count = gui.state(0)

@gui.app("Counter", width=380, height=300)
def ui():
    # The whole page is built top-to-bottom.
    # with gui.card() opens a raised container; everything indented is inside it.

    with gui.col(align="center", justify="center", style="height:100vh"):
        with gui.card(gap=14):
            with gui.row(justify="space-between", align="center"):
                gui.title("Counter")
                variant = "success" if count > 0 else "danger" if count < 0 else "neutral"
                label   = "positive" if count > 0 else "negative" if count < 0 else "zero"
                gui.badge(label, variant=variant)

            gui.divider()

            with gui.row(gap=16, align="center", justify="center"):
                gui.button("−", variant="secondary",
                         on_click=lambda: count.update(lambda x: x - 1))
                gui.text(count, size="2xl", bold=True,
                       style="min-width:64px;text-align:center")
                gui.button("+",
                         on_click=lambda: count.update(lambda x: x + 1))

            gui.button("Reset", variant="ghost", size="sm",
                     on_click=lambda: count.set(0),
                     style="align-self:flex-end")
