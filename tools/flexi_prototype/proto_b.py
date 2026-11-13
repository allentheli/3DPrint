import sys
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage
from skimage import measure
from PIL import Image, ImageDraw
sys.path.insert(0, "/home/user/3DPrint"); sys.path.insert(0, str(Path(__file__).parent))
import manifold3d as m3d
from charm_maker.geom import extrude
from charm_maker.preview import render_shaded
import shapes
HERE = Path(sys.argv[1]); which = sys.argv[2]
axes, D, view = getattr(shapes, f"{which}_head")()
VOX = shapes.VOX
def to_solid(field):     # field: negative inside
    vol = np.pad(-field, 2, constant_values=-1.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.0)
    v = (v - 2) * VOX + np.array([a[0] for a in axes])
    return m3d.Manifold(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))
head = to_solid(D)
bb = np.array(head.bounding_box()); print(which, "size", np.round(bb[3:] - bb[:3], 1), "volume %.0f" % head.volume())
# The guide: the head's outline seen from the face's direction.
inside = D < 0
if view == "front":
    sil = inside.any(axis=0)          # [y, z]
    u_axis, v_axis = axes[1], axes[2]
else:
    sil = inside.any(axis=1)          # [x, z]
    u_axis, v_axis = axes[0], axes[2]
np.save(HERE / f"{which}-sil.npy", sil)
img = Image.fromarray(((~sil.T[::-1]) * 255).astype(np.uint8)).convert("RGB")
if view == "front":
    img = img.transpose(Image.FLIP_LEFT_RIGHT)   # seen from the front, the head's left is on the right
img.save(HERE / f"{which}-guide.png")
print("guide px", img.size, "u", u_axis[0], u_axis[-1], "v", v_axis[0], v_axis[-1])
