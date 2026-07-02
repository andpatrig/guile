import guile as gui

# ── 1. Your existing code ───────────
def to_celsius(f):
    return round((f - 32) * 5/9, 1)
    
def water_phase(c):
    if c <= 0: return "Solid"
    if c < 100: return "Liquid"
    return "Gas"
    

# ── 2. State ───────────────────────
fahrenheit = gui.state(32)
celsius = gui.state(None)
phase = gui.state("")


# ── 3. Callback ────────────────────
def analyze():
    c = to_celsius(fahrenheit.value)
    celsius.set(c)
    phase.set(water_phase(c))


# ── 4. Layout ──────────────────────
@gui.app("Water", height= 300, width=360, center=True)
def ui():
    gui.slider(label="°F", min=20, max=230, value=fahrenheit, on_change=fahrenheit.set)
    gui.button("Convert", on_click=analyze)
    if celsius.value is not None:
        gui.text(f"{celsius.value} °C")
        gui.text(phase.value)