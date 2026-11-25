"""A turkey royal scepter: Fran Gaur's SPQR Roman scepter (Allen's download) with our own regal-but-goofy turkey in
place of the eagle (Allen, 2026-11-25: "now I want a turkey royal scepter to go with it" [the turkey trophy crown];
"do a mock up of the first one ... I want the turkey to be goofy with eyes pointing in different directions"; "I
still like the spread eagle/turkey tail, so its not only funny but also very very regal"; "u dont need to use that
turkey model exactly").

The scepter model is read from Allen's file at run time (MakerWorld, Standard Digital File License: personal
printing only); neither it nor the output goes into git. The turkey is our own design, built here:

- a heraldic, front-facing turkey the size of the eagle it replaces: a tail fan spread as wide as the eagle's wings
  (two rows of banded feathers, gold tips and pearls), a bronze breast with a beard, drooping wings,
- a bare red head with a dangly snood, a wattle, and big googly eyes looking two different ways,
- a little gold crown sitting crooked on its head; no legs (Allen: a weak spot): its body sits on a round gold base
  with jewels round the side, its toes peeking out from under the belly,
- the base takes the place of the SPQR plaque and its thunderbolts, right on top of the column.

The turkey is a relief with a flat back (like a plaque), so it can print back-down.

    python -I tools/turkey_scepter.py <SPQR scepter .3mf> [--out output/turkey-scepter]

Writes the mock-up (mockup.glb) and the print files: plate 1, the turkey lying on its back (everything in front of the
fan has a tapered wall back to the flat back, so nothing prints in mid-air; a tab under the belly); plate 2, the base
and the top of the column in one piece upside down, plus the original middle and bottom-ball pieces. One color: Allen's
kids color it with acrylic markers.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import zipfile
from pathlib import Path

import manifold3d as m3d
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

M = m3d.Manifold
SEG = 48

# name: (hex color, metal)
COLORS = {
    "gold": ("#D9A83A", True),
    "bronze": ("#6B3B20", False),
    "chestnut": ("#9D432C", False),
    "tan": ("#E4BD68", False),
    "dark": ("#2A1A12", False),
    "red": ("#C8281E", False),
    "darkred": ("#8E1B17", False),
    "white": ("#F6F3EC", False),
    "black": ("#0E0E0E", False),
    "orange": ("#E8820E", False),
    "ruby": ("#B3122E", False),
    "sapphire": ("#1E4DB5", False),
    "emerald": ("#13834A", False),
}

ZB = -14.0          # the turkey's flat back (the plaque's mid-plane is z = 0, its faces z = +-17.5)


# ---------------------------------------------------------------- scepter model

def _mat(s: str) -> np.ndarray:
    v = [float(x) for x in s.split()]
    m = np.eye(4)
    if len(v) == 12:
        m[:3, :3] = np.array(v[:9]).reshape(3, 3).T
        m[:3, 3] = v[9:12]
    return m


def read_objects(path: Path) -> dict[str, M]:
    """Each object of a Bambu 3MF in its own coordinates (the plate placement is ignored)."""
    z = zipfile.ZipFile(path)
    files = {n: z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".model")}
    meshes, comps = {}, {}
    for fname, xml in files.items():
        for m in re.finditer(r'<object id="(\d+)"[^>]*>(.*?)</object>', xml, re.S):
            oid, body = m.group(1), m.group(2)
            if "<mesh>" in body:
                v = np.array(re.findall(r'<vertex x="([-\d.eE+]+)" y="([-\d.eE+]+)" z="([-\d.eE+]+)"', body), float)
                f = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', body), int)
                meshes[(fname, oid)] = (v, f)
            else:
                cl = []
                for c in re.finditer(r"<component ([^>]*)/>", body):
                    a = c.group(1)
                    p = re.search(r'p:path="([^"]+)"', a)
                    t = re.search(r'transform="([^"]+)"', a)
                    cl.append((p.group(1).lstrip("/") if p else fname, re.search(r'objectid="(\d+)"', a).group(1),
                               _mat(t.group(1)) if t else np.eye(4)))
                comps[(fname, oid)] = cl
    cfg = "Metadata/model_settings.config"
    ms = z.read(cfg).decode("utf-8", "replace") if cfg in z.namelist() else ""
    names = dict(re.findall(r'<object id="(\d+)">\s*<metadata key="name" value="([^"]+)"', ms))
    out = {}
    for (fname, oid), cl in comps.items():
        if fname != "3D/3dmodel.model":
            continue
        vs, fs, n = [], [], 0
        for p, o, t in cl:
            v, f = meshes[(p, o)]
            vs.append((np.c_[v, np.ones(len(v))] @ t.T)[:, :3])
            fs.append(f + n)
            n += len(v)
        out[names.get(oid, oid)] = _solid(np.vstack(vs), np.vstack(fs))
    return out


def _solid(v: np.ndarray, f: np.ndarray) -> M:
    s = M(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f.astype(np.uint32)))
    if s.status() != m3d.Error.NoError:
        t = trimesh.Trimesh(v, f, process=True)
        trimesh.repair.fill_holes(t)
        s = M(m3d.Mesh(vert_properties=t.vertices.astype(np.float32), tri_verts=t.faces.astype(np.uint32)))
    return s


# Measured on the model (each piece lies along y, plaque end up; the front faces +z):
# the threaded peg's shoulder of each piece meets the top of the piece below it.
STACK = {"Lower_ball.stl": 0.0, "Middle.stl": 73.7 + 52.65, "SPQR_upper.stl": 73.7 + 52.65 + 68.3 + 66.72}
# Allen (2026-11-25, circling the SPQR plaque and its thunderbolts): "make the circular base larger and replace the
# circled red part". The top piece is cut where the plaque starts, just above the column's top ring (radius 17.2), and
# the round base sits there instead.
PLAQUE_START = 42.25
COLUMN_TOP = STACK["SPQR_upper.stl"] + PLAQUE_START


def scepter(objs: dict[str, M]) -> dict[str, M]:
    out = {k.split(".")[0]: objs[k].translate([0, dy, 0]) for k, dy in STACK.items()}
    below = M.cube([400, 400, 400]).translate([-200, COLUMN_TOP - 400, -200])
    out["SPQR_upper"] = out["SPQR_upper"] ^ below
    return out


# ---------------------------------------------------------------- shapes

def ball(c, r) -> M:
    r = np.broadcast_to(np.asarray(r, float), (3,))
    return M.sphere(1.0, SEG).scale(list(r)).translate(list(c))


def ell(c, r, rot_z: float = 0.0) -> M:
    r = np.broadcast_to(np.asarray(r, float), (3,))
    return M.sphere(1.0, SEG).scale(list(r)).rotate([0, 0, rot_z]).translate(list(c))


def front_half(s: M, zb: float = ZB) -> M:
    return s ^ M.cube([2000, 2000, 1000]).translate([-1000, -1000, zb])


def relief(s: M, k: float = 0.6) -> M:
    """A convex part plus a tapered wall back to the turkey's flat back (a copy squashed onto it, `k` as wide), so
    the turkey prints lying on its back with nothing in mid-air. Seen from the front the wall hides behind the part."""
    b = s.bounding_box()
    cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
    flat = s.translate([-cx, -cy, 0]).scale([k, k, 1e-3]).translate([cx, cy, ZB + 0.05])
    return front_half(M.batch_hull([s, flat]))


def chain(points, radii, rel: bool = False) -> M:
    """Spheres hulled pairwise along a path: a tapered, bent tube (`rel`: each piece with its wall to the back)."""
    balls = [ball(p, r) for p, r in zip(points, radii)]
    segs = [M.batch_hull([a, b]) for a, b in zip(balls, balls[1:])]
    return M.batch_boolean([relief(x) if rel else x for x in segs], m3d.OpType.Add)


def ring_band(c, r0: float, r1: float) -> M:
    """Everything between radius r0 and r1 around c (in x, y), any z."""
    out = M.cylinder(400, r1, r1, 180).translate([c[0], c[1], -200])
    if r0 > 0:
        out = out - M.cylinder(402, r0, r0, 180).translate([c[0], c[1], -201])
    return out


def union(parts) -> M:
    parts = [p for p in parts if not p.is_empty()]
    return M.batch_boolean(parts, m3d.OpType.Add) if parts else M()


# ---------------------------------------------------------------- the turkey

P = dict(
    seat=17.0,                    # where the turkey's body ends flat (in its own coordinates); it sits on the base
    base_r=47.0, gems=18,         # round gold base on the column: band radius, jewels round it
    fan_c=(0.0, 67.0), fan_r=112.0, fan_n=15, fan_span=(-12.0, 192.0), fan_tip=14.5, fan_thick=4.2,
    row2_r=80.0, row2_tip=12.5, row2_thick=11.0,
    body=(0.0, 57.0, 39.0, 46.0, 31.0),          # center x, y; radii x, y, z (dome on the back plane)
    head=(3.0, 133.0), head_r=(15.0, 16.0, 13.0),
)


def turkey(p: dict = P) -> dict[str, M]:
    parts: dict[str, list[M]] = {k: [] for k in COLORS}
    cx, cy = p["fan_c"]
    C = np.array([cx, cy])

    # Tail fan, back row: long banded feathers whose tips are jewels in gold settings (Allen: "make the tip of each of
    # the turkey feather tails into gems too"); ruby, sapphire, emerald, mirrored left to right.
    R, n = p["fan_r"], p["fan_n"]
    angs = np.linspace(*p["fan_span"], n)
    back = []
    for a in angs:
        u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        b0, b1 = C + 28 * u, C + (R - p["fan_tip"]) * u
        f = M.batch_hull([ball([*b0, ZB], [6, 6, 3.5]), ball([*b1, ZB], [p["fan_tip"], p["fan_tip"], p["fan_thick"]])])
        back.append(front_half(f))
        k = abs(int(round((a - angs[0]) / (angs[1] - angs[0]))) - (n - 1) // 2)
        at = lambda s: s.rotate([0, 0, a]).translate([*(C + (R - 13.5) * u), ZB])
        parts["gold"].append(at(hex_prism(10.6, p["fan_thick"] + 0.4, stretch=1.12)))  # setting, down to the back
        gem = hex_gem(9.2, 3.6, stretch=1.12).translate([0, 0, p["fan_thick"] - 0.2])
        parts[("ruby", "sapphire", "emerald")[k % 3]].append(at(gem))
    back = union(back)
    bands = [("bronze", 0, 0.52), ("tan", 0.52, 0.59), ("bronze", 0.59, 0.74), ("gold", 0.74, 2)]
    for col, r0, r1 in bands:
        parts[col].append(back ^ ring_band(C, r0 * R, r1 * R))

    # Front row: shorter chestnut feathers between them.
    R2 = p["row2_r"]
    front = []
    for a0, a1 in zip(angs, angs[1:]):
        a = (a0 + a1) / 2
        u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        b0, b1 = C + 24 * u, C + (R2 - p["row2_tip"]) * u
        f = M.batch_hull([ball([*b0, ZB], [5, 5, 5]), ball([*b1, ZB], [p["row2_tip"], p["row2_tip"], p["row2_thick"]])])
        front.append(front_half(f))
    front = union(front)
    for col, r0, r1 in [("chestnut", 0, 0.62), ("tan", 0.62, 0.71), ("chestnut", 0.71, 0.88), ("dark", 0.88, 2)]:
        parts[col].append(front ^ ring_band(C, r0 * R2, r1 * R2))

    # Body: a bronze breast with scalloped feathers.
    bx, by, rx, ry, rz = p["body"]
    body = front_half(ell([bx, by, ZB], [rx, ry, rz]))
    parts["bronze"].append(body)

    def surf(x, y):
        q = 1 - ((x - bx) / rx) ** 2 - ((y - by) / ry) ** 2
        return ZB + rz * math.sqrt(max(q, 0.0))

    for j, y in enumerate(np.arange(by - 36, by + 30, 6.5)):
        for x in np.arange(-36 + (j % 2) * 4.5, 37, 9.0):
            q = 1 - ((x - bx) / rx) ** 2 - ((y - by) / ry) ** 2
            if q < 0.3:
                continue
            parts["bronze"].append(ell([x, y - 1.5, surf(x, y) - 0.7], [5.6, 4.4, 1.6]))

    # Wings, drooping at the sides, with tan bars.
    for side in (-1, 1):
        w = front_half(ell([side * 37, by - 5, ZB], [16, 32, 24], rot_z=side * 16))
        w2 = front_half(ell([side * 37, by - 5, ZB], [16.8, 32.8, 24.8], rot_z=side * 16))
        bars = union([w2 ^ M.cube([200, 3.2, 100]).translate([-100, by - 32 + 7.5 * k, -50]) for k in range(4)])
        parts["bronze"].append(w)
        parts["tan"].append(bars)

    # Neck and head (bare red skin), wattle, snood, beak.
    hx, hy = p["head"]
    # (Everything in front of the fan gets a wall back to the flat back: see relief().)
    parts["red"].append(chain([(0, by + 30, 0), (1.5, hy - 26, 3), (hx, hy - 8, 3)], [11, 9, 9], rel=True))
    parts["red"].append(relief(ell([hx, hy, 3], p["head_r"])))
    parts["darkred"].append(relief(ell([hx - 1, hy - 23, 10], [6.5, 9, 6])))
    parts["orange"].append(relief(M.batch_hull([ball([hx, hy - 4, 14], 5.6), ball([hx, hy - 12, 25.5], 1.3)])))
    parts["darkred"].append(chain([(hx, hy + 2, 14.5), (hx + 2.5, hy - 3, 22.5), (hx + 5, hy - 11, 26.5),
                                   (hx + 6.5, hy - 20, 25), (hx + 7, hy - 26, 22)], [2.7, 2.6, 2.4, 2.2, 2.8], rel=True))

    # Googly eyes, looking two different ways.
    eyes = [((hx - 10.6, hy + 7, 12.0), 10.5, (-0.62, 0.45, 0.64)),      # left: up and out
            ((hx + 11.0, hy + 8.5, 12.0), 11.2, (0.45, -0.55, 0.70))]     # right: down and out
    for c, r, d in eyes:
        d = np.asarray(d) / np.linalg.norm(d)
        parts["white"].append(relief(ball(c, r)))
        parts["black"].append(ball(np.asarray(c) + (r - 2.3) * d, 4.4))

    # A little crown, on crooked.
    place = lambda s: s.rotate([0, 0, -17]).translate([hx + 4, hy + 14, 1])
    parts["gold"].append(union([relief(place(c)) for c in crown_pieces()]))
    parts["red"].append(relief(place(ball([0, 4.0, 12.0], 2.2))))

    # No legs (Allen: a weak spot): the body sits on the round base; the turkey ends flat at the base's top. Its toes
    # rest on the base, peeking out from under the belly (in the print they stand up from the belly).
    s0 = p["seat"]
    for side in (-1, 1):
        x0 = side * 11
        for dx in (-0.45, 0.0, 0.45):
            x1 = x0 + side * 1.5 + dx * 13
            parts["orange"].append(chain([(x0, s0 + 2.9, 2.0), (x1, s0 + 2.8, 15.0), (x1 + dx * 1.5, s0 + 2.4, 19.5)],
                                         [2.9, 2.5, 2.1]))
            parts["dark"].append(ball([x1 + dx * 2.2, s0 + 1.7, 21.0], [1.4, 1.1, 1.8]))
    above = M.cube([1000, 1000, 1000]).translate([-500, s0, -500])
    out = {k: union(v) ^ above for k, v in parts.items() if v}
    out["bronze"] = out["bronze"] + tab(p)
    return out


TAB = (12.0, 12.0, 10.0)       # the hidden tab under the belly: half width, depth into the base, thickness (from the back)
FIT = 0.25                     # gap round the tab in its slot (glued)


def tab(p: dict = P) -> M:
    hw, d, t = TAB
    s0 = p["seat"]
    pts = [(sx * hw, y, z) for sx in (-1, 1) for y in (s0 + 2.0, s0 - d + 0.8) for z in (ZB, ZB + t)]
    pts += [(sx * (hw - 0.8), s0 - d, z) for sx in (-1, 1) for z in (ZB, ZB + t - 0.8)]      # chamfered end
    return M.hull_points(np.array(pts, float))


BASE_TOP = 63.0


def base(p: dict = P) -> dict[str, M]:
    """The round gold base on top of the column (its bottom at y = 0): it flares out from the column's top ring at
    45 degrees, a beaded lip, a band of jewels, a beaded top rim, and a slot in the top for the turkey's tab. It is
    printed in one piece with the top of the column, upside down (its flat top on the plate)."""
    r, h = p["base_r"], BASE_TOP
    prof = [(0, 0), (17.2, 0), (17.2, 3.0), (r - 3, 3.0 + r - 20.2), (r + 3, 9.0 + r - 20.2), (r + 3, 10.5 + r - 20.2),
            (r, 13.2 + r - 20.2), (r, h - 6.0), (r + 3, h - 3.0), (r + 3, h - 1.5), (r + 1.5, h), (0, h)]
    drum = M.revolve(m3d.CrossSection([np.array(prof, float)]), 120).rotate([-90, 0, 0])   # axis z -> y
    gold = [drum]
    lip_y = 9.75 + r - 20.2
    for k in range(72):                                   # beads round the lip and the top rim (flush with the top)
        a = math.radians(k * 5.0)
        for rr, y in ((r + 2.6, h - 1.7), (r + 2.6, lip_y)):
            gold.append(ball([rr * math.sin(a), y, rr * math.cos(a)], 1.7))
    band_mid = (13.2 + r - 20.2 + h - 6.0) / 2
    gems = {"ruby": [], "sapphire": [], "emerald": []}
    for k in range(p["gems"]):
        a = 360.0 * k / p["gems"]
        place = lambda s: s.translate([0, 0, r]).rotate([0, a, 0]).translate([0, band_mid, 0])
        gold.append(place(hex_prism(7.0, 2.2).translate([0, 0, -0.5])))                  # setting
        gems[("ruby", "sapphire", "emerald")[k % 3]].append(place(hex_gem(5.8, 2.8).translate([0, 0, 1.2])))
    hw, d, t = TAB
    slot = M.cube([2 * (hw + FIT), d + 0.5 + 1.0, t + 2 * FIT]).translate([-(hw + FIT), h - d - 0.5, ZB - FIT])
    # A pointed end (45 degrees), so the slot's ceiling needs no bridge when the base prints upside down.
    zc, half = ZB + t / 2, t / 2 + FIT
    slot = slot + M.hull_points(np.array([(sx * (hw + FIT), y, z) for sx in (-1, 1) for y, z in
                                          ((h - d - 0.5, zc - half), (h - d - 0.5, zc + half), (h - d - 0.5 - half, zc))], float))
    out = {"gold": union(gold) - slot, **{k: union(v) for k, v in gems.items()}}
    return out


def _hexagon(r: float, z: float, turn: float = 0.0, stretch: float = 1.0) -> list:
    return [(stretch * r * math.cos(math.radians(60 * k + turn)), r * math.sin(math.radians(60 * k + turn)), z)
            for k in range(6)]


def hex_gem(r: float, h: float, stretch: float = 1.0) -> M:
    """A hexagonal cut gem facing +z from z = 0: a thin girdle, then a crown of star facets up to a flat table.
    Points along x; `stretch` makes it longer along x."""
    g = 0.5
    pts = (_hexagon(r, 0.0, stretch=stretch) + _hexagon(r, g, stretch=stretch)
           + _hexagon(0.80 * r, g + 0.5 * h, turn=30, stretch=stretch) + _hexagon(0.52 * r, g + h, stretch=stretch))
    return M.hull_points(np.array(pts))


def hex_prism(r: float, h: float, stretch: float = 1.0) -> M:
    """A hexagonal gold setting under a gem, z = 0..h, a little bigger than the gem."""
    return M.hull_points(np.array(_hexagon(r, 0.0, stretch=stretch) + _hexagon(r - 0.4, h, stretch=stretch)))


def crown_pieces() -> list[M]:
    """A small crown standing on y, as convex pieces: a (solid) band and five points, each with a pearl."""
    r, t, h = 12.0, 1.6, 8.0
    pieces = [M.cylinder(h, r, r, SEG)]
    for k in range(5):
        a = math.radians(90 + 72 * k)
        c = (r - t / 2) * np.array([math.cos(a), math.sin(a)])
        pieces += [M.cylinder(8.5, 3.2, 0.5, 16).translate([c[0], c[1], h - 0.5]), ball([*(c * 1.0), h + 8.3], 1.9)]
    return [s.rotate([-90, 0, 0]) for s in pieces]      # z (up) -> y


def disjoint(parts: dict[str, M]) -> dict[str, M]:
    """Make the colored parts not overlap: what is in front (later in this list) wins."""
    order = ["gold", "bronze", "chestnut", "tan", "dark", "red", "darkred", "orange", "white", "black",
             "ruby", "sapphire", "emerald"]
    order = [k for k in order if k in parts]
    out = {}
    for i, k in enumerate(order):
        later = union([parts[j] for j in order[i + 1:]])
        out[k] = parts[k] - later if not later.is_empty() else parts[k]
    return out


# ---------------------------------------------------------------- output

def to_glb(scene: dict[str, tuple[M, str]], path: Path) -> None:
    """Each entry name -> (solid, color key). Node names are 'colorkey__name' (the mock-up renderer reads them)."""
    sc = trimesh.Scene()
    for name, (s, col) in scene.items():
        m = s.to_mesh()
        t = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=False)
        hexc, metal = COLORS[col]
        rgb = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
        t.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=rgb + [255], metallicFactor=0.9 if metal else 0.0, roughnessFactor=0.35 if metal else 0.6))
        sc.add_geometry(t, node_name=f"{col}__{name}", geom_name=f"{col}__{name}")
    sc.export(str(path))


def _upside_down(s: M) -> M:
    """Turned so the scepter's top end is on the plate (as the original file prints its shaft pieces), centred."""
    r = s.rotate([-90, 0, 0])                    # (x, y, z) -> (x, z, -y)
    b = r.bounding_box()
    return r.translate([-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2]])


