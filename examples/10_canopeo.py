"""
examples/10_canopeo.py — Green canopy cover with the Canopeo algorithm.

Load an image, classify green canopy using Canopeo ratio thresholds,
blend the mask over the original with a slider, and download the mask.

Canopeo (Patrignani & Ochsner, 2015 — Agronomy Journal):
    A pixel is green canopy when ALL three conditions hold:
        R / G  <  threshold   (default 0.95)
        B / G  <  threshold   (default 0.95)
        2G - R - B  >  ex_threshold  (Excess Green, default 20)

Run:
    pip install numpy pillow matplotlib
    python examples/10_canopeo.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import guile as gui

# ── State ──────────────────────────────────────────────────────────────────
img_path   = gui.state("")          # path to the loaded image
img_array  = gui.state(None)        # original image as numpy (H, W, 3) uint8
mask_array = gui.state(None)        # binary mask as numpy (H, W) bool
cover_pct  = gui.state(0.0)         # green canopy cover %
blend      = gui.state(50.0)        # slider: 0 = image only, 100 = mask only

# Canopeo thresholds
rg_thresh  = gui.state(0.95)        # R/G threshold
bg_thresh  = gui.state(0.95)        # B/G threshold
exg_thresh = gui.state(20.0)        # Excess Green threshold


# ── Canopeo algorithm ──────────────────────────────────────────────────────

def canopeo(rgb: np.ndarray,
            rg: float, bg: float, exg: float) -> np.ndarray:
    """
    Classify green canopy pixels.

    Parameters
    ----------
    rgb : ndarray (H, W, 3) uint8
    rg  : R/G threshold   (pixel green if R/G < rg)
    bg  : B/G threshold   (pixel green if B/G < bg)
    exg : ExG threshold   (pixel green if 2G-R-B > exg)

    Returns
    -------
    mask : ndarray (H, W) bool
    """
    R = rgb[:, :, 0].astype(float)
    G = rgb[:, :, 1].astype(float)
    B = rgb[:, :, 2].astype(float)

    # Avoid division by zero
    G_safe = np.where(G == 0, 1e-6, G)

    ratio_rg = R / G_safe
    ratio_bg = B / G_safe
    excess_g = 2 * G - R - B

    return (ratio_rg < rg) & (ratio_bg < bg) & (excess_g > exg)


def blend_image(rgb: np.ndarray,
                mask: np.ndarray,
                alpha: float) -> np.ndarray:
    """
    Blend green mask (bright green overlay) over the original image.

    alpha = 0.0 → pure original image
    alpha = 1.0 → pure mask overlay
    """
    overlay = rgb.copy().astype(float)
    green_px = np.array([0, 200, 0], dtype=float)

    # Apply green colour where mask is True
    overlay[mask] = (1 - alpha) * rgb[mask].astype(float) + alpha * green_px
    # Non-mask pixels: darken slightly to make canopy pop
    overlay[~mask] = rgb[~mask].astype(float) * (1 - alpha * 0.25)

    return np.clip(overlay, 0, 255).astype(np.uint8)


# ── Callbacks ──────────────────────────────────────────────────────────────

def load_image(path: str):
    """Load image from path into state, then run Canopeo."""
    if not path:
        return
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        # Downscale very large images for display performance
        max_dim = 1200
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)),
                             Image.LANCZOS)
        arr = np.array(img)
        img_path.set(path)
        img_array.set(arr)
        run_canopeo()
    except Exception as e:
        gui.notify(f"Error loading image: {e}", variant="danger")


def run_canopeo():
    """Re-run Canopeo with current thresholds."""
    arr = img_array.value
    if arr is None:
        return
    m = canopeo(arr,
                rg_thresh.value,
                bg_thresh.value,
                exg_thresh.value)
    mask_array.set(m)
    pct = float(m.sum()) / m.size * 100
    cover_pct.set(round(pct, 2))


def save_mask(path: str):
    """Save the binary mask as a PNG file."""
    if not path or mask_array.value is None:
        return
    try:
        from PIL import Image
        m = mask_array.value
        # White = canopy, black = non-canopy
        png = Image.fromarray((m * 255).astype(np.uint8), mode="L")
        png.save(path)
        gui.notify(f"Mask saved to {os.path.basename(path)}")
    except Exception as e:
        gui.notify(f"Error saving mask: {e}", variant="danger")


# ── Figure ─────────────────────────────────────────────────────────────────

def make_figure() -> plt.Figure:
    arr  = img_array.value
    mask = mask_array.value
    if arr is None or mask is None:
        return None

    alpha  = blend.value / 100.0
    blended = blend_image(arr, mask, alpha)

    fig, ax = plt.subplots(figsize=(7, 5))
    fig.patch.set_alpha(0)
    ax.imshow(blended)
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


# ── App ────────────────────────────────────────────────────────────────────

@gui.app("Canopeo — Green Canopy Cover", width=860, height=700)
def ui():
    with gui.col(padding=20, gap=14, style="min-height:100vh"):

        # ── Header
        with gui.row(justify="space-between", align="center"):
            gui.title("Canopeo")
            gui.text("Green canopy cover classifier",
                     muted=True, size="sm")
            if cover_pct.value > 0 or mask_array.value is not None:
                gui.badge(
                    f"{cover_pct.value:.1f}% green cover",
                    variant="success",
                    style="font-size:15px;padding:6px 14px"
                )

        # ── Load image
        with gui.card(gap=10, padding=14):
            with gui.row(gap=12, align="center"):
                gui.file_picker(
                    "Load image",
                    file_types=(
                        "Image Files (*.jpg)",
                        "Image Files (*.jpeg)",
                        "Image Files (*.png)",
                        "Image Files (*.tif)",
                        "Image Files (*.bmp)",
                        "All files (*.*)",
                    ),
                    on_change=load_image,
                    key="img-load",
                )
                gui.file_picker(
                    "Save mask",
                    save=True,
                    file_types=("PNG Files (*.png)",),
                    disabled=mask_array.value is None,
                    on_change=save_mask,
                    key="mask-save",
                )
                if img_path.value:
                    gui.text(
                        os.path.basename(img_path.value),
                        muted=True, size="sm"
                    )

        if img_array.value is not None:

            # ── Blend slider
            with gui.card(gap=10, padding=14):
                gui.slider(
                    "Mask blend",
                    min=0, max=100, step=1,
                    value=blend, on_change=blend.set,
                    key="blend-sl",
                )
                with gui.row(gap=16):
                    gui.text("← Original image",
                             muted=True, size="sm")
                    gui.text("Mask overlay →",
                             muted=True, size="sm",
                             style="margin-left:auto")

            # ── Threshold controls
            with gui.card(gap=10, padding=14):
                gui.text("Canopeo thresholds", bold=True, size="sm",
                         muted=True,
                         style="text-transform:uppercase;letter-spacing:.06em")
                with gui.row(gap=12, align="flex-end"):
                    gui.number_input(
                        "R/G threshold", value=rg_thresh,
                        min=0.5, max=1.5, step=0.01,
                        on_change=lambda v: (rg_thresh.set(v), run_canopeo()),
                        key="rg"
                    )
                    gui.number_input(
                        "B/G threshold", value=bg_thresh,
                        min=0.5, max=1.5, step=0.01,
                        on_change=lambda v: (bg_thresh.set(v), run_canopeo()),
                        key="bg"
                    )
                    gui.number_input(
                        "Excess Green", value=exg_thresh,
                        min=0, max=100, step=1,
                        on_change=lambda v: (exg_thresh.set(v), run_canopeo()),
                        key="exg"
                    )

            # ── Blended image
            fig = make_figure()
            if fig is not None:
                with gui.card(padding=8):
                    gui.figure(fig, dpi=110)

        else:
            # Placeholder before image is loaded
            with gui.card(padding=40):
                with gui.col(align="center", gap=8):
                    gui.text("No image loaded", muted=True)
                    gui.text(
                        "Load a JPG, PNG, or TIFF to begin classification.",
                        muted=True, size="sm"
                    )
