"""Paint a kid's face drawing onto a ready-made head: from the front (cat) or both sides (fish)."""
import sys
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage
from skimage import measure
from shapely import affinity
from PIL import Image
sys.path.insert(0, "/home/user/3DPrint"); sys.path.insert(0, str(Path(__file__).parent))
import manifold3d as m3d
from charm_maker.config import load_config
from charm_maker.inks import separate_colors
from charm_maker.shape import fix_design
from charm_maker.geom import extrude
from charm_maker.preview import render_shaded
import shapes
cfg = load_config("/home/user/3DPrint/config.yaml")
HERE = Path(sys.argv[1]); which = sys.argv[2]; base_rgb = tuple(int(v) for v in sys.argv[3].split(","))
PPM, VOX, SKIN = 20.0, shapes.VOX, 0.8
axes, D, view = getattr(shapes, f"{which}_head")()
inside = D < 0
def to_solid(field):     # field > 0 inside
    vol = np.pad(field, 2, constant_values=-1.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.0)
    v = (v - 2) * VOX + np.array([a[0] for a in axes])
    return m3d.Manifold(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))
head = to_solid(-D)
depth = ndimage.distance_transform_edt(inside).astype(np.float32) * VOX
skin = head - to_solid(np.where(inside, ndimage.gaussian_filter(depth, 0.8), -1.0) - SKIN)
g = np.gradient(ndimage.gaussian_filter(inside.astype(np.float32), 2.0))
nx, ny, nz = -g[0], -g[1], -g[2]
norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2) + 1e-9
facing = (nx / norm > 0.35) if view == "front" else (np.abs(ny) / norm > 0.35)
# Only the surface you see from that direction: the first one the paint hits.
def seen_from(axis, sign):
    idx = np.arange(inside.shape[axis]).reshape([-1 if a == axis else 1 for a in range(3)])
    if sign > 0:
        first = np.where(inside, idx, -1).max(axis=axis, keepdims=True)
        return inside & (idx >= first - (SKIN + 1.2) / VOX)
    first = np.where(inside, idx, 10 ** 6).min(axis=axis, keepdims=True)
    return inside & (idx <= first + (SKIN + 1.2) / VOX)
seen = seen_from(0, +1) if view == "front" else (seen_from(1, +1) | seen_from(1, -1))
zone = ndimage.binary_dilation(facing & seen & (depth < SKIN + 1.0), iterations=2)
zone_solid = to_solid(ndimage.gaussian_filter(zone.astype(np.float32), 1.0) * 2 - 1)
# Read the drawing like any card drawing.
img = cv2.imread(str(HERE / f"{which}-face.png"))
inks = separate_colors(cfg, img, px_per_mm=PPM)
design = fix_design(cfg, inks.layers, PPM, border_on=False, name=which, product="magnet_figure")
Hpx = img.shape[0]
u_axis = axes[1] if view == "front" else axes[0]
du, dv = float(u_axis[0]), float(axes[2][-1]) - Hpx / PPM
if view == "front":
    to_prism = lambda g: extrude(g, 60, -30).transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
else:
    to_prism = lambda g: extrude(g, 60, -30).transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]])
parts, colors, taken = {}, {}, m3d.Manifold()
for ink in design.inks:
    g = affinity.translate(ink.geometry, du, dv)
    part = (skin ^ zone_solid ^ to_prism(g)) - taken
    if part.volume() > 0.05:
        parts[ink.name] = part; colors[ink.name] = ink.rgb; taken = taken + part
        print(which, ink.name, "volume %.1f mm3" % part.volume())
parts = {"head": head - taken, **parts}; colors["head"] = base_rgb
views = (((15, -50), "a"), ((5, 0), "b"), ((5, 90), "c")) if view == "front" else (((20, -30), "a"), ((5, 0), "b"), ((15, 60), "c"))
ims = []
for vw, t in views:
    p = HERE / f"{which}-painted-{t}.png"
    render_shaded(parts, p, view=vw, px_per_mm=12, labels=False, colors=colors)
    ims.append(Image.open(p))
h = max(i.height for i in ims)
o = Image.new("RGB", (sum(i.width for i in ims) + 20 * len(ims), h), "white"); x = 0
for i in ims: o.paste(i, (x, 0)); x += i.width + 20
o.save(HERE / f"{which}-painted.png")
import pickle
