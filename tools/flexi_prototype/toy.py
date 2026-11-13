"""First full flexi: cat head (ready-made, kid face painted) + chest, torso, hips + tail,
joined by the standard ring joint. Prototype."""
import sys, time
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage
from skimage import measure
from shapely import affinity
from shapely.geometry import Polygon
sys.path.insert(0, "/home/user/3DPrint"); sys.path.insert(0, str(Path(__file__).parent))
import manifold3d as m3d
from charm_maker.config import load_config
from charm_maker.inks import separate_colors
from charm_maker.shape import fix_design
from charm_maker.geom import extrude
from charm_maker.fittest import flexi_joint
import shapes
from shapes import ellipsoid, cone, smooth_union
cfg = load_config("/home/user/3DPrint/config.yaml")
HERE = Path(sys.argv[1])
VOX, SKIN = shapes.VOX, 0.8
GAP = cfg["fit"]["flexi_joint_gap"]["value"]
J = cfg["fit_test"]["flexi_joint"]
ZM = 8.6                     # joint height (middle of the body)
ZCUT = 2.4                   # flat bottom (a wider flat belly to stand and print on)
SPACING = 15.5
X1 = -10.5
XS = [X1, X1 - SPACING, X1 - 2 * SPACING, X1 - 3 * SPACING]    # head|chest, chest|torso, torso|hips, hips|tail
t0 = time.time()

def solid_from(axes, D):
    vol = np.pad(-D, 2, constant_values=-1.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.0)
    v = (v - 2) * VOX + np.array([a[0] for a in axes])
    return m3d.Manifold(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))

# --- Head: the ready-made cat, with a neck to hold the first joint -------------------------
axes_h, X, Y, Z = shapes.grid((-19, -14, 0), (14, 14, 27))
d = ellipsoid(X, Y, Z, (0, 0, 10.5), (9.0, 10.5, 9.5))
d = smooth_union(d, ellipsoid(X, Y, Z, (6.0, 0, 7.5), (5.0, 6.8, 4.6)), 2.0)
for s in (1, -1):
    d = smooth_union(d, cone(X, Y, Z, (-0.8, s * 5.8, 15.5), (-1.4, s * 8.4, 23.5), 4.6, 0.9, flat=0.4), 1.8)
d = smooth_union(d, ellipsoid(X, Y, Z, (X1 + 0.5, 0, ZM), (8.0, 8.2, 7.4)), 3.0)          # neck
D_head = np.maximum(d, ZCUT - Z)
head = solid_from(axes_h, D_head)

# --- Body: chest, torso, hips with paws, and a tail ------------------------------------------
axes_b, X, Y, Z = shapes.grid((XS[3] - 26, -20, 0), (X1 + 2, 20, 26))
zc = ZM
d = ellipsoid(X, Y, Z, (XS[0] - 8.0, 0, zc), (9.5, 8.6, 8.0))                               # chest
d = smooth_union(d, ellipsoid(X, Y, Z, (XS[1] - 7.75, 0, zc), (9.0, 8.3, 7.8)), 3.0)          # torso
d = smooth_union(d, ellipsoid(X, Y, Z, (XS[2] - 7.75, 0, zc), (9.5, 8.7, 8.0)), 3.0)          # hips
d = smooth_union(d, ellipsoid(X, Y, Z, (XS[3] - 6.5, 0, zc), (7.0, 7.0, 6.5)), 3.0)           # tail root
# Legs like the kitten's: chunky, each pair wholly on one piece (front pair on the chest, back pair
# on the hips), sticking out sideways and resting on the bed, clear of where the neighbors swing.
def capsule(a, b, r):
    return cone(X, Y, Z, a, b, r, r, flat=1.0)
LEG_R = 3.1
def leg_shape(s, back):
    if back:                                     # haunch, lower leg, paw
        xh = XS[2] - 11.5
        g = ellipsoid(X, Y, Z, (xh, s * 7.2, 7.0), (3.8, 3.6, 4.8))
        g = smooth_union(g, capsule((xh, s * 8.0, 5.0), (xh + 0.3, s * 13.2, 4.6), LEG_R), 1.2)
        g = smooth_union(g, ellipsoid(X, Y, Z, (xh + 0.3, s * 14.6, 4.6), (3.9, 3.7, 3.0)), 1.0)
    else:                                        # shoulder, front leg, paw
        xf = XS[0] - 9.9
        g = capsule((xf - 2.5, s * 5.0, 7.0), (xf - 0.5, s * 13.2, 4.6), LEG_R)
        g = smooth_union(g, ellipsoid(X, Y, Z, (xf - 0.5, s * 14.6, 4.6), (3.9, 3.7, 3.0)), 1.0)
    return g
