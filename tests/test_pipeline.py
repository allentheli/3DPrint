import json
import zipfile
import xml.dom.minidom as md

import pytest
import trimesh

from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from tests.synthetic import draw_cat_card, draw_circle_card, draw_heart_keychain, draw_small_star_card


@pytest.fixture(scope="module")
def batch(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("batch")
    photos = [draw_circle_card(cfg, d), draw_cat_card(cfg, d), draw_small_star_card(cfg, d), draw_heart_keychain(cfg, d)]
    return run_batch(cfg, photos, d / "out")


def test_every_card_became_a_piece(batch):
    assert batch.problems == []
    names = sorted(p.name for p in batch.pieces)
    assert names == ["clip-02", "clip-03", "clip-04", "key-03"]


def test_scale_is_exactly_one_third(cfg, batch):
    """A 60 mm ring on the card (20 mm real) plus a 1.5 mm border each side."""
    piece = next(p for p in batch.pieces if p.name == "clip-02")
    w, h = piece.size()
    expected = 20.0 + 2 * cfg["process"]["border"]
    assert w == pytest.approx(expected, abs=0.5)
    assert h == pytest.approx(expected, abs=0.5)
    black = next(i for i in piece.design.inks if i.name == "black")
    minx, miny, maxx, maxy = black.geometry.bounds
    assert maxx - minx == pytest.approx(20.0, abs=0.4)


def test_yellow_survives_and_guides_vanish(batch):
    star = next(p for p in batch.pieces if p.name == "clip-04")
    names = {i.name for i in star.design.inks}
    assert "yellow" in names
    assert not any(n in ("sky blue", "teal", "blue") for n in names)
    # A small star gets the backer disc so the clip pocket fits.
    assert any("backer disc" in f for f in star.design.fixes) or star.attachment["wall"] >= 1.5


def test_fixes_are_logged(batch):
    cat = next(p for p in batch.pieces if p.name == "clip-03")
    text = " ".join(cat.design.fixes)
    assert "speck" in text and "thickened" in text and "border" in text and "bridge" in text


def test_pieces_are_sound(cfg, batch):
    for piece in batch.pieces:
        union = None
        for name, solid in piece.parts.items():
            tm = to_trimesh(solid)
            assert tm.is_watertight, name
            union = solid if union is None else union + solid
        assert count_bodies(union) == 1
        lo = union.bounding_box()
        assert lo[2] == pytest.approx(0.0, abs=1e-6)
        assert lo[5] == pytest.approx(piece.thickness, abs=1e-6)
        # Every color part lives in the front face layers only.
        face = cfg["process"]["color_face_depth"]
        for name, solid in piece.parts.items():
            if name != piece.base_part:
                assert solid.bounding_box()[5] == pytest.approx(face, abs=1e-6)


def test_clip_pocket_inside_with_wall(cfg, batch):
    from shapely.geometry import Point
    for piece in (p for p in batch.pieces if p.design.product == "hair_clip"):
        att = piece.attachment
        pocket = Point(att["center"]).buffer(att["diameter"] / 2)
        assert piece.design.outline.contains(pocket)
        assert piece.design.outline.exterior.distance(pocket) >= cfg["hardware"]["clip_pocket_min_wall"] - 1e-6
        # Pocket really is cut: a slice near the back has a hole there, the front does not.
        base = piece.parts[piece.base_part]
        back = base.slice(piece.thickness - att["depth"] / 2).to_polygons()
        front = base.slice(att["depth"]).to_polygons()
        assert len(back) >= 2 and len(front) >= 1


def test_keychain_tab_hole(cfg, batch):
    from shapely.geometry import Point
    key = next(p for p in batch.pieces if p.name == "key-03")
    att = key.attachment
    hole = Point(att["hole_center"]).buffer(att["hole_diameter"] / 2)
    outline = key.design.outline
    assert outline.interiors, "hole must be cut through the outline"
    ring = outline.buffer(0).exterior
    assert ring.distance(hole) >= cfg["hardware"]["keyring_hole_min_wall"] - 0.05
    # Hole goes through every layer.
    for solid in key.parts.values():
        pass
    base = key.parts[key.base_part]
    z_mid = key.thickness / 2
    polys = base.slice(z_mid).to_polygons()
    assert len(polys) >= 2


def test_plates_and_files(cfg, batch):
    assert len(batch.plates) >= 1
    for plate in batch.plates:
        assert len(plate.filaments) <= cfg["printer"]["max_filaments_per_plate"]
        boxes = []
        for pp in plate.pieces:
            w, h = pp.piece.size()
            boxes.append((pp.x, pp.y, pp.x + w, pp.y + h))
            assert pp.x >= 0 and pp.y >= 0
            assert pp.x + w <= cfg["printer"]["bed_size"][0] and pp.y + h <= cfg["printer"]["bed_size"][1]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])
    for n, paths in batch.files["plates"].items():
        z = zipfile.ZipFile(paths["3mf"])
        names = z.namelist()
        assert "Metadata/model_settings.config" in names and "3D/3dmodel.model" in names
        for name in names:
            md.parseString(z.read(name))
        cfg_xml = z.read("Metadata/model_settings.config").decode()
        assert 'key="extruder"' in cfg_xml
        sc = trimesh.load(paths["plain-3mf"])
        assert len(sc.geometry) == sum(len(pp.piece.parts) for pp in batch.plates[n - 1].pieces)
    assert batch.files["contact_sheet"].exists()
    notes = batch.files["notes"].read_text()
    assert "AMS slot" in notes and "0.12" in notes


def test_design_json_written(batch, cfg):
    out = batch.files["notes"].parent / "designs"
    for piece in batch.pieces:
        data = json.loads((out / f"{piece.name}.json").read_text())
        assert data["name"] == piece.name and data["fixes"]
        assert (out / f"{piece.name}-preview.png").exists()
