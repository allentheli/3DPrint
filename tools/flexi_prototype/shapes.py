"""Ready-made heads as smooth blended shapes on a voxel grid (mm; X forward, Y left, Z up)."""
import numpy as np

VOX = 0.2

def grid(lo, hi):
    axes = [np.arange(a, b + VOX / 2, VOX, dtype=np.float32) for a, b in zip(lo, hi)]
    X, Y, Z = np.meshgrid(*axes, indexing="ij")
    return axes, X, Y, Z

def ellipsoid(X, Y, Z, c, r):
    """Approximate signed distance (mm, negative inside) to an ellipsoid."""
    p = np.stack([(X - c[0]) / r[0], (Y - c[1]) / r[1], (Z - c[2]) / r[2]])
    k0 = np.sqrt((p ** 2).sum(0))
    p2 = np.stack([(X - c[0]) / r[0] ** 2, (Y - c[1]) / r[1] ** 2, (Z - c[2]) / r[2] ** 2])
    k1 = np.sqrt((p2 ** 2).sum(0)) + 1e-9
    return k0 * (k0 - 1.0) / k1

def cone(X, Y, Z, base, apex, r_base, r_apex=0.4, flat=1.0):
    """Rounded cone from base to apex (radius r_base to r_apex); `flat` squashes it front-back."""
    b, a = np.array(base, np.float32), np.array(apex, np.float32)
    ax = a - b; L = np.linalg.norm(ax); ax /= L
    px, py, pz = X - b[0], Y - b[1], Z - b[2]
    t = np.clip(px * ax[0] + py * ax[1] + pz * ax[2], 0, L)
    qx, qy, qz = px - t * ax[0], py - t * ax[1], pz - t * ax[2]
    qx = qx / flat                                     # squash along X (ears are thin front to back)
    d = np.sqrt(qx ** 2 + qy ** 2 + qz ** 2)
    r = r_base + (r_apex - r_base) * t / L
    return d - r

def smooth_union(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)

def cat_head():
    axes, X, Y, Z = grid((-12, -14, 0), (14, 14, 27))
    d = ellipsoid(X, Y, Z, (0, 0, 10.5), (9.0, 10.5, 9.5))                       # skull
    d = smooth_union(d, ellipsoid(X, Y, Z, (6.0, 0, 7.5), (5.0, 6.8, 4.6)), 2.0)  # muzzle and cheeks
    for s in (1, -1):                                                              # wide flat triangle ears
        d = smooth_union(d, cone(X, Y, Z, (-0.8, s * 5.8, 15.5), (-1.4, s * 8.4, 23.5), 4.6, 0.9, flat=0.4), 1.8)
    d = np.maximum(d, 1.6 - Z)                                                     # flat bottom
    return axes, d, "front"

def fish_head():
    axes, X, Y, Z = grid((-10, -10, 0), (20, 10, 20))
    d = ellipsoid(X, Y, Z, (3.0, 0, 9.0), (13.0, 6.8, 8.5))                       # body of the head, narrower
    d = smooth_union(d, ellipsoid(X, Y, Z, (12.0, 0, 6.8), (5.5, 4.2, 3.8)), 2.5) # lower snout
    d = np.maximum(d, 1.6 - Z)
    return axes, d, "side"
