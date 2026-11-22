"""A Christmas tree topper: a chunky five-pointed star with the family's names (Allen, 2026-11-22: "Give me a
star with names").

The names are raised on the four lower and side arms, in the order given (top left, top right, bottom left,
bottom right), all the same size, as big as fits; a raised heart sits in the middle where they meet, a raised
border runs round the edge, and the top arm stays plain. The star prints face-up and flat; the raised parts are
separate parts, so one color change at the top gives gold with (say) red names. A cone that slips over the top
of the tree prints standing beside it, and the star's tab slides into the slot on the cone (a drop of glue).

    python tools/star_topper.py Allen Emma Madison Alison [--out output/star-topper] [--size 176]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import cv2
import manifold3d as m3d
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from treasure_chest import box, heart  # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
SEG = 72

P = dict(
    R=88.0, r_ratio=0.5,          # tip radius; inner corners at half of it (a chubby star with room for names)
    T=6.0, fillet=1.5,            # body thickness, rounded top edge
    raise_=1.2,                   # names, heart and border stand 1.2 mm (6 layers at 0.2 mm)
    rim_in=1.5, rim_w=2.5,        # the border, inside the rounded edge
    gap=1.2,                      # clear space around every name
    heart_w=24.0,
    tab_w=14.0, tab_len=24.0,     # tab below the bottom inner corner, into the cone's slot
    slot_depth=16.0, fit=0.4,     # slot on the cone; gap around the tab (glued)
    cone_h=70.0, cone_in=(26.0, 9.0), cone_wall=2.0,   # takes a tree tip from 9 to 26 mm thick
)


def star_outline(R: float, r: float) -> CS:
    pts = []
    for k in range(10):
        a = math.radians(90 + 36 * k)
        rad = R if k % 2 == 0 else r
        pts.append((rad * math.cos(a), rad * math.sin(a)))
    s = CS([np.array(pts)])
    s = s.offset(-3.0, m3d.JoinType.Round, circular_segments=SEG).offset(3.0, m3d.JoinType.Round, circular_segments=SEG)
    return s.offset(2.5, m3d.JoinType.Round, circular_segments=SEG).offset(-2.5, m3d.JoinType.Round, circular_segments=SEG)


def text_outline(text: str, height_mm: float) -> CS:
    """The text as a shape, `height_mm` from its lowest to highest ink, centered on the origin, reading along +x.
    Drawn large with the font and traced (40 px per mm of height, so the outline is smooth)."""
    px = 40 * 12
    font = ImageFont.truetype(FONT, px)
    l, t, r_, b = font.getbbox(text)
    pad = 20
    img = Image.new("L", (r_ - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(img).text((pad - l, pad - t), text, fill=255, font=font)
    mask = (np.asarray(img) > 127).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    ys, xs = np.nonzero(mask)
    k = height_mm / (ys.max() - ys.min() + 1)
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    polys = [np.stack([(c[:, 0, 0] - cx) * k, -(c[:, 0, 1] - cy) * k], 1) for c in contours if len(c) >= 3]
    return CS(polys, m3d.FillRule.EvenOdd).simplify(0.01)


def place(cs: CS, angle_deg: float, center) -> CS:
    return cs.rotate(angle_deg).translate(list(center))


def layout_names(names: list[str], star: CS, keep_out: CS, p: dict):
    """The biggest common text height at which each name fits on its arm (inside the border, clear of the
    heart and of each other). Returns (height, [placed outlines])."""
    arms = [162.0, 18.0, 234.0, 306.0]          # top left, top right, bottom left, bottom right
    allowed = star.offset(-(p["rim_in"] + p["rim_w"] + p["gap"]), m3d.JoinType.Round, circular_segments=SEG) - keep_out
    for h in np.arange(16.0, 5.0, -0.25):
        placed = []
        for name, arm in zip(names, arms):
            reads = arm if math.cos(math.radians(arm)) > 0 else arm + 180    # left to right, never upside down
            t = text_outline(name, h)
            u = (math.cos(math.radians(arm)), math.sin(math.radians(arm)))
            ok = [rho for rho in np.arange(8.0, p["R"], 0.5)
                  if (place(t, reads, (rho * u[0], rho * u[1])) - allowed).area() < 1e-3]
            if not ok:
                break
            rho = (min(ok) + max(ok)) / 2           # the middle of the room on its arm
            placed.append(place(t, reads, (rho * u[0], rho * u[1])))
        else:
            clear = all((placed[i] ^ placed[j].offset(p["gap"], m3d.JoinType.Round)).area() < 1e-3
                        for i in range(len(placed)) for j in range(i + 1, len(placed)))
            if clear:
                return float(h), placed
    raise ValueError("the names do not fit; try a bigger --size")


def build(names: list[str], p: dict):
    R, T, f, hr = p["R"], p["T"], p["fillet"], p["raise_"]
    r = R * p["r_ratio"]
    star = star_outline(R, r)
    # Body with a rounded top edge (stacked thin steps), and the tab below the bottom inner corner.
    body = star.extrude(T - f)
    n = 8
    for i in range(n):
        u0, u1 = f * i / n, f * (i + 1) / n
        inset = f - math.sqrt(max(f * f - u1 * u1, 0.0))
        body = body + star.offset(-inset, m3d.JoinType.Round, circular_segments=SEG).extrude(u1 - u0).translate([0, 0, T - f + u0])
    tab = box(-p["tab_w"] / 2, p["tab_w"] / 2, -r - p["tab_len"], -r + 6.0, 0, T)
    body = body + tab
    rim = (star.offset(-p["rim_in"], m3d.JoinType.Round, circular_segments=SEG)
           - star.offset(-(p["rim_in"] + p["rim_w"]), m3d.JoinType.Round, circular_segments=SEG))
    hrt = heart(p["heart_w"], stretch=1.15)
    h, placed = layout_names(names, star, hrt.offset(p["gap"] + 0.5, m3d.JoinType.Round, circular_segments=SEG), p)
    parts = {"star": body,
             "border": rim.extrude(hr).translate([0, 0, T]),
             "heart": hrt.extrude(hr).translate([0, 0, T])}
    for name, cs in zip(names, placed):
        parts[f"name-{name.lower()}"] = cs.extrude(hr).translate([0, 0, T])
    return parts, h, r


def mount(p: dict) -> M:
    """A cone that slips over the tree's top tip (9 to 26 mm thick), with a slot on top for the star's tab and
    two slots near the bottom for a twist tie. Prints standing, wide end down, no supports."""
    H, (d0, d1), w = p["cone_h"], p["cone_in"], p["cone_wall"]
    outer = M.cylinder(H, d0 / 2 + w, d1 / 2 + w + 2.0, circular_segments=SEG)
    inner = M.cylinder(H - 4.0, d0 / 2, d1 / 2, circular_segments=SEG).translate([0, 0, -0.01])
    bw, bd = p["tab_w"] + p["fit"] + 4.0, p["T"] + p["fit"] + 4.0
    block = box(-bw / 2, bw / 2, -bd / 2, bd / 2, H - 0.5, H + p["slot_depth"] + 2.0)
    slot = box(-(p["tab_w"] + p["fit"]) / 2, (p["tab_w"] + p["fit"]) / 2, -(p["T"] + p["fit"]) / 2, (p["T"] + p["fit"]) / 2,
               H + 2.0, H + p["slot_depth"] + 3.0)
    tie = box(-2.5, 2.5, -d0, d0, 5.0, 7.5)       # through both walls, front to back
    return (outer - inner) + block - slot - tie


def main() -> None:
    ap = argparse.ArgumentParser(description="Christmas star topper with names")
    ap.add_argument("names", nargs=4)
    ap.add_argument("--out", default=str(ROOT / "output" / "star-topper"))
    ap.add_argument("--size", type=float, default=176.0, help="star width from tip to tip, mm")
    args = ap.parse_args()
    p = dict(P)
    p["R"] = args.size / (2 * math.sin(math.radians(72)))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    parts, h, r = build(args.names, p)
    cone = mount(p)
    for k, s in list(parts.items()) + [("mount", cone)]:
        assert s.status() == m3d.Error.NoError and not s.is_empty(), k
    bb = parts["star"].bounding_box()
    print(f"star {bb[3] - bb[0]:.0f} x {bb[4] - bb[1]:.0f} mm, names {h:.2f} mm tall")
    write_files(args.names, parts, cone, h, r, p, out)


def write_files(names, parts, cone, h, r, p, out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    GOLD, RED = (232, 180, 40), (200, 30, 45)
    bb = parts["star"].bounding_box()
    cb = cone.bounding_box()
    gap = 12.0
    total = (bb[3] - bb[0]) + gap + (cb[3] - cb[0])
    x0 = 128 - total / 2
    sx, sy = x0 - bb[0], 128 - (bb[1] + bb[4]) / 2
    cx = x0 + (bb[3] - bb[0]) + gap - cb[0]
    star_parts = [(k, s.translate([sx, sy, 0]), 1 if k == "star" else 2, GOLD if k == "star" else RED)
                  for k, s in parts.items()]
    write_bambu_3mf([("star", star_parts), ("tree-mount", [("tree-mount", cone.translate([cx, 128, 0]), 1, GOLD)])],
                    out / "star-topper.3mf", plate_name="star-topper")
    # Pictures: the star standing in its mount, from the front and at an angle.
    up = {k: s.translate([0, 0, -p["T"] / 2]).rotate([90, 0, 0]) for k, s in parts.items()}
    lift = (p["cone_h"] + 2.0) - (-r - p["tab_len"])
    up = {k: s.translate([0, 0, lift]) for k, s in up.items()}
    colors = {k: (GOLD if k == "star" else RED) for k in up}
    scene = dict(up, mount=cone)
    colors["mount"] = GOLD
    render_shaded(scene, out / "star-front.png", view=(6.0, -8.0), px_per_mm=5.0, labels=False, colors=colors)
    render_shaded(scene, out / "star-angle.png", view=(18.0, -35.0), px_per_mm=5.0, labels=False, colors=colors)
    w = bb[3] - bb[0]
    (out / "PRINT_NOTES.md").write_text(f"""# Star tree topper: print notes

{", ".join(names)}: one name on each side arm, a heart in the middle, a border round the edge.
The star is {w:.0f} mm across and {bb[4] - bb[1]:.0f} mm tall with its tab; the names are {h:.1f} mm tall.

## Plate: `star-topper.3mf`

- The star lies face-up; the tree mount (the cone) stands beside it. Don't press **Arrange**.
- **Slot 1: gold** (or yellow) for the star and the mount. **Slot 2: red** for the raised names, heart and border.
  With all raised parts in one color there is a single color change, at the top. Each name is its own part
  (`name-...`), so you can give each one its own color in Bambu Studio; that adds a few color changes on the top
  6 layers only.
- Layer height 0.20 mm. Supports off. Default infill.

## Putting it on

1. Push the star's tab (the square bit at the bottom, between the two lower points) into the slot on top of the
   cone, names facing front. A drop of glue makes it permanent.
2. Slide the cone over the top tip of the tree. It fits tips from about 9 to 26 mm thick.
3. If it leans, tie it on through the two small slots near the bottom of the cone with a twist tie.
""")


if __name__ == "__main__":
    main()
