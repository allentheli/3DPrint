"""Read a photo of a design card: find the markers, straighten the page, cut out the
drawing box and the name line. No network, no OCR."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .cards import CORNER_NAMES, CardLayout, aruco_dictionary, decode_marker_id, layout_for


@dataclass
class CardRead:
    layout: CardLayout | None            # None when no markers were found
    page: np.ndarray | None              # rectified page, BGR, px_per_card_mm
    box_image: np.ndarray                # BGR crop of the drawing box (plus margin)
    box_origin_mm: tuple[float, float]   # card mm of the crop's top-left (x, y-up)
    px_per_card_mm: float
    name_image: np.ndarray | None
    markers_found: int
    notes: list[str] = field(default_factory=list)


def _scan_zoom(page, max_side: int = 8000) -> float | None:
    """The zoom that renders a scanned PDF page at its photo's own resolution, or None for
    a page without a photo. iPhone Notes scans have odd page sizes (27 x 36 inches), so a
    fixed dpi can blow the photo up 4x, which wastes time and hides markers."""
    best = None
    for info in page.get_images(full=True):
        xref, w_px = info[0], info[2]
        for rect in page.get_image_rects(xref):
            if rect.width > 0.5 * page.rect.width:            # the scan, not a logo
                z = w_px / rect.width
                best = z if best is None else max(best, z)
    if best is None:
        return None
    return min(best, max_side / max(page.rect.width, page.rect.height))


def load_image(path: Path, page_index: int = 0, dpi: int = 300) -> np.ndarray:
    """Load a JPEG, PNG, HEIC or PDF page as a BGR array, honoring EXIF rotation. A scanned
    PDF page is rendered at its photo's own resolution; a drawn (vector) page at `dpi`."""
    from PIL import Image, ImageOps

    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import pymupdf

        doc = pymupdf.open(str(path))
        page = doc[page_index]
        zoom = _scan_zoom(page)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)) if zoom else page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        if path.suffix.lower() in (".heic", ".heif"):
            import pillow_heif

            pillow_heif.register_heif_opener()
        img = Image.open(path)
        img = ImageOps.exif_transpose(img).convert("RGB")
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def pdf_page_count(path: Path) -> int:
    import pymupdf

    return pymupdf.open(str(path)).page_count


DETECT_SIDES = (4000, 2500, 1600)    # smaller copies to try when a marker is missed


def detect_cards(cfg: dict, image: np.ndarray) -> dict[tuple[int, int], list[tuple[int, np.ndarray]]]:
    """Find our markers. Returns {(type_id, number): [(corner_index, corners_px[4,2]), ...]}.
    The detector misses markers that are hundreds of pixels wide (a 48 MP phone photo, a
    blown-up scan), so when a card is missing a corner it looks again on smaller copies
    and keeps what it finds there, in full-size pixels."""
    dictionary = aruco_dictionary(cfg)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    side = max(gray.shape)
    scales = [1.0] + [s / side for s in DETECT_SIDES if s < side]
    seen: dict[tuple[int, int], dict[int, np.ndarray]] = {}
    for k in scales:
        small = gray if k == 1.0 else cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        corners, ids, _ = detector.detectMarkers(small)
        if ids is not None:
            for quad, mid in zip(corners, ids.flatten()):
                decoded = decode_marker_id(int(mid))
                if decoded is None:
                    continue
                ci, type_id, number = decoded
                card = seen.setdefault((type_id, number), {})
                if ci not in card:                   # the sharpest copy wins
                    card[ci] = quad.reshape(4, 2).astype(np.float64) / k
        if seen and all(len(c) == 4 for c in seen.values()):
            break
    return {key: sorted(c.items()) for key, c in seen.items()}


def _product_for_type(cfg: dict, type_id: int) -> str | None:
    for name, tid in cfg["cards"]["type_ids"].items():
        if tid == type_id:
            return name
    return None


def read_card(cfg: dict, image: np.ndarray, product_hint: str | None = None) -> list[CardRead]:
    """Read every card visible in the image. Without markers, falls back to treating the
    whole image as a drawing for `product_hint`."""
    rd = cfg["reader"]
    ppm = float(rd["px_per_card_mm"])
    found = detect_cards(cfg, image)
    reads: list[CardRead] = []
    for (type_id, number), markers in found.items():
        product = _product_for_type(cfg, type_id)
        if product is None:
            continue
        lay = layout_for(cfg, product, number)
        src, dst = [], []
        for ci, quad in markers:
            src.extend(quad.tolist())
            mm = lay.marker_corners_mm(CORNER_NAMES[ci])
            dst.extend([[x * ppm, (lay.page[1] - y) * ppm] for x, y in mm])
        src_a = np.asarray(src, dtype=np.float64)
        dst_a = np.asarray(dst, dtype=np.float64)
        if len(markers) >= 2:
            H, _ = cv2.findHomography(src_a, dst_a, cv2.RANSAC, 3.0)
        else:
            H, _ = cv2.findHomography(src_a, dst_a, 0)
        if H is None:
            continue
        size = (int(round(lay.page[0] * ppm)), int(round(lay.page[1] * ppm)))
        page = cv2.warpPerspective(image, H, size, flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
        notes = []
        if len(markers) < 4:
            notes.append(f"only {len(markers)} of 4 markers found; straightening may be less exact")
        bx, by, bw, bh = lay.box
        m = rd["box_margin"]
        x0, x1 = int((bx - m) * ppm), int((bx + bw + m) * ppm)
        y0, y1 = int((lay.page[1] - (by + bh + m)) * ppm), int((lay.page[1] - (by - m)) * ppm)
        box_img = page[max(y0, 0):y1, max(x0, 0):x1].copy()
        name_img = None
        if product != "calibration":
            nx, ny, nw, nh = lay.name_box
            nyt = int((lay.page[1] - (ny + nh)) * ppm)
            name_img = page[nyt:int((lay.page[1] - ny + 2) * ppm), int((nx - 18) * ppm):int((nx + nw + 2) * ppm)].copy()
        reads.append(CardRead(lay, page, box_img, (bx - m, by + bh + m), ppm, name_img, len(markers), notes))
    if reads:
        return reads
    if product_hint is None:
        raise ValueError("no design-card markers found; pass the product to use the whole image as a drawing")
    return [CardRead(None, None, image.copy(), (0.0, 0.0), 0.0, None, 0,
                     ["no markers found: whole image used, scaled to the product's default size"])]
