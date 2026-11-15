"""An IgG antibody, drawn as exact shapes (mm, y up) and saved as a clean color drawing (Allen, 2026-11-15:
"my wife is a scientist and she wants a set of antibody earrings, make it nice").

Heavy chains blue (the Fc stem and the inner half of each arm), light chains pink (the outer half),
variable domains gold (the antigen-binding tips), a hinge with a disulfide bridge; 1 mm white gaps.

    python tools/antibody_earrings.py photos/antibody/antibody.png
    python -m charm_maker run photos/antibody/antibody.png --product earrings --out output/antibody-earrings
"""
import math, sys
from pathlib import Path
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

W = 3.4        # chain (domain) width
L = 5.0        # domain length
GAP = 1.0      # white gap between domains and between chains
import os
ANG = float(os.environ.get('ANG', 45))     # arm angle from vertical
BLUE, PINK, GOLD = (25, 75, 205), (232, 60, 135), (246, 176, 20)

def domain(cx, cy, length=L, width=W, angle=0.0):
    """A rounded domain (capsule) centred at (cx, cy), long axis rotated `angle` degrees from vertical."""
    seg = LineString([(0, -(length - width) / 2), (0, (length - width) / 2)]).buffer(width / 2, resolution=32)
    return translate(rotate(seg, angle, origin=(0, 0)), cx, cy)

shapes = []   # (geometry, color)
# Fc stem: two heavy chains side by side, CH2 above CH3.
off = (W + GAP) / 2
top = -2.6
for sx in (-1, 1):
    x = sx * off
    shapes.append((domain(x, top - L / 2), BLUE))                    # CH2
    shapes.append((domain(x, top - L - GAP - L / 2), BLUE))          # CH3
# Arms, built straight up in local coordinates and then turned: the heavy chain on the inner
# side (toward the V), the light chain outside; constant domain first, the variable tip after it.
S0 = float(os.environ.get('S0', 1.0))      # where the domains start along the arm, from the pivot
HX, HY = float(os.environ.get('HX', 2.4)), float(os.environ.get('HY', -1.6))   # pivot of each arm
for side in (-1, 1):
    inner = -side            # local x of the inner side (left arm: +x turns to the inner side)
    parts = []
    for chain_x, const_col in ((inner * off, BLUE), (-inner * off, PINK)):
        for k, col in ((0, const_col), (1, GOLD)):
            y = S0 + L / 2 + k * (L + GAP)
            parts.append((domain(chain_x, y), col))
    for g, col in parts:
        g = rotate(g, -side * ANG, origin=(0, 0))
        shapes.append((translate(g, side * HX, HY), col))
# Hinge: each heavy chain runs up from CH2 into its arm's heavy chain.
for side in (-1, 1):
    inner = -side
    a = math.radians(ANG)
    # bottom of the arm's heavy chain (local (inner*off, S0 + 0.9)), turned and moved like the arm
    lx, ly = inner * off, S0 + W / 2
    gx = lx * math.cos(a) + ly * math.sin(a) * side * 1.0
    gx = side * HX + (lx * math.cos(math.radians(-side * ANG)) - ly * math.sin(math.radians(-side * ANG)))
    gy = HY + (lx * math.sin(math.radians(-side * ANG)) + ly * math.cos(math.radians(-side * ANG)))
    x = side * off
    shapes.append((LineString([(x, top - W / 2), (x, -0.3), (gx, gy)]).buffer(0.7, resolution=16), BLUE))
# Disulfide bridge across the hinge.
shapes.append((box(-off, top + 0.9, off, top + 1.55), BLUE))
domains = [g for g, c in shapes if g.area > 12]
clear = min(a.distance(b) for i, a in enumerate(domains) for b in domains[i + 1:])
print('closest gap between segments:', round(clear, 2), 'mm')
if os.environ.get('SKIP'):
    allb = unary_union([g for g, _ in shapes]).bounds
    print('RESULT', round(clear, 2), round(allb[3] - allb[1], 1), round(allb[2] - allb[0], 1)); sys.exit()

out = Path(sys.argv[1]); ppm = 40
allg = unary_union([g for g, _ in shapes])
x0, y0, x1, y1 = allg.bounds
pad = 4
Wpx, Hpx = int((x1 - x0 + 2 * pad) * ppm), int((y1 - y0 + 2 * pad) * ppm)
img = Image.new("RGB", (Wpx, Hpx), "white")
d = ImageDraw.Draw(img)
def P(x, y): return ((x - x0 + pad) * ppm, (y1 + pad - y) * ppm)
for g, col in shapes:
    for p in getattr(g, "geoms", [g]):
        d.polygon([P(*c) for c in p.exterior.coords], fill=col)
img.save(out)
print(out, img.size, "mm:", round(x1 - x0, 1), "x", round(y1 - y0, 1))
