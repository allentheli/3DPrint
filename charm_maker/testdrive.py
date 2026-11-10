"""A test-drive pack: one parent page and six design cards for one young artist, so a
whole run (draw, scan, upload, preview, print) can be tried before the party."""

from __future__ import annotations

import tempfile
from pathlib import Path

# (product, card number, what it makes, what to draw)
TEST_CARDS = [
    ("hair_clip", 1, "Hair clip charm", "A smiley face, a flower or a bug. Cover the circle."),
    ("hair_clip", 2, "Hair clip charm", "A rainbow or a heart, colored in."),
    ("keychain", 1, "Keychain", "Her favorite animal, big."),
    ("keychain", 2, "Keychain", "Her name in big, fat letters."),
    ("magnet_figure", 1, "Fridge magnet", "A person, a pet or a monster, standing on the line."),
    ("pendant", 1, "Necklace", "Anything she loves, colored in."),
]


def card_stem(cfg: dict, product: str, number: int) -> str:
    from .cards import card_layout

    return card_layout(cfg, product, number).stem


def _parent_page(cfg: dict, path: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    st = getSampleStyleSheet()
    body = st["BodyText"]
    body.fontSize = 10.5
    body.leading = 13
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=11 * mm, bottomMargin=11 * mm)

    def steps(items):
        return ListFlowable([ListItem(Paragraph(t, body), leftIndent=12) for t in items], bulletType="1", leftIndent=14)

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(t, body), leftIndent=12) for t in items], bulletType="bullet", leftIndent=14)

    rows = [[Paragraph("<b>Card (as printed at its top)</b>", body), Paragraph("<b>Makes</b>", body),
             Paragraph("<b>What to draw</b>", body)]]
    for product, number, makes, idea in TEST_CARDS:
        title = cfg["products"][product]["label"]
        rows.append([Paragraph(f"{title}, card {number:02d}", body), Paragraph(makes, body), Paragraph(idea, body)])
    table = Table(rows, colWidths=[45 * mm, 50 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    flow = [
        Paragraph("Charm Maker test drive", st["Title"]),
        Paragraph("Six cards for one young artist, about 20 minutes of drawing. Each card shows what it makes "
                  "and its number at the top.", body),
        Spacer(1, 3 * mm),
        Paragraph("Before you start", st["Heading2"]),
        steps([
            'Print this PDF on US Letter paper. In the print dialog choose <b>Actual size</b> (or 100%), not <b>Fit to page</b>.',
            "Check one card: the line at the bottom is 50 mm (about 2 inches) long. If it is not, print again at Actual size.",
            "Markers: broad-tip, black plus two or three bright colors. No pencil, crayon or glitter this time.",
        ]),
        Paragraph("The cards", st["Heading2"]),
        table,
        Spacer(1, 2 * mm),
        Paragraph("Tips for her: press hard, go big, color it in, and stay inside the box. Write her name on the line.", body),
        Paragraph("After drawing", st["Heading2"]),
        steps([
            "iPhone Notes: open a note, tap the camera button, choose <b>Scan Documents</b>, scan all six cards one after "
            "another, then tap <b>Save</b>. That makes one PDF.",
            'Share the PDF into the Claude chat for this project and say "test drive".',
            "Claude sends back a contact sheet (what each piece will look like), print files and print notes.",
        ]),
        Paragraph("Let her pick a shape (optional)", st["Heading2"]),
        Paragraph("Every card can come out <b>flat</b> (the default), <b>puffy</b> like a pillow, with a <b>raised "
                  "outline</b>, or as a <b>figurine</b> (a rounded front like a toy, still flat on the back so the clip "
                  'or magnet works). Ask her which she wants and tell Claude, for example: "keychain 1 puffy, the '
                  'magnet a figurine".', body),
        Paragraph("What to look for", st["Heading2"]),
        bullets([
            "Does each preview look like her drawing? Anything missing, or anything extra?",
            "Open a plate in Bambu Studio: each color should be its own part you can assign a filament to.",
            "Print one plate. Does the clip charm sit on the hair clip pad, and does the split ring fit the keychain? "
            "(These sizes are guesses until the fit-test plate is printed.)",
            "Tell Claude what she liked and what looked wrong. That is the whole point of the test drive.",
        ]),
    ]
    doc.build(flow)
    return path


def write_test_drive(cfg: dict, out_path: Path) -> Path:
    import pymupdf

    from .cards import write_cards_pdf

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = [_parent_page(cfg, tmp / "parent.pdf")]
        for i, (product, number, _, _) in enumerate(TEST_CARDS):
            parts.append(write_cards_pdf(cfg, [product], tmp / f"card-{i}.pdf", numbers=[number]))
        merged = pymupdf.open()
        for p in parts:
            with pymupdf.open(str(p)) as src:
                merged.insert_pdf(src)
        merged.set_metadata({"title": "Charm Maker test drive"})
        merged.save(str(out_path))
    return out_path
