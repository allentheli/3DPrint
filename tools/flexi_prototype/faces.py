"""Kid-style test faces drawn on each head's guide outline. 20 px per mm.
Cat: seen from the front, canvas right = the head's +Y. Fish: seen from the side, canvas right = +X."""
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
import shapes
PPM = 20
BLACK, PINK, BROWN, WHITE, BLUE, YELLOW = (20, 20, 20), (240, 110, 150), (150, 80, 30), (255, 255, 255), (40, 90, 210), (245, 200, 30)
def canvas(axes_u, axes_v):
    W = int(round((axes_u[-1] - axes_u[0]) * PPM)) + 1; H = int(round((axes_v[-1] - axes_v[0]) * PPM)) + 1
    return Image.new("RGB", (W, H), "white"), axes_u[0], axes_v[-1]
def guide(sil, size):
    """The outline the card would print, as a light line (for looking only)."""
    m = cv2.resize(sil.T[::-1].astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    return edge
out = Path(sys.argv[1])
# Cat face (front): canvas covers Y (left->right) and Z (bottom->top).
axes, D, _ = shapes.cat_head()
inside = D < 0
im, u0, vtop = canvas(axes[1], axes[2]); d = ImageDraw.Draw(im)
P = lambda y, z: ((y - u0) * PPM, (vtop - z) * PPM)
for s in (1, -1):
    d.ellipse([P(s * 3.6 - 1.6, 13.6), P(s * 3.6 + 1.6, 10.6)], fill=BLACK)                # eyes
    d.ellipse([P(s * 3.6 + 0.2, 13.1), P(s * 3.6 + 0.9, 12.4)], fill=WHITE)                # shine
    d.ellipse([P(s * 6.6 - 1.5, 8.6), P(s * 6.6 + 1.5, 6.0)], fill=PINK)                   # cheeks
    d.polygon([P(s * 6.6, 19.6), P(s * 7.7, 22.8), P(s * 5.6, 20.1)], fill=PINK)           # inner ears, where the ears show above the head
d.polygon([P(-1.1, 9.4), P(1.1, 9.4), P(0, 8.2)], fill=PINK, outline=BLACK, width=4)       # nose
d.line([P(0, 8.2), P(0, 7.2)], fill=BLACK, width=6)
d.arc([P(-1.8, 7.9), P(0, 6.3)], 20, 160, fill=BLACK, width=6)
d.arc([P(0, 7.9), P(1.8, 6.3)], 20, 160, fill=BLACK, width=6)
for k in (-1, 0, 1):
    d.line([P(k * 1.6, 18.5), P(k * 1.4, 16.4)], fill=BROWN, width=12)                     # forehead stripes
sil = inside.any(axis=0)
g = guide(sil, im.size)
im.save(out / "cat-face.png")
look = np.array(im); look[g & (look.sum(2) > 700)] = (150, 180, 230); Image.fromarray(look).save(out / "cat-face-on-guide.png")
# Fish (side): canvas covers X (tail-left -> snout-right) and Z.
axes, D, _ = shapes.fish_head()
inside = D < 0
im, u0, vtop = canvas(axes[0], axes[2]); d = ImageDraw.Draw(im)
P = lambda x, z: ((x - u0) * PPM, (vtop - z) * PPM)
d.ellipse([P(8.0, 12.6), P(12.2, 8.4)], fill=WHITE, outline=BLACK, width=6)                # big eye
d.ellipse([P(9.6, 11.7), P(11.9, 9.1)], fill=BLACK)
d.ellipse([P(10.6, 11.4), P(11.3, 10.7)], fill=WHITE)
d.arc([P(13.0, 7.2), P(17.5, 3.8)], 200, 320, fill=BLACK, width=7)                          # smile
d.arc([P(-1.0, 15.0), P(6.0, 3.0)], 300, 60, fill=BLACK, width=7)                           # gill
for x, z in ((-4, 11), (-2, 6.5), (1.5, 13.5), (0.5, 9.5)):
    d.ellipse([P(x - 1.1, z + 1.1), P(x + 1.1, z - 1.1)], fill=YELLOW)                      # spots
d.ellipse([P(12.5, 7.5), P(15.0, 5.6)], fill=PINK)                                           # cheek
sil = inside.any(axis=1)
g = guide(sil, im.size)
im.save(out / "fish-face.png")
look = np.array(im); look[g & (look.sum(2) > 700)] = (150, 180, 230); Image.fromarray(look).save(out / "fish-face-on-guide.png")
print("ok")
