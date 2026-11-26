"""Text plates for BK-Projects' "Trophy Cup with Easy Customizable Text Plate" (Allen's MakerWorld download, Standard
Digital File License: personal printing only; read from his file at run time, never in git). Allen, 2026-11-26:
"we can use this, and we can edit the text".

The designer's plate (45 x 17.5 x 2 mm, chamfered underneath, it fits the recess on the front or back of the cup's
base) is used as is; only the raised text is ours: one or two lines, bold, rounded corners, 0.6 mm tall like the
original, each line as big as fits (at most 4.8 mm). Writes:

    award-plates.3mf      every plate on one plate (gold plate in slot 1, text in slot 2: one color change)
    award-plates.png      what each plate says, where it sits
    mockup.glb            a few cups with their plates in the base, for a picture

    python -I tools/cup_awards.py <CupBambu.3mf> [--out output/cup-awards] [--awards "I ATE|- 2026" ...]
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import cv2
import manifold3d as m3d
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from star_topper import text_outline             # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection

AWARDS = [
    "I ATE|- 2026",
    "THANKSGIVING|CHAMPION",
    "LEFTOVER|LEGEND",
    # for the biggest potato fan (pick one)
    "TOP|TATER",
    "SPUD|STUD",
    "MASHED POTATO|MVP",
    "CHAMPION OF|POTATOES",
    # more
    "STRETCHY PANTS|AWARD",
    "MOST|STUFFED",
    "GRAVY|BOSS",
    "PIE|MASTER",
    "FOOD COMA|CHAMPION",
    "TURKEY|WHISPERER",
    "SECONDS AND|THIRDS CLUB",
    "PROFESSIONAL|NAPPER",
    "WORLD'S BEST|DISHWASHER",
]

PLATE = (45.0, 17.5, 2.0)
CAP, GAP, MAX_W, RAISE = 4.8, 2.3, 40.5, 0.6
GOLD, BROWN = (224, 172, 52), (92, 58, 36)


def read_cup(path: Path) -> dict[str, M]:
    """The designer's parts by name (Top, Bottom, Frame, Your Text), each placed as in their file (object coords)."""
    z = zipfile.ZipFile(path)
    main = z.read("3D/3dmodel.model").decode("utf-8", "replace")
    ms = z.read("Metadata/model_settings.config").decode("utf-8", "replace")
    names = re.findall(r'<part id="(\d+)" subtype="normal_part">\s*<metadata key="name" value="([^"]+)"', ms)
    names = dict(names)
    subs: dict[str, str] = {}
    out = {}
    for c in re.finditer(r'<component p:path="([^"]+)" objectid="(\d+)"[^>]*transform="([^"]+)"', main):
        path_, oid, tf = c.group(1).lstrip("/"), c.group(2), [float(x) for x in c.group(3).split()]
        xml = subs.setdefault(path_, z.read(path_).decode("utf-8", "replace"))
        body = re.search(r'<object id="%s"[^>]*>(.*?)</object>' % oid, xml, re.S).group(1)
        v = np.array(re.findall(r'<vertex x="([-\d.eE+]+)" y="([-\d.eE+]+)" z="([-\d.eE+]+)"', body), float)
        f = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', body), int)
        rot = np.array(tf[:9]).reshape(3, 3)
        v = v @ rot + np.array(tf[9:12])
        s = M(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f.astype(np.uint32)))
        out[names.get(oid, oid)] = s
    return out


def line_shape(text: str) -> CS:
    cs = text_outline(text, CAP)
    w = cs.bounds()[2] - cs.bounds()[0]
    if w > MAX_W:
        cs = text_outline(text, CAP * MAX_W / w)
    r = 0.16                                               # rounded corners, like the original's rounded font
    return cs.offset(-r, m3d.JoinType.Round).offset(r, m3d.JoinType.Round)


def plate_text(award: str) -> CS:
    """One or two lines (split by |), centred on the plate."""
    lines = [line_shape(t.strip()) for t in award.split("|") if t.strip()]
    hs = [ln.bounds()[3] - ln.bounds()[1] for ln in lines]
    total = sum(hs) + GAP * (len(lines) - 1)
    y = total / 2
    placed = []
    for ln, h in zip(lines, hs):
        b = ln.bounds()
        placed.append(ln.translate([-(b[0] + b[2]) / 2, y - b[3]]))
        y -= h + GAP
    out = placed[0]
    for p in placed[1:]:
        out = out + p
    return out


def plate(frame: M, award: str) -> tuple[M, M]:
    """The designer's plate (centred, back at z = 0) and our raised text on its top."""
    b = frame.bounding_box()
    fr = frame.translate([-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2]])
    top = fr.bounding_box()[5]
    text = plate_text(award).extrude(RAISE + 0.05).translate([0, 0, top - 0.05])
    return fr, text