# tail: a tapering tube lying on the bed, curving to one side (no supports needed)
for k in range(9):
    r = 3.8 - 0.2 * k
    p = (XS[3] - 10 - 2.1 * k, 0.09 * k * k, ZCUT + r * 0.75)
    d = smooth_union(d, ellipsoid(X, Y, Z, p, (r, r, r)), 1.5)
# Each pair of legs is built onto its own piece only, so a leg can never spill onto a neighbor.
legs, bodies = {}, {"plain": solid_from(axes_b, np.maximum(d, ZCUT - Z))}
for back in (False, True):
    key = "back" if back else "front"
    legs[key] = np.minimum(leg_shape(1, back), leg_shape(-1, back))
    bodies[key] = solid_from(axes_b, np.maximum(smooth_union(d, legs[key], 2.0), ZCUT - Z))
body = bodies["plain"]
print("shapes built %.0f s" % (time.time() - t0), "head", np.round(head.bounding_box(), 1), "body", np.round(body.bounding_box(), 1))

# --- Cut into pieces and join them --------------------------------------------------------
lobe_r = J["pin_radius"] + GAP + J["ring_width"] + GAP + J["cup_wall"]
SW = J["swing"] + 5 + 5                     # the front piece's sides clear the back piece's swing
BIG = 200
def cyl(x, r):
    return m3d.Manifold.cylinder(60, r, r, 96).translate([x, 0, -10])
def wedge_front(x, half):
    pts = [(x, 0)] + [(x + BIG * np.cos(np.radians(a)), BIG * np.sin(np.radians(a))) for a in np.linspace(-half, half, 31)]
    return extrude(Polygon(pts), 60, -10)
def behind(x):
    return m3d.Manifold.cube([BIG, 2 * BIG, 60]).translate([x - BIG, -BIG, -10])
# Like the shark: the front piece ends in a round end as wide as the body, the back piece starts
# with a matching cup, so turning never bumps (round end radius >= half-width / cos(swing / 2)).
HALF_W = 9.0
RF = max(lobe_r + 1.5, HALF_W / np.cos(np.radians((J["swing"] + 10) / 2)) - GAP + 0.2)
print("round end radius %.2f mm" % RF)
def keep_front(x):
    return cyl(x, RF) + m3d.Manifold.cube([BIG, 2 * BIG, 60]).translate([x, -BIG, -10])
def keep_back(x):
    return behind(x) - cyl(x, RF + GAP)
joints = []
for x in XS:
    jt = flexi_joint(cfg, GAP, 0.0, 0.0, end_r=RF)
    place = lambda m: m.rotate([0, 0, 180]).translate([x, 0, ZM - J["thickness"] / 2])   # noqa: E731
    joints.append((place(jt["ring"]), place(jt["void"])))
pieces = {}
pieces["head"] = (head ^ keep_front(XS[0])) - joints[0][1]
names = ["chest", "torso", "hips"]
source = {"chest": bodies["front"], "torso": bodies["plain"], "hips": bodies["back"]}
for i, n in enumerate(names):
    p = source[n] ^ keep_back(XS[i]) ^ keep_front(XS[i + 1])
    pieces[n] = (p + joints[i][0]) - joints[i + 1][1]
pieces["tail"] = (body ^ keep_back(XS[3])) + joints[3][0]
for n, p in pieces.items():
    print(n, "volume %.0f mm3" % p.volume(), "parts", len(p.decompose()))
for key, owner in (("front", "chest"), ("back", "hips")):
    added = bodies[key] - bodies["plain"]                 # what the legs add to the body
    lost = added - pieces[owner]
    print(f"{key} legs add {added.volume():.0f} mm3, all on the {owner} except {lost.volume():.2f} mm3 (cut off at its edge)", np.round(lost.bounding_box(), 1))
names_all = list(pieces)
for i, a in enumerate(names_all):
    for b in names_all[i + 1:]:
        v = (pieces[a] ^ pieces[b]).volume()
        if v > 1e-3:
            print("OVERLAP", a, b, round(v, 3))
import pickle
for n, p in pieces.items():
    m = p.to_mesh()
    np.savez(HERE / f"toy-{n}.npz", v=np.asarray(m.vert_properties)[:, :3], f=np.asarray(m.tri_verts))
