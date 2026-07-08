# pip install guile

import guile as gui

# your existing code
def to_celsius(f):
    return round((f - 32) * 5 / 9, 1)

# state
fahrenheit = gui.state(32.0)

# callback
# This example does not require a callback — the function can be called
# directly from the slider. Use callbacks when you need to coordinate
# multiple functions from a single event.

# layout
@gui.app("Converter", width=360, height=300, center=True)
def ui():
    with gui.card(gap=16):
        gui.title("Temperature converter")
        gui.slider("°F", value=fahrenheit, on_change=fahrenheit.set, min=0, max=212)
        gui.text(f"{to_celsius(fahrenheit.value)} °C", size="2xl", bold=True)
