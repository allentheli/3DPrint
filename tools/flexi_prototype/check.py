import sys
from pathlib import Path
import numpy as np
import manifold3d as m3d
HERE = Path(sys.argv[1])
def load(n):
    z = np.load(HERE / f"toy-{n}.npz")
    return m3d.Manifold(m3d.Mesh(vert_properties=z["v"].astype(np.float32), tri_verts=z["f"].astype(np.uint32)))
order = ["head", "chest", "torso", "hips", "tail"]
P = {n: load(n) for n in order}
X1, SP = -10.5, 15.5
XS = [X1 - k * SP for k in range(4)]
for k in range(4):
    F, B, x = P[order[k]], P[order[k + 1]], XS[k]
    turn = lambda m, a: m.translate([-x, 0, 0]).rotate([0, 0, a]).translate([x, 0, 0])
    free = max(a for a in range(0, 61) if (turn(B, a) ^ F).volume() < 1e-3 and (turn(B, -a) ^ F).volume() < 1e-3)
    pull = max(d for d in np.arange(0, 3.01, 0.05) if (B.translate([-d, 0, 0]) ^ F).volume() < 1e-3)
    lift = max(d for d in np.arange(0, 3.01, 0.05) if (B.translate([0, 0, d]) ^ F).volume() < 1e-3)
    print(f"{order[k]}-{order[k+1]}: swings +-{free} deg, pulls out at most {pull:.2f} mm, lifts at most {lift:.2f} mm")