def print_pieces(objs: dict[str, M]) -> dict[str, M]:
    """The four printed pieces, each as it lies on the plate (centred on x = y = 0):
    the turkey on its back; the base and the top of the column in one piece, upside down (the base's flat top on the
    plate, the screw peg up); the middle and the bottom ball of the shaft as the original file prints them."""
    sc = scepter(objs)
    tk = union(list(turkey().values()))
    tk = union([c for c in tk.decompose() if c.volume() > 1.0])      # drop zero-volume slivers from the booleans
    b = tk.bounding_box()
    tk = tk.translate([-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -ZB])
    top = sc["SPQR_upper"] + union(list(base().values())).translate([0, COLUMN_TOP - 0.1, 0])
    return {"turkey": tk, "base-and-column-top": _upside_down(top),
            "middle": _upside_down(sc["Middle"]), "bottom-ball": _upside_down(sc["Lower_ball"])}


def unsupported(s: M, step: float = 0.2, max_from_upright: float = 55.0) -> list:
    """Spots wider than 1.5 mm that would print over thin air (beyond `max_from_upright` degrees)."""
    reach = step * math.tan(math.radians(max_from_upright))
    top = s.bounding_box()[5]
    z, prev, bad = step, s.slice(step / 2), []
    while z < top:
        cur = s.slice(z)
        un = cur - prev.offset(reach, m3d.JoinType.Round)
        if un.area() > 0.5:
            core = un.offset(-0.75, m3d.JoinType.Round)
            if not core.is_empty() and core.area() > 0.05:
                for q in core.decompose():
                    bb = q.bounds()
                    bad.append((round(z, 1), round(q.area(), 1), [round(x, 1) for x in bb]))
        prev, z = cur, z + step
    return bad


