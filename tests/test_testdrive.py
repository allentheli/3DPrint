"""The test-drive pack: a parent page plus six cards the reader recognizes."""

import pymupdf
from PIL import Image

from charm_maker.reader import read_card
from charm_maker.testdrive import TEST_CARDS, write_test_drive


def test_pack_has_a_parent_page_and_readable_cards(cfg, tmp_path):
    import cv2
    import numpy as np

    pdf = write_test_drive(cfg, tmp_path / "pack.pdf")
    doc = pymupdf.open(str(pdf))
    assert doc.page_count == 1 + len(TEST_CARDS)
    text = doc[0].get_text()
    for must in ("Actual size", "Scan Documents", "What to draw", "test drive"):
        assert must in text
    for i, (product, number, _, _) in enumerate(TEST_CARDS, start=1):
        pix = doc[i].get_pixmap(dpi=150)
        img = cv2.cvtColor(np.asarray(Image.frombytes("RGB", (pix.width, pix.height), pix.samples)), cv2.COLOR_RGB2BGR)
        reads = read_card(cfg, img)
        assert len(reads) == 1
        assert (reads[0].layout.product, reads[0].layout.number) == (product, number)
