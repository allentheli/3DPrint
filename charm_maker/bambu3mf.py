"""Write a 3MF the way Bambu Studio does: one object per design, one component
(part) per color, and Metadata/model_settings.config naming the filament slot
of every part. Opening it in Bambu Studio should give one object per charm with
its colors already assigned. If Bambu Studio ignores the assignments, the plain
3MF next to it still carries every part as a named object."""

from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import manifold3d as m3d
import numpy as np

from .geom import to_trimesh

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_P = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS_BBS = "http://schemas.bambulab.com/package/2021"

IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"
IDENTITY4 = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


def _uuid() -> str:
    return str(uuid.uuid4())


def _mesh_xml(obj_id: int, solid: m3d.Manifold) -> str:
    mesh = to_trimesh(solid)
    v = np.asarray(mesh.vertices, dtype=np.float64)
    f = np.asarray(mesh.faces, dtype=np.int64)
    verts = "".join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in v)
    tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in f)
    return (f'<object id="{obj_id}" p:UUID="{_uuid()}" type="model"><mesh>'
            f"<vertices>{verts}</vertices><triangles>{tris}</triangles></mesh></object>")


def write_bambu_3mf(objects: list[tuple[str, list[tuple[str, m3d.Manifold, int, tuple[int, int, int]]]]],
                    path: Path, slot_filaments: dict | None = None) -> Path:
    """objects: [(object_name, [(part_name, solid, extruder_slot, rgb), ...]), ...]"""
    path = Path(path)
    next_id = 1
    sub_models: dict[str, str] = {}      # zip path -> xml
    main_objects = []
    build_items = []
    config_objects = []
    rels = []
    for oi, (obj_name, parts) in enumerate(objects, start=1):
        part_ids = []
        part_xml = []
        for part_name, solid, slot, rgb in parts:
            pid = next_id
            next_id += 1
            part_ids.append((pid, part_name, slot, solid))
            part_xml.append(_mesh_xml(pid, solid))
        obj_id = next_id
        next_id += 1
        sub_path = f"3D/Objects/object_{oi}.model"
        sub_models[sub_path] = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{NS}" xmlns:p="{NS_P}" xmlns:BambuStudio="{NS_BBS}">'
            f'<metadata name="BambuStudio:3mfVersion">1</metadata><resources>{"".join(part_xml)}</resources><build/></model>'
        )
        rels.append(f'<Relationship Target="/{sub_path}" Id="rel-{oi}" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        comps = "".join(
            f'<component p:path="/{sub_path}" objectid="{pid}" p:UUID="{_uuid()}" transform="{IDENTITY}"/>'
            for pid, *_ in part_ids
        )
        main_objects.append(f'<object id="{obj_id}" p:UUID="{_uuid()}" type="model"><components>{comps}</components></object>')
        build_items.append(f'<item objectid="{obj_id}" p:UUID="{_uuid()}" transform="{IDENTITY}" printable="1"/>')
        parts_cfg = "".join(
            f'<part id="{pid}" subtype="normal_part">'
            f'<metadata key="name" value="{escape(pname, {chr(34): "&quot;"})}"/>'
            f'<metadata key="matrix" value="{IDENTITY4}"/>'
            f'<metadata key="extruder" value="{slot}"/>'
            f'<mesh_stat face_count="{solid.num_tri()}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>'
            "</part>"
            for pid, pname, slot, solid in part_ids
        )
        first_slot = part_ids[0][2] if part_ids else 1
        config_objects.append(
            f'<object id="{obj_id}"><metadata key="name" value="{escape(obj_name, {chr(34): "&quot;"})}"/>'
            f'<metadata key="extruder" value="{first_slot}"/>{parts_cfg}</object>'
        )
    main_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{NS}" xmlns:p="{NS_P}" xmlns:BambuStudio="{NS_BBS}" requiredextensions="p">'
        '<metadata name="Application">CharmMaker</metadata>'
        '<metadata name="BambuStudio:3mfVersion">1</metadata>'
        f'<resources>{"".join(main_objects)}</resources>'
        f'<build p:UUID="{_uuid()}">{"".join(build_items)}</build></model>'
    )
    instances = "".join(
        f'<model_instance><metadata key="object_id" value="{oid}"/><metadata key="instance_id" value="0"/>'
        f'<metadata key="identify_id" value="{100 + i}"/></model_instance>'
        for i, oid in enumerate(int(o.split('id="')[1].split('"')[0]) for o in main_objects)
    )
    config_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>'
        f'{"".join(config_objects)}'
        '<plate><metadata key="plater_id" value="1"/><metadata key="plater_name" value=""/>'
        f'<metadata key="locked" value="false"/>{instances}</plate></config>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '<Default Extension="config" ContentType="text/xml"/></Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        "</Relationships>"
    )
    model_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(rels)}</Relationships>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("3D/3dmodel.model", main_xml)
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        for sub_path, xml in sub_models.items():
            z.writestr(sub_path, xml)
        z.writestr("Metadata/model_settings.config", config_xml)
    return path