def layout(n: int, gap: float = 7.0, bed: float = 256.0):
    w, h = PLATE[0] + gap, PLATE[1] + gap
    cols = int((bed - 16) // w)
    rows = -(-n // cols)
    x0, y0 = bed / 2 - (min(n, cols) * w - gap) / 2 + PLATE[0] / 2, bed / 2 + (rows * h - gap) / 2 - PLATE[1] / 2
    return [(x0 + (i % cols) * w, y0 - (i // cols) * h) for i in range(n)]


def picture(awards: list[str], spots, path: Path, px: float = 6.0) -> None:
    """Each plate as it sits on the plate (top view), with its number."""
    xs = [s[0] for s in spots]; ys = [s[1] for s in spots]
    x0, x1 = min(xs) - 30, max(xs) + 30
    y0, y1 = min(ys) - 18, max(ys) + 18
    W, H = int((x1 - x0) * px), int((y1 - y0) * px)
    img = np.full((H, W, 3), 245, np.uint8)
    for i, (a, (cx, cy)) in enumerate(zip(awards, spots)):
        to = lambda p: np.stack([(p[:, 0] + cx - x0) * px, (y1 - (p[:, 1] + cy)) * px], 1).astype(np.int32)
        rect = np.array([[-22.5, -8.75], [22.5, -8.75], [22.5, 8.75], [-22.5, 8.75]])
        cv2.fillPoly(img, [to(rect)], GOLD[::-1], cv2.LINE_AA)
        polys = [np.asarray(p) for p in plate_text(a).to_polygons()]
        for p in sorted(polys, key=lambda p: -abs(_area(p))):
            cv2.fillPoly(img, [to(p)], (BROWN if _area(p) > 0 else GOLD)[::-1], cv2.LINE_AA)
        cv2.putText(img, str(i + 1), (int((cx - 22.5 - x0) * px) - 26, int((y1 - cy) * px) + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), img)


def _area(p) -> float:
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def mockup(parts: dict[str, M], awards: list[str], path: Path) -> None:
    """Cups side by side with their plates in the front recess of the base (y up, front toward +z)."""
    import turkey_scepter as TS
    up = lambda s: s.rotate([-90, 0, 0])                    # z up -> y up, -y (front) -> +z
    top, bottom = up(parts["Top"]), up(parts["Bottom"])
    bb = parts["Bottom"].bounding_box()                      # cup coords: front face at y = bb[1]
    scene = {}
    for i, a in enumerate(awards):
        fr, tx = plate(parts["Frame"], a)
        # stand the plate up in the front recess (about 1.1 mm deep): its back on the recess floor
        put = lambda s: s.translate([0, 0, -1.0]).rotate([90, 0, 0]).translate(
            [0, bb[1] + 1.1 - 1.0, (bb[2] + bb[5]) / 2]).rotate([-90, 0, 0]).translate([i * 100.0, 0, 0])
        scene[f"{i}-cup"] = (top.translate([i * 100.0, 0, 0]), "gold")
        scene[f"{i}-base"] = (bottom.translate([i * 100.0, 0, 0]), "walnut")
        scene[f"{i}-plate"] = (put(fr), "gold")
        scene[f"{i}-text"] = (put(tx), "ink")
    TS.COLORS.update({"walnut": ("#4A2C1A", False), "ink": ("#3A2416", False)})
    TS.to_glb(scene, path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Text plates for the trophy cup")
    ap.add_argument("cup", type=Path, help="BK-Projects' CupBambu.3mf (Allen's download)")
    ap.add_argument("--awards", nargs="*", default=AWARDS, help='"LINE 1|LINE 2" for each plate')
    ap.add_argument("--mockup", nargs="*", type=int, default=[1, 2, 3, 4], help="plate numbers to show on cups")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "cup-awards")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    parts = read_cup(args.cup)
    spots = layout(len(args.awards))
    objects = []
    for i, (a, (x, y)) in enumerate(zip(args.awards, spots)):
        fr, tx = plate(parts["Frame"], a)
        assert fr.status() == m3d.Error.NoError and tx.status() == m3d.Error.NoError and not tx.is_empty(), a
        name = f"{i + 1:02d}-" + re.sub(r"[^a-z0-9]+", "-", a.replace("|", " ").lower()).strip("-")
        objects.append((name, [("plate", fr.translate([x, y, 0]), 1, GOLD), ("text", tx.translate([x, y, 0]), 2, BROWN)]))
    from charm_maker.bambu3mf import write_bambu_3mf
    write_bambu_3mf(objects, args.out / "award-plates.3mf", plate_name="award-plates")
    picture(args.awards, spots, args.out / "award-plates.png")
    mockup(parts, [args.awards[k - 1] for k in args.mockup], args.out / "mockup.glb")
    print(f"{len(args.awards)} plates; wrote {args.out}")


if __name__ == "__main__":
    main()
