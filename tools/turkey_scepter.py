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
- a little gold crown sitting crooked on its head, and orange feet gripping a gold perch on top of the SPQR plaque.

The turkey is a relief with a flat back (like a plaque), so it can print back-down.

    python -I tools/turkey_scepter.py <SPQR scepter .3mf> [--out output/turkey-scepter]
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
PLAQUE_TOP = STACK["SPQR_upper.stl"] + 82.3
PLAQUE_HALF_W = 61.5


def scepter(objs: dict[str, M]) -> dict[str, M]:
    out = {k.split(".")[0]: objs[k].translate([0, dy, 0]) for k, dy in STACK.items()}
    # The thunderbolts: each piece's joint (its end with the little hooks) goes into the slot in the side of the
    # plaque, bolts pointing outward. Arrows_LH has its joint at -x, so it goes on the right (+x) side.
    plaque_mid = PLAQUE_TOP - 20.0
    for k, side in (("Arrows_LH.stl", 1), ("Arrows_RH.stl", -1)):
        a = objs[k]
        b = a.bounding_box()
        joint_x = b[0] if side > 0 else b[3]
        ys = _joint_y(a, joint_x, side)
        out[k.split(".")[0]] = a.translate([side * (PLAQUE_HALF_W - 3.0) - joint_x, plaque_mid - ys, 0])
    return out


def _joint_y(a: M, x: float, side: int) -> float:
    """Height of the arrow piece's joint: the middle of its slice 1.5 mm in from its joint end."""
    s = a.rotate([0, 90, 0]).slice(-(x + side * 1.5))      # cut across x
    b = s.bounds()
    return (b[1] + b[3]) / 2


# ---------------------------------------------------------------- shapes

def ball(c, r) -> M:
    r = np.broadcast_to(np.asarray(r, float), (3,))
    return M.sphere(1.0, SEG).scale(list(r)).translate(list(c))


def ell(c, r, rot_z: float = 0.0) -> M:
    r = np.broadcast_to(np.asarray(r, float), (3,))
    return M.sphere(1.0, SEG).scale(list(r)).rotate([0, 0, rot_z]).translate(list(c))


def front_half(s: M, zb: float = ZB) -> M:
    return s ^ M.cube([2000, 2000, 1000]).translate([-1000, -1000, zb])


def chain(points, radii) -> M:
    """Spheres hulled pairwise along a path: a tapered, bent tube."""
    balls = [ball(p, r) for p, r in zip(points, radii)]
    return M.batch_boolean([M.batch_hull([a, b]) for a, b in zip(balls, balls[1:])], m3d.OpType.Add)


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
    perch=(27.0, 9.0, 11.0),      # gold perch on the plaque: half width, height, half depth
    fan_c=(0.0, 80.0), fan_r=112.0, fan_n=15, fan_span=(-12.0, 192.0), fan_tip=14.5, fan_thick=4.2,
    row2_r=80.0, row2_tip=12.5, row2_thick=11.0,
    body=(0.0, 70.0, 39.0, 46.0, 31.0),          # center x, y; radii x, y, z (dome on the back plane)
    head=(3.0, 146.0), head_r=(15.0, 16.0, 13.0),
)


