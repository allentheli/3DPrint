import sys
from pathlib import Path
import numpy as np
from skimage import measure
from PIL import Image
sys.path.insert(0, "/home/user/3DPrint"); sys.path.insert(0, str(Path(__file__).parent))
import manifold3d as m3d
from charm_maker.preview import render_shaded
import shapes
HERE = Path(sys.argv[1])
ims = []
for which in ("cat", "fish"):
    axes, D, view = getattr(shapes, f"{which}_head")()
    vol = np.pad(-D, 2, constant_values=-1.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.0)
    v = (v - 2) * shapes.VOX + np.array([a[0] for a in axes])
    head = m3d.Manifold(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))
    for vw, t in (((15, -50), "a"), ((5, 0), "b"), ((5, 90), "c")):
        p = HERE / f"bare-{which}-{t}.png"
        render_shaded({"h": head}, p, view=vw, px_per_mm=10, labels=False, colors={"h": (235, 180, 120)})
        ims.append(Image.open(p))
h = max(i.height for i in ims)
o = Image.new("RGB", (sum(i.width for i in ims) + 20 * len(ims), h), "white"); x = 0
for i in ims: o.paste(i, (x, 0)); x += i.width + 20
o.save(HERE / "bare.png"); print(o.size)
