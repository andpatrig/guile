"""
examples/02_todo.py — To-do list.

Shows:
  - gui.input() returning its own State, so we can read name.value inline
  - Conditional rendering without any framework magic — just Python if
  - Dynamic lists with key= for stable patching
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import guile as gui

todos = gui.state([])    # list of {id, text, done}
_nid  = gui.state(0)

def add_todo(text):
    text = text.strip()
    if not text: return
    _nid.set(_nid.value + 1)
    todos.set(todos.value + [{"id": _nid.value, "text": text, "done": False}])

def toggle(tid):
    todos.set([{**t, "done": not t["done"]} if t["id"] == tid else t
               for t in todos.value])

def delete(tid):
    todos.set([t for t in todos.value if t["id"] != tid])

@gui.app("To-Do", width=460, height=560)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):
        with gui.card(gap=12):

            # ── Header
            with gui.row(justify="space-between", align="center"):
                gui.title("To-Do")
                done  = sum(1 for t in todos.value if t["done"])
                total = len(todos.value)
                gui.badge(f"{done}/{total}", variant="primary")

            if total > 0:
                gui.progress(done, max=total or 1)

            gui.divider()

            # ── Input row
            # gui.input() returns a State — we capture it as `new_text`
            # and read new_text.value below.
            with gui.row(gap=8, align="flex-end"):
                new_text = gui.input(placeholder="Add a task…",
                                   key="new-task",
                                   style="flex:1")
                gui.button("Add", on_click=lambda: (
                    add_todo(new_text.value),
                    new_text.set("")      # clear the field after adding
                ))

            # ── Filter
            filt = gui.select(
                [("all","All"), ("active","Active"), ("done","Done")],
                key="filter",
            )

            gui.divider()

            # ── List
            visible = [
                t for t in todos.value
                if filt.value == "all"
                or (filt.value == "done"   and     t["done"])
                or (filt.value == "active" and not t["done"])
            ]

            if not todos.value:
                with gui.col(align="center", gap=6, style="padding:12px 0"):
                    gui.html('<span style="font-size:2rem">📝</span>')
                    gui.text("Nothing here yet", muted=True)
            else:
                for t in visible:
                    tid = t["id"]
                    with gui.row(justify="space-between", align="center",
                               key=f"row-{tid}",
                               style=f"padding:4px 0;{'opacity:.5;' if t['done'] else ''}"):
                        # Checkbox returns its State but we use on_change here
                        gui.checkbox(t["text"], value=t["done"],
                                   on_change=lambda _, i=tid: toggle(i),
                                   key=f"cb-{tid}")
                        gui.button("✕", variant="ghost", size="sm",
                                 on_click=lambda i=tid: delete(i),
                                 key=f"del-{tid}")

            # ── Footer
            if any(t["done"] for t in todos.value):
                gui.button("Clear done", variant="ghost", size="sm",
                         on_click=lambda: todos.set(
                             [t for t in todos.value if not t["done"]]
                         ),
                         style="align-self:flex-start")