def turkey(p: dict = P) -> dict[str, M]:
    parts: dict[str, list[M]] = {k: [] for k in COLORS}
    cx, cy = p["fan_c"]
    C = np.array([cx, cy])

    # Gold perch (the eagle stood on a block too), rounded.
    hw, ph, hd = p["perch"]
    perch = M.batch_hull([ball([sx * (hw - 3), y, sz * (hd - 3)], 3.0)
                          for sx in (-1, 1) for sz in (-1, 1) for y in (3.0, ph - 3.0)])
    parts["gold"].append(perch)

    # Tail fan, back row: long banded feathers with a gold band, buff tips and a gold pearl on each.
    R, n = p["fan_r"], p["fan_n"]
    angs = np.linspace(*p["fan_span"], n)
    back = []
    for a in angs:
        u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
        b0, b1 = C + 28 * u, C + (R - p["fan_tip"]) * u
        f = M.batch_hull([ball([*b0, ZB], [6, 6, 3.5]), ball([*b1, ZB], [p["fan_tip"], p["fan_tip"], p["fan_thick"]])])
        back.append(front_half(f))
        parts["gold"].append(ball([*(C + (R + 1.5) * u), ZB + 3.0], 4.0))
    back = union(back)
    bands = [("bronze", 0, 0.52), ("tan", 0.52, 0.59), ("bronze", 0.59, 0.78), ("gold", 0.78, 0.87), ("tan", 0.87, 2)]
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
        w = front_half(ell([side * 37, by - 14, ZB], [16, 38, 24], rot_z=side * 16))
        w2 = front_half(ell([side * 37, by - 14, ZB], [16.8, 38.8, 24.8], rot_z=side * 16))
        bars = union([w2 ^ M.cube([200, 3.2, 100]).translate([-100, by - 40 + 8 * k, -50]) for k in range(4)])
        parts["bronze"].append(w)
        parts["tan"].append(bars)

    # Neck and head (bare red skin), wattle, snood, beak.
    hx, hy = p["head"]
    parts["red"].append(chain([(0, by + 30, 0), (1.5, hy - 26, 3), (hx, hy - 8, 3)], [11, 9, 9]))
    parts["red"].append(ell([hx, hy, 3], p["head_r"]))
    parts["darkred"].append(ell([hx - 1, hy - 23, 10], [6.5, 9, 6]))
    parts["orange"].append(M.batch_hull([ball([hx, hy - 4, 14], 5.6), ball([hx, hy - 12, 25.5], 1.3)]))
    parts["darkred"].append(chain([(hx, hy + 2, 14.5), (hx + 2.5, hy - 3, 22.5), (hx + 5, hy - 11, 26.5),
                                   (hx + 6.5, hy - 20, 25), (hx + 7, hy - 26, 22)], [2.7, 2.6, 2.4, 2.2, 2.8]))

    # Googly eyes, looking two different ways.
    eyes = [((hx - 10.6, hy + 7, 12.0), 10.5, (-0.62, 0.45, 0.64)),      # left: up and out
            ((hx + 11.0, hy + 8.5, 12.0), 11.2, (0.45, -0.55, 0.70))]     # right: down and out
    for c, r, d in eyes:
        d = np.asarray(d) / np.linalg.norm(d)
        parts["white"].append(ball(c, r))
        parts["black"].append(ball(np.asarray(c) + (r - 2.3) * d, 4.4))

    # A little crown, on crooked.
    place = lambda s: s.rotate([0, 0, -17]).translate([hx + 4, hy + 14, 1])
    parts["gold"].append(place(crown()))
    parts["red"].append(place(ball([0, 4.0, 12.0], 2.2)))

    # Legs and feet gripping the perch's front edge.
    top = ph
    for side in (-1, 1):
        x0 = side * 14
        parts["orange"].append(chain([(side * 12, by - ry + 6, -2), (x0, top + 4, 2)], [4.2, 3.4]))
        for dx in (-0.4, 0.0, 0.4):
            x1 = x0 + side * 2 + dx * 14
            parts["orange"].append(chain([(x0, top + 3, 2), (x1, top + 2.6, hd - 1), (x1 + dx * 2, top - 3, hd + 1.8)],
                                         [2.8, 2.5, 2.1]))
            parts["dark"].append(chain([(x1 + dx * 2, top - 3, hd + 1.8), (x1 + dx * 2.4, top - 7.5, hd + 0.8)], [1.6, 0.6]))
    return {k: union(v) for k, v in parts.items() if v}


def crown() -> M:
    """A small crown standing on y: a band with five points, each with a pearl."""
    r, t, h = 12.0, 1.6, 8.0
    band = M.cylinder(h, r, r, SEG) - M.cylinder(h + 2, r - t, r - t, SEG).translate([0, 0, -1])
    pts = []
    for k in range(5):
        a = math.radians(90 + 72 * k)
        c = (r - t / 2) * np.array([math.cos(a), math.sin(a)])
        spike = M.cylinder(8.5, 3.2, 0.5, 16).translate([c[0], c[1], h - 0.5])
        pts += [spike, ball([*(c * 1.0), h + 8.3], 1.9)]
    s = union([band] + pts)
    return s.rotate([-90, 0, 0])      # z (up) -> y


def disjoint(parts: dict[str, M]) -> dict[str, M]:
    """Make the colored parts not overlap: what is in front (later in this list) wins."""
    order = ["gold", "bronze", "chestnut", "tan", "dark", "red", "darkred", "orange", "white", "black"]
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Turkey royal scepter mock-up")
    ap.add_argument("scepter", type=Path, help="Fran Gaur's SPQR scepter 3MF (Allen's download)")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "turkey-scepter")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    objs = read_objects(args.scepter)
    sc = scepter(objs)
    tk = disjoint(turkey())
    for k, s in tk.items():
        assert s.status() == m3d.Error.NoError, k
    b = union(list(tk.values())).bounding_box()
    print(f"turkey {b[3] - b[0]:.0f} wide x {b[4] - b[1]:.0f} tall x {b[5] - b[2]:.0f} deep mm")
    scene = {k: (s.simplify(0.02), "gold") for k, s in sc.items()}
    scene.update({f"turkey-{k}": (s.translate([0, PLAQUE_TOP, 0]), k) for k, s in tk.items()})
    to_glb(scene, args.out / "mockup.glb")
    print("wrote", args.out / "mockup.glb")


if __name__ == "__main__":
    main()
