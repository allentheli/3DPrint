"""Write 3MF and STL files from named solids."""

from __future__ import annotations

from pathlib import Path

import manifold3d as m3d
import trimesh

from .geom import to_trimesh


def write_plate(solids: dict[str, m3d.Manifold], out_dir: Path, stem: str) -> dict[str, Path]:
    """Write `<stem>.3mf` holding every solid as a named object, plus one STL per solid
    in `<stem>_stl/`. Returns the written paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    meshes: dict[str, trimesh.Trimesh] = {}
    for name, solid in solids.items():
        mesh = to_trimesh(solid)
        mesh.metadata["name"] = name
        meshes[name] = mesh
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    paths: dict[str, Path] = {}
    three_mf = out_dir / f"{stem}.3mf"
    scene.export(three_mf)
    paths["3mf"] = three_mf
    stl_dir = out_dir / f"{stem}_stl"
    stl_dir.mkdir(exist_ok=True)
    for name, mesh in meshes.items():
        p = stl_dir / f"{name}.stl"
        mesh.export(p)
        paths[f"stl:{name}"] = p
    merged = trimesh.util.concatenate(list(meshes.values()))
    all_stl = out_dir / f"{stem}_all.stl"
    merged.export(all_stl)
    paths["stl:all"] = all_stl
    return paths
