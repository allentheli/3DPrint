"""Curl test: turn every joint through its range in many combinations and make sure no two
pieces that are not neighbors ever touch (legs against legs, tail against hips, ...)."""
import sys, itertools
from pathlib import Path
import numpy as np
import manifold3d as m3d
HERE = Path(sys.argv[1]); PREFIX = sys.argv[2]
order = ["head", "chest", "torso", "hips", "tail"]
def load(n):
    z = np.load(HERE / f"{PREFIX}-{n}.npz")
    return m3d.Manifold(m3d.Mesh(vert_properties=z["v"].astype(np.float32), tri_verts=z["f"].astype(np.uint32)))
P = [load(n) for n in order]
XS = [-10.5 - k * 15.5 for k in range(4)]
steps = (-38, -19, 0, 19, 38)
worst = 0.0; bad = []
for angles in itertools.product(steps, repeat=4):
    posed = list(P); axes = [np.array([x, 0.0]) for x in XS]
    for k, a in enumerate(angles):
        cx, cy = axes[k]; r = np.radians(a); R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
        for j in range(k + 1, 5):
            posed[j] = posed[j].translate([-cx, -cy, 0]).rotate([0, 0, a]).translate([cx, cy, 0])
        for j in range(k + 1, 4):
            axes[j] = np.array([cx, cy]) + R @ (axes[j] - np.array([cx, cy]))
    for i in range(5):
        for j in range(i + 2, 5):
            v = (posed[i] ^ posed[j]).volume()
            if v > 1e-3:
                bad.append((angles, order[i], order[j], round(v, 2)))
print(len(steps) ** 4, "poses checked;", "no bumps" if not bad else f"{len(bad)} bumps, e.g. {bad[:5]}")