def estimate(s: M, layer: float = 0.24, skin: float = 0.9, infill: float = 0.10) -> tuple[float, float]:
    """Rough grams and hours: a 0.9 mm skin all over plus 10 % infill inside, at about 30 g an hour plus a few seconds
    a layer. Only a guide: Bambu Studio's estimate after slicing is the real one."""
    m = s.to_mesh()
    t = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=False)
    vol, area = s.volume(), t.area
    shell = min(vol, area * skin)
    grams = 1.24 * (shell + infill * (vol - shell)) / 1000.0
    b = s.bounding_box()
    hours = grams / 30.0 + (b[5] - b[2]) / layer * 3.0 / 3600.0
    return grams, hours


def layout(pieces: list[tuple[str, M]], gap: float = 10.0, bed: float = 256.0) -> list[tuple[str, M]]:
    """In a row along x, centred on the bed."""
    widths = [p.bounding_box()[3] - p.bounding_box()[0] for _, p in pieces]
    total = sum(widths) + gap * (len(pieces) - 1)
    x, out = bed / 2 - total / 2, []
    for (name, p), w in zip(pieces, widths):
        b = p.bounding_box()
        q = p.translate([x - b[0], bed / 2 - (b[1] + b[4]) / 2, 0])
        qb = q.bounding_box()
        assert qb[0] >= 2 and qb[3] <= bed - 2 and qb[1] >= 2 and qb[4] <= bed - 2, f"{name} does not fit the plate"
        out.append((name, q))
        x += w + gap
    return out


