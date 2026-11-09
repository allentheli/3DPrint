"""Milestone 0: the fit-test plate.

Numbered coupons, one per candidate size, for every fit-critical value in config,
plus one figure stand. Allen prints the plate once, tries the real hardware, and
reports the numbers that fit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import manifold3d as m3d

from .geom import (
    circle,
    cylinder,
    extrude,
    move_to,
    plus,
    rounded_rect,
    size,
    square,
)
from .labels import label_shape
from .stand import build_stand


@dataclass
class Coupon:
    number: int
    group: str          # config key under `fit:`
    candidate: float    # the size this coupon tests
    description: str
    solid: m3d.Manifold
    feature_center: tuple[float, float]   # where the pocket/hole is, local mm
    feature_size: float                    # diameter or square side
    outline: object                        # Shapely polygon of the coupon outline (local)
    extras: dict = field(default_factory=dict)


@dataclass
class FitPlate:
    coupons: list[Coupon]
    stand: m3d.Manifold
    placed: dict[str, m3d.Manifold]        # name -> solid moved into plate position
    positions: dict[str, tuple[float, float]]
    plate_size: tuple[float, float]


def _coupon_body(cfg: dict, key: str, number: int):
    """A rounded tag. Feature goes in the lower square, label in the top strip."""
    ft = cfg["fit_test"]
    w, length, t = ft[key]
    r = ft["coupon_corner_radius"]
    outline = rounded_rect(w, length, r, w / 2, length / 2)
    body = extrude(outline, t)
    feature_center = (w / 2, w / 2)
    label_cy = w + (length - w) / 2
    label = label_shape(str(number), ft["label_height"], ft["label_stroke"], w / 2, label_cy)
    body = body + extrude(label, ft["label_raise"], t)
    return body, outline, feature_center, t


def build_coupons(cfg: dict) -> list[Coupon]:
    fit = cfg["fit"]
    hw = cfg["hardware"]
    ft = cfg["fit_test"]
    coupons: list[Coupon] = []
    n = 0

    # 1. Clip pad pockets (0.6 mm deep, on the up-facing side).
    for d in fit["clip_pocket_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "clip_coupon", n)
        depth = hw["clip_pocket_depth"]
        body = body - cylinder(d, depth + 1.0, cx, cy, t - depth)
        coupons.append(Coupon(n, "clip_pocket_diameter", d, f"clip pad pocket {d} mm, {depth} mm deep",
                              body, (cx, cy), d, outline, {"depth": depth}))

    # 2. Keyring holes (through).
    for d in fit["keyring_hole_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "keyring_coupon", n)
        body = body - cylinder(d, t + 2.0, cx, cy, -1.0)
        coupons.append(Coupon(n, "keyring_hole_diameter", d, f"split-ring hole {d} mm",
                              body, (cx, cy), d, outline))

    # 3. Jump-ring holes (through).
    for d in fit["jump_ring_hole_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "jump_ring_coupon", n)
        body = body - cylinder(d, t + 2.0, cx, cy, -1.0)
        coupons.append(Coupon(n, "jump_ring_hole_diameter", d, f"jump-ring hole {d} mm",
                              body, (cx, cy), d, outline))

    # 4. Magnet pockets (1.9 mm deep, on the up-facing side).
    for d in fit["magnet_pocket_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "magnet_coupon", n)
        depth = hw["magnet_pocket_depth"]
        body = body - cylinder(d, depth + 1.0, cx, cy, t - depth)
        coupons.append(Coupon(n, "magnet_pocket_diameter", d, f"magnet pocket {d} mm, {depth} mm deep",
                              body, (cx, cy), d, outline, {"depth": depth}))

    # 5. MX switch cutouts in a 1.5 mm plate (through).
    for s in fit["switch_cutout"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "switch_coupon", n)
        body = body - extrude(square(s, cx, cy), t + 2.0, -1.0)
        coupons.append(Coupon(n, "switch_cutout", s, f"switch cutout {s} mm square in a {t} mm plate",
                              body, (cx, cy), s, outline))

    # 6. Keycap stem sockets: a boss with a plus-shaped hole, open at the top.
    for c in fit["stem_socket_clearance"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "stem_coupon", n)
        boss_h = ft["stem_boss_height"]
        boss = cylinder(ft["stem_boss_diameter"], boss_h, cx, cy, t)
        arm_x = hw["mx_stem_arm_x"] + c
        arm_y = hw["mx_stem_arm_y"] + c
        span = hw["mx_stem_span"] + c
        socket = extrude(plus(span, arm_x, arm_y, cx, cy), ft["stem_socket_depth"] + 1.0,
                         t + boss_h - ft["stem_socket_depth"])
        body = body + boss - socket
        coupons.append(Coupon(n, "stem_socket_clearance", c,
                              f"stem socket arms {arm_x:.2f} x {arm_y:.2f} mm (clearance {c} mm)",
                              body, (cx, cy), ft["stem_boss_diameter"], outline,
                              {"arm_x": arm_x, "arm_y": arm_y, "span": span,
                               "depth": ft["stem_socket_depth"]}))
    return coupons


def build_fit_plate(cfg: dict) -> FitPlate:
    coupons = build_coupons(cfg)
    stand = build_stand(cfg)
    gap = cfg["fit_test"]["gap"]

    placed: dict[str, m3d.Manifold] = {}
    positions: dict[str, tuple[float, float]] = {}

    # Lay coupons out in rows, one row per group.
    x = y = 0.0
    row_h = 0.0
    max_x = 0.0
    current_group = None
    for c in coupons:
        if c.group != current_group and current_group is not None:
            x = 0.0
            y += row_h + gap
            row_h = 0.0
        current_group = c.group
        name = f"fit-{c.number:02d}"
        placed[name] = move_to(c.solid, x, y)
        positions[name] = (x, y)
        w, h, _ = size(c.solid)
        x += w + gap
        row_h = max(row_h, h)
        max_x = max(max_x, x)
    # Stand goes to the right of the rows.
    sx = max_x + gap
    placed["stand"] = move_to(stand, sx, 0.0)
    positions["stand"] = (sx, 0.0)
    sw, sh, _ = size(stand)
    plate_w = sx + sw
    plate_h = max(y + row_h, sh)
    return FitPlate(coupons, stand, placed, positions, (plate_w, plate_h))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

GROUP_TITLES = {
    "clip_pocket_diameter": ("Hair clip pad pocket", "Press the clip's round pad into each pocket. Best = snug, pad fully seated, no rocking."),
    "keyring_hole_diameter": ("Split-ring hole", "Thread a 25 mm split key ring through each hole. Best = goes on without forcing and turns freely."),
    "jump_ring_hole_diameter": ("Jump-ring hole", "Open a jump ring and pass it through each hole. Best = passes easily; the smallest that does."),
    "magnet_pocket_diameter": ("Magnet pocket", "Push a 10 x 2 mm magnet into each pocket. Best = snug, sits a hair proud, does not fall out upside down."),
    "switch_cutout": ("Switch cutout", "Push a switch into each square from the top until it clicks. Best = snaps in, no wobble, can be pulled out with effort."),
    "stem_socket_clearance": ("Keycap stem socket", "Press each boss onto a switch stem. Best = firm push-on, stays on when you shake it, comes off with a pull."),
}


def fit_guide_markdown(cfg: dict, plate: "FitPlate") -> str:
    hw = cfg["hardware"]
    lines = [
        "# Fit test (milestone 0)",
        "",
        "Print this plate once, try the real hardware on every numbered piece, and tell",
        "Claude which number fits best in each group. There are 18 numbered coupons and one",
        "figure stand.",
        "",
        "## 1. Print it",
        "",
        "1. Open Bambu Studio.",
        "2. Click **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...** and pick `fit-test.3mf`.",
        "   If Bambu Studio asks whether to load it as a project or geometry, choose **Load geometry only**.",
        "3. Leave every piece where it lands. If any piece is off the plate, click **Arrange** (the A key).",
        "4. In the **Process** panel set **Layer height** to **0.12 mm**. Supports stay **off**.",
        "5. Pick any one filament. Click **Slice plate**, then **Print plate**, and send it to the printer as usual.",
        "6. When it is done, pop the pieces off. Every piece has its number raised on the top face.",
        "",
        "## 2. Try the hardware",
        "",
    ]
    by_group: dict[str, list[Coupon]] = {}
    for c in plate.coupons:
        by_group.setdefault(c.group, []).append(c)
    step = 1
    for group, coupons in by_group.items():
        title, how = GROUP_TITLES[group]
        lines.append(f"### {step}. {title}")
        lines.append("")
        lines.append("| Piece | Tests |")
        lines.append("| --- | --- |")
        for c in coupons:
            lines.append(f"| **{c.number}** | {c.description} |")
        lines.append("")
        lines.append(how)
        lines.append("")
        step += 1
    lines += [
        f"### {step}. Stand and washer",
        "",
        "1. Put a 1 inch zinc-plated steel fender washer into the round recess on the back of the stand's upright.",
        "   It should drop in and sit flush or just below the surface. Glue it with gel super glue.",
        "2. Glue a magnet into the best magnet pocket (from step 4) with gel super glue. Let it cure.",
        f"3. Stick that piece on the fridge. It should hold its own weight. Note the magnet sits about {hw['magnet_thickness'] - hw['magnet_pocket_depth']:.1f} mm proud, on purpose.",
        "4. Stand the same piece on the stand, pocket side toward the upright, bottom edge in the slot behind the lip.",
        "   It should snap gently to the upright and stay standing.",
        "",
        "## 3. Report",
        "",
        "Tell Claude one number per group, for example:",
        "",
        "> clip 2, keyring 5, jump ring 8, magnet 11, switch 14, stem 17. Washer fits. Fridge and stand hold.",
        "",
        "If nothing fits in a group, say whether everything was too tight or too loose, and Claude",
        "will make a second plate with new sizes. Claude then runs `python -m charm_maker fit-results`",
        "and the values go into `config.yaml`.",
        "",
        "## Legend",
        "",
        "| Group | Pieces | Candidates (mm) |",
        "| --- | --- | --- |",
    ]
    for group, coupons in by_group.items():
        nums = ", ".join(str(c.number) for c in coupons)
        cands = ", ".join(str(c.candidate) for c in coupons)
        lines.append(f"| {GROUP_TITLES[group][0]} | {nums} | {cands} |")
    lines.append("")
    return "\n".join(lines)


def fit_guide_pdf(markdown_text: str, path):
    """A plain one-or-two-page PDF of the guide, for printing and keeping by the printer."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    flow = []
    table_rows: list[list[str]] = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        body = [[Paragraph(_md_inline(c), styles["BodyText"]) for c in row] for row in table_rows]
        t = Table(body, hAlign="LEFT")
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
        flow.append(Spacer(1, 3 * mm))
        table_rows = []

    for line in markdown_text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            table_rows.append(cells)
            continue
        flush_table()
        if line.startswith("# "):
            flow.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            flow.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("### "):
            flow.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("> "):
            flow.append(Paragraph(_md_inline(line[2:]), styles["Italic"]))
        elif line.strip():
            flow.append(Paragraph(_md_inline(line), styles["BodyText"]))
        else:
            flow.append(Spacer(1, 2 * mm))
    flush_table()
    doc.build(flow)
    return path


def _md_inline(text: str) -> str:
    import re

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", text)
    return text


def write_fit_test(cfg: dict, plate: "FitPlate", out_dir) -> dict:
    from pathlib import Path

    from .export import write_plate
    from .preview import render_plan, render_shaded

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = write_plate(plate.placed, out_dir, "fit-test")
    paths["plan"] = render_plan(plate, out_dir / "fit-test-plan.png", title="Charm Maker fit-test plate (top view)")
    paths["preview"] = render_shaded(plate.placed, out_dir / "fit-test-preview.png")
    paths["stand-front"] = render_shaded({"stand": plate.placed["stand"]}, out_dir / "stand-front.png",
                                         view=(20.0, 20.0), px_per_mm=10, labels=False)
    paths["stand-back"] = render_shaded({"stand": plate.placed["stand"]}, out_dir / "stand-back.png",
                                        view=(20.0, 200.0), px_per_mm=10, labels=False)
    guide = fit_guide_markdown(cfg, plate)
    md = out_dir / "fit-test-guide.md"
    md.write_text(guide, encoding="utf-8")
    paths["guide-md"] = md
    paths["guide-pdf"] = fit_guide_pdf(guide, out_dir / "fit-test-guide.pdf")
    return paths