print("done %.0f s" % (time.time() - t0))

# --- Paint the kid's face on the head (seen from the front) ------------------------------
from charm_maker.preview import render_shaded
from charm_maker.bambu3mf import write_bambu_3mf
from PIL import Image
inside = D_head < 0
depth = ndimage.distance_transform_edt(inside).astype(np.float32) * VOX
inner = solid_from(axes_h, -(np.where(inside, ndimage.gaussian_filter(depth, 0.8), -1.0) - SKIN))
skin = head - inner
g = np.gradient(ndimage.gaussian_filter(inside.astype(np.float32), 2.0))
nx, ny, nz = -g[0], -g[1], -g[2]
nrm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2) + 1e-9
idx = np.arange(inside.shape[0]).reshape(-1, 1, 1)
first = np.where(inside, idx, -1).max(axis=0, keepdims=True)
seen = inside & (idx >= first - (SKIN + 1.2) / VOX)
zone = ndimage.binary_dilation((nx / nrm > 0.35) & seen & (depth < SKIN + 1.0), iterations=2)
zone_solid = solid_from(axes_h, -(ndimage.gaussian_filter(zone.astype(np.float32), 1.0) * 2 - 1))
img = cv2.imread(str(HERE / "cat-face.png"))
inks = separate_colors(cfg, img, px_per_mm=20.0)
design = fix_design(cfg, inks.layers, 20.0, border_on=False, name="face", product="magnet_figure")
ax_c, _, _ = shapes.cat_head()[0], None, None
du, dv = float(ax_c[1][0]), float(ax_c[2][-1]) - img.shape[0] / 20.0
prism = lambda g: extrude(g, 60, -30).transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
head_piece = pieces["head"]
paint, colors = {}, {}
taken = m3d.Manifold()
for ink in design.inks:
    part = (skin ^ zone_solid ^ prism(affinity.translate(ink.geometry, du, dv)) ^ head_piece) - taken
    if part.volume() > 0.05:
        paint[f"head {ink.name}"] = part; colors[f"head {ink.name}"] = ink.rgb; taken = taken + part
pieces["head"] = head_piece - taken
BODY_RGB, HEAD_RGB = (250, 165, 80), (250, 165, 80)
colors.update({n: BODY_RGB for n in ["chest", "torso", "hips", "tail"]}); colors["head"] = HEAD_RGB
allparts = {**pieces, **paint}
print({k: round(v.volume(), 1) for k, v in allparts.items()})

out = Path("/home/user/3DPrint/output/flexi-concept/cat-flexi"); out.mkdir(parents=True, exist_ok=True)
bb = np.array(m3d.Manifold.batch_boolean(list(allparts.values()), m3d.OpType.Add).bounding_box())
shift = [-(bb[0] + bb[3]) / 2 + 128, -(bb[1] + bb[4]) / 2 + 128, -bb[2]]
slot = {"black": 2, "pink": 3}
parts3mf = [(name, s.translate(shift), slot.get(name.split()[-1], 1) if name.startswith("head ") else 1, colors[name])
            for name, s in allparts.items()]
write_bambu_3mf([("flexi-cat", parts3mf)], out / "flexi-cat.3mf")
render_shaded(allparts, out / "flexi-cat-a.png", view=(25, -55), px_per_mm=8, labels=False, colors=colors)
render_shaded(allparts, out / "flexi-cat-side.png", view=(5, 0), px_per_mm=8, labels=False, colors=colors)
# A wiggled pose: each joint turned, the joints behind it carried along.
order = ["head", "chest", "torso", "hips", "tail"]
angles = [22, -28, 28, -22]
axes2d = [np.array([x, 0.0]) for x in XS]
posed = dict(allparts)
for k in range(4):
    cx, cy = axes2d[k]
    a = np.radians(angles[k]); R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    for n in [n for n in posed if n.split()[0] in order[k + 1:]]:
        posed[n] = posed[n].translate([-cx, -cy, 0]).rotate([0, 0, angles[k]]).translate([cx, cy, 0])
    for j in range(k + 1, 4):
        axes2d[j] = np.array([cx, cy]) + R @ (axes2d[j] - np.array([cx, cy]))
render_shaded(posed, out / "flexi-cat-wiggle-top.png", view=(80, -90), px_per_mm=8, labels=False, colors=colors)
render_shaded(posed, out / "flexi-cat-wiggle.png", view=(30, -60), px_per_mm=8, labels=False, colors=colors)
print("written", sorted(p.name for p in out.iterdir()))