def write_print_files(objs: dict[str, M], out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    pieces = print_pieces(objs)
    WHITE = (235, 232, 222)
    plates = {"turkey-scepter-1-turkey": [("turkey", pieces["turkey"])],
              "turkey-scepter-2-shaft": [(k, pieces[k]) for k in ("base-and-column-top", "bottom-ball", "middle")]}
    report = {}
    for plate, items in plates.items():
        placed = layout(items)
        write_bambu_3mf([(name, [(name, s, 1, WHITE)]) for name, s in placed], out / f"{plate}.3mf", plate_name=plate)
        render_shaded({name: s.simplify(0.05) for name, s in placed}, out / f"{plate}.png", view=(35.0, -30.0),
                      px_per_mm=2.5, labels=True, colors={name: WHITE for name, _ in placed})
        for name, s in placed:
            b = s.bounding_box()
            g, h = estimate(s)
            bad = unsupported(s)
            report[name] = dict(plate=plate, size=(b[3] - b[0], b[4] - b[1], b[5] - b[2]), grams=g, hours=h, bad=bad)
            print(f"{plate}: {name} {b[3] - b[0]:.0f} x {b[4] - b[1]:.0f} x {b[5] - b[2]:.0f} mm, about {g:.0f} g, "
                  f"{h:.1f} h; spots over air: {len(bad)}" + (f" (first {bad[:3]})" if bad else ""))
    write_notes(report, out)
    return report


def write_notes(rep: dict, out: Path) -> None:
    t, sh = rep["turkey"], [rep[k] for k in ("base-and-column-top", "bottom-ball", "middle")]
    g1, h1 = t["grams"], t["hours"]
    g2, h2 = sum(r["grams"] for r in sh), sum(r["hours"] for r in sh)
    mid = rep["middle"]
    (out / "PRINT_NOTES.md").write_text(f"""# Turkey royal scepter: print notes

Our own goofy-but-regal turkey (jewelled tail fan, googly eyes, crooked crown) on a round jewelled base, on the fluted
shaft of Fran Gaur's SPQR Roman scepter (your download, MakerWorld Standard Digital File License: for your own
printing only). About 60 cm long; the turkey is {t['size'][0]:.0f} mm wide.

Printed in one color; the kids color it in afterwards with acrylic markers. **White PLA** takes the markers best
(any light color works). Nothing needs supports.

## Plate 1: `turkey-scepter-1-turkey.3mf`

- The turkey lying on its back (its back is flat). The tab at its bottom edge goes into the base.
- Profile **0.24mm Draft**. **Sparse infill density 10%** (Strength tab). **Supports off**. No brim needed.
- Roughly {h1:.0f} hours, {g1:.0f} g (my rough guess; Bambu Studio shows the real time after **Slice plate**).

## Plate 2: `turkey-scepter-2-shaft.3mf`

- Three pieces standing up: the base with the top of the column (upside down, the base's flat top on the plate),
  the bottom ball and the middle section (as the original file prints them).
- Profile **0.24mm Draft**. **Sparse infill density 10%**. **Supports off**. **Others > Brim type: Outer brim only**
  (the two thin pieces are tall).
- Roughly {h2:.0f} hours, {g2:.0f} g (rough guess again).
- Short on time? Delete the middle section from the plate (saves about {mid['hours']:.1f} hours): the base's screw
  goes straight into the bottom ball, and the scepter is 14 cm shorter (about 46 cm).

## Putting it together

1. Screw the bottom ball onto the middle section, then the middle section onto the screw under the base.
2. Put a little glue (gel super glue or 5-minute epoxy) on the turkey's tab and push it into the slot on top of the
   base. It only fits facing the front. Hold it a minute and let the glue set before anyone waves it around.
   The slot has 0.25 mm of room round the tab (not test-printed): if it is tight, sand the tab a little.
3. Color with acrylic markers; let it dry.
""")


def main() -> None:
    ap = argparse.ArgumentParser(description="Turkey royal scepter mock-up")
    ap.add_argument("scepter", type=Path, help="Fran Gaur's SPQR scepter 3MF (Allen's download)")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "turkey-scepter")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    objs = read_objects(args.scepter)
    sc = scepter(objs)
    lift = BASE_TOP - P["seat"]
    tk = {k: s.translate([0, lift, 0]) for k, s in disjoint(turkey()).items()}
    bs = base()
    for k, s in list(tk.items()) + list(bs.items()):
        assert s.status() == m3d.Error.NoError, k
    b = union(list(tk.values())).bounding_box()
    print(f"turkey {b[3] - b[0]:.0f} wide x {b[4] - b[1]:.0f} tall x {b[5] - b[2]:.0f} deep mm")
    scene = {k: (s.simplify(0.02), "gold") for k, s in sc.items()}
    scene.update({f"turkey-{k}": (s.translate([0, COLUMN_TOP, 0]), k) for k, s in tk.items()})
    scene.update({f"base-{k}": (s.translate([0, COLUMN_TOP, 0]), k) for k, s in bs.items()})
    to_glb(scene, args.out / "mockup.glb")
    print("wrote", args.out / "mockup.glb")
    write_print_files(objs, args.out)


if __name__ == "__main__":
    main()
