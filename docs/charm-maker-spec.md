# Charm Maker: build instructions for Claude Code

Last updated: November 9, 2026

You are building a small tool that turns a photo of a hand drawing into a ready-to-print file for Allen's Bambu Lab X2D with AMS. Read this whole file before writing code.

## 1. What you are building

Kids (and adults) draw on printed design cards. Allen takes a photo of each card and uploads it to a Claude Code session. You turn every photo into a print file for one of the products below, plus a preview picture, without asking questions unless something is unreadable.

| Product | Made by | What it is |
| --- | --- | --- |
| Hair clip charm | Kids | A flat charm glued onto a hair clip's round pad |
| Keychain | Kids | A flat charm with a ring tab |
| Clicker keychain | Kids | A small case holding a clicky keyboard switch, with the kid's design as the keycap, and a ring tab |
| Magnet figure | Kids | A flat character with a magnet glued into the back. It goes on the fridge or stands up on the universal stand |
| Figure stand | (no drawing) | One stand design that holds any magnet figure |
| Earrings | Adults | A matching pair of light flat charms with a jump-ring hole or a flat back for stud posts |
| Necklace pendant | Adults | A flat charm with a bail hole |

First use: a design party for four girls aged 5 and 8 (two families), with the parents making earrings and pendants. The tool should keep working for later parties and one-off drawings.

## 2. Who you are working with

- Allen owns the project and does not write code. Do the work yourself, run it, and tell him in plain words how to see the result.
- He prints with Bambu Studio and is comfortable opening 3MF files from MakerWorld. He has no 3D modeling experience.
- When he has to do something by hand (create a repository, print a test, measure a part), give numbered steps with exact button names.
- Ask at most one question at a time, and only when the answer changes what you build. Otherwise pick the simplest option, make it a setting, and record it in `DECISIONS.md`.
- Never report something as working unless you ran it. Say plainly what you could not test (anything that needs the real printer, the real clip or the real magnets).

## 3. Hard rules

1. **Stay faithful to the drawing.** Fix only what is needed to print: thicken thin lines, remove specks, add a border, round sharp corners. Never redraw, restyle or "improve" a design. No AI image generation or AI image-to-3D in the pipeline.
2. **Flat, flush, face-down.** Every design piece is a flat plate with its colors flush on the front face, printed face-down. No raised lines: they snag hair and snap off.
3. **One solid piece.** Every design prints as one connected part. Separate bits get joined by the border (section 7).
4. **Preview before print.** Every output comes with an actual-size preview showing the colors, the filament each color maps to, and every fix you made.
5. **Drawings stay private.** No network calls while processing. Never commit photos or outputs to git (add them to `.gitignore`). Never send anything to the printer.
6. **Fit-critical numbers come from test prints, not guesses.** They live in one config file and are set from Allen's fit-test results (milestone 0).

## 4. Technical approach

- Python 3, run from the command line by you. Suggested: OpenCV (including its ArUco markers), NumPy, scikit-image, Shapely for 2D geometry, manifold3d or trimesh for solids, ReportLab (or similar) for the card PDF. Justify other choices in `DECISIONS.md`.
- One config file holding every product size, tolerance and the filament list.
- Define products in config, so more flat products (ornaments, gift tags, bookmarks, name plates, jigsaw puzzles, Play-Doh stamps and cutters) can be added later without new code. Do not build those yet.
- A `CLAUDE.md` in the repository with the everyday runbook (section 10). This is the most important file for daily use, because future sessions will start cold.
- Automated tests for geometry: watertight solids, one connected part per design, correct dimensions, and every pocket (clip pad, magnet) inside the shape with enough wall around it.
- Works in a cloud Claude Code session or on Allen's computer. In a cloud session, hand Allen the print files as downloads.

## 5. Products

All numbers are starting values. Fit-critical ones (marked *) are replaced by milestone 0 results.

| Product | Real size (longest side) | Thickness | Attachment | Copies |
| --- | --- | --- | --- | --- |
| Hair clip charm | 14 to 25 mm | 2.4 mm | Round pocket on the back for the clip pad* | 1 |
| Keychain | 35 to 55 mm | 3.2 mm | Ring tab with a 5 mm hole* | 1 |
| Clicker keychain | Keycap top 16 to 22 mm | See below | Switch case with ring tab | 1 |
| Magnet figure | 30 to 55 mm | About 3.2 mm | Recessed magnet pocket on the back* | 1 |
| Earrings | 15 to 35 mm | 1.8 mm | 2.0 mm jump-ring hole*, or a flat back for glue-on studs | 2 |
| Pendant | 25 to 45 mm | 2.6 mm | 3.5 mm bail hole* | 1 |

### Hair clip charm

- The clip is about 2 inches (51 mm) long and flat, with a round plastic pad about 11 mm across. The charm is glued onto the pad.
- Cut a round pocket on the back of the charm to fit the pad: 0.6 mm deep, diameter set by the fit test (try 11.2, 11.5 and 11.8 mm). The pocket centers the charm and gives the glue edges to grip.
- Place the pocket at the point deepest inside the shape (the center of the largest circle that fits), with at least 1.5 mm of material around it.
- If no 13 mm circle fits inside the design, grow the border first. If that is not enough (a stick figure, a thin word), add a round backer disc on the back, and say so in the preview.
- The design card's "cover the circle" zone (section 6) keeps most drawings big enough to cover the pad.

### Keychain

- A ring tab merges with the top of the design by default (top means the top of the card). A setting moves it to top-left, top-right, left or right.
- 5 mm hole, at least 2.5 mm of wall around it, same thickness as the charm.

### Clicker keychain

- Allen has blue clicky keyboard switches. Assume Cherry MX-compatible (plus-shaped stem). Before building this product, ask Allen for the brand or a photo of one switch, and adapt if it is not MX-style.
- **Case:** a rounded box. The switch snaps in from the top.
  - Top plate 1.5 mm thick (the MX spec is 1.5 ± 0.1 mm) with a 14 × 14 mm square cutout (fit test: 13.9, 14.0, 14.1 mm).
  - A closed cavity under the plate, at least 15.6 mm square and about 9 mm deep. That covers the 5 mm of switch housing below the plate plus the pins.
  - Print upright with the top plate bridging the cavity. If the bridge prints poorly, switch to a two-piece case and record it in `DECISIONS.md`.
  - A ring tab on one side. The case prints in one filament, chosen per order.
- **Keycap:** a flat charm-shaped top made from the kid's design, with a cross-shaped socket underneath for the MX stem (fit test: three tolerances). Print it face-down with the socket pointing up, so the design face comes out smooth. Check that the keycap clears the switch housing and the case at full travel (about 4 mm).
- **Fallback setting:** if printed sockets turn out unreliable, make the design as a flat charm to glue onto a store-bought blank flat-top MX keycap.

### Magnet figure

The same figure lives on the fridge or stands up on the universal stand.

- Allen glues the magnets in after printing. No sealed magnets and no print pauses; do not add them unless Allen asks.
- Each figure gets an open, recessed round pocket on the back for one 10 × 2 mm disc magnet, or two for figures over 45 mm. The pocket is snug (diameter set by the fit test) and slightly shallower than the magnet (start at 1.9 mm deep), so the magnet sits a hair proud and touches the fridge directly. A recess holds glue far better than a flat back.
- At least 1.2 mm of plastic behind the pocket bottom (the 0.6 mm color face plus base), so the figure is about 3.2 mm thick.
- At least 1.2 mm of wall all around the pocket. Never put a magnet on a flat back.
- The figure's bottom is its lowest point as drawn on the card. Place the magnet at a standard height above the bottom (start at 12 mm) so it lines up with the stand. If the shape cannot fit the pocket there, use the nearest spot that fits and flag it in the preview.
- The pockets face up while printing, so magnet figures can share plates with other face-down pieces.
- Print notes remind Allen to glue the magnets in with gel super glue, and to switch to two-part epoxy if any pop out.

### Figure stand

- One stand design fits every magnet figure: a wide base that does not tip, a ledge for the figure's bottom, and an upright back tilted slightly backward.
- A steel fender washer (about 25 mm, zinc-plated steel) is glued into a recess cut from the back of the upright, centered at the standard magnet height above the ledge. Leave a thin front wall (start at 0.6 mm) so the magnet grips through as little plastic as possible. A washer, not a magnet, so polarity never matters.
- One filament, no kid design on the stand for now. Print it in whatever orientation needs no supports.

### Earrings

- Always a pair on the same plate. Identical by default; a mirrored option; or two different drawings from the earring card's two boxes.
- Two styles: hook (2.0 mm hole near the top for a jump ring, at least 1.5 mm of wall) or stud (no hole, flat back, with an optional shallow pocket for a glue-on post pad).
- Keep them light: 1.8 mm thick and 35 mm at most.

### Pendant

- A 3.5 mm bail hole near the top, or a small loop tab like the keychain's (setting).

## 6. Design cards (you generate these)

You generate the printable cards, so the markers on the cards always match what the reader looks for.

- Output a PDF on US Letter. Each page carries a 50 mm check ruler and a note to print at "Actual size."
- **Scale:** every drawing box is exactly 3 times the product's real size. One fat marker line (about 4 to 5 mm) becomes a 1.3 to 1.7 mm line on the print. Keep this scale the same for every product so the same markers always give the same results.
- **Markers:** four ArUco markers at the corners of each card. They give the scale, straighten a tilted photo, and encode the card type, so the reader knows the product without being told. Each card also gets a printed card number (01, 02...) for file names.
- **Guides:** the box, the zones and the labels print in a very light color that the reader removes along with the paper. Test it against a yellow marker, the hardest color to separate from paper, and pick the guide color that separates most reliably.
- **Kid-facing pictures, minimal words:**
  - Hair clip: a box with a light circle in the middle, about 39 mm across (13 mm real) and labeled "cover the circle."
  - Keychain: a box with a small ring picture just outside the top edge showing where the ring goes.
  - Clicker: a rounded square box the size of the keycap.
  - Magnet figure: a box with a light "ground line" near the bottom labeled "stand here."
  - Earrings: two boxes side by side.
  - Pendant: a box with a small bail picture at the top.
- Picture rules on every kid card: "fat marker," "black + 1 color," "no pencil or crayon."
- A name line outside the drawing box. Do not read the name with OCR. Just crop that area into the preview so Allen can match pieces to kids.
- **Half-drawn cards** for the younger kids: the same cards with a simple outline pre-printed in black (a cloud, a heart, a cat head, a star, a bow). The reader treats the printed black outline as ink, so the outline is part of the kid's design.
- Adult cards allow up to 3 colors plus black.

### Other inputs to accept

- A photo of a drawing on any paper (no markers): ask which product, find the drawing, and scale it to the product's default size.
- A digital image (PNG or SVG) from an adult's iPad drawing: same, without the photo cleanup.
- Text: "a keychain that says Mia." Use one bold, rounded, open-license font bundled in the repository.

## 7. From photo to print file

1. **Read the card:** find the markers, straighten and crop the photo, get the exact scale, read the card type and number. If the markers are not found, use the fallback above.
2. **Clean:** even out lighting and shadows, then remove the paper and the printed guides.
3. **Separate the inks:** black (dark, low color) and up to 1 color for kid cards or 3 for adult cards (group the colored pixels by hue). Paper areas inside the outline become the base color.
4. **Shape:** the outer edge of all the ink, filled in, is the piece's outline.
5. **Fix for printing**, and log every fix for the preview:
   - Ink areas narrower than 1.0 mm at real size get thickened. Specks smaller than about 1 square mm are removed. Tiny holes are filled.
   - The outline gets a border, 1.5 mm by default, in the base color, like the white edge on a die-cut sticker. It joins separate pieces into one and protects thin bits like whiskers and sun rays. On by default for kid cards, off by default for adult cards.
   - Any outer feature still narrower than 2 mm gets smoothed into the border.
   - Sharp outer corners are rounded slightly (0.5 mm).
6. **Build the solid:** the front 0.6 mm holds the colors side by side, flush. Everything behind it is the base color. Then add the product's attachment (clip pocket, magnet pocket, tab or hole), or for the clicker, the keycap and the case.
7. **Export:**
   - One 3MF per plate. Each design is one object, and each color is a separate part of that object with a clear name ("card-03 black", "card-03 pink").
   - Try to set the filament slot for each part inside the 3MF so Bambu Studio opens with colors already assigned. If Bambu Studio does not honor it reliably, leave assignment to Allen (two clicks per color) and say so in the README.
   - Also export one STL per color part as a backup.
8. **Preview:** one image per design at actual size and at 4× zoom, with color swatches, the filament each color maps to, the name crop from the card, and the list of fixes. Plus one contact sheet for the whole batch.

**Base color.** By default, paper areas inside the outline print white, so the piece matches what was drawn. A setting changes this to "fill with the kid's color" for strictly two-filament prints.

## 8. Colors and plates

- **Filament list** in config: name, AMS slot and color code for each spool Allen owns. He fills it in once from his spools.
- Map each ink color to the nearest filament and show the mapping in the preview. Allen can override it in plain words ("card 3's pink should be Magenta").
- **Plate planner:** pack many designs onto each plate. Group designs so each plate needs at most N filaments (setting, default 4, one AMS). Designs with the same colors share a plate. Because the colors sit only in the first few layers, a full plate costs little extra purge.
- **Orientation:** design pieces face-down (including magnet figures); clicker cases upright; keycaps face-down with the socket up; stands in whatever orientation needs no supports. Give clicker cases and stands their own plates if their best layer heights differ from the charms'.
- **Print notes** with every output: suggested layer height (0.12 mm for charms, figures and earrings, 0.2 mm for clicker cases and stands), and plate choice (the smooth plate gives a glossy face, the textured plate a matte, sparkly face).

## 9. Build order

Finish and show each milestone before starting the next. Each ends with something Allen can print or hold.

**Milestone 0: fit test.** One small single-color plate with numbered test pieces: discs with the three clip pocket sizes, three keyring hole sizes, three jump-ring hole sizes, three magnet pocket sizes, three MX switch cutout coupons with the 1.5 mm plate, three keycap stem sockets, and one figure stand with its washer recess. Give Allen numbered steps: print it, then try the real clip pad, a switch, a keycap stem test, a split ring, a jump ring, and a magnet glued into the best pocket (checked on the fridge and on the stand with a washer). He reports which numbers fit, and you write the results into config. Done when config holds tested values.

**Milestone 1: cards, hair clips and keychains.** The card PDF (clip and keychain cards first), the reader, the full pipeline, previews and 3MF export. Done when Allen scans a test card with the iPhone Notes document scanner, uploads it, gets a file that opens in Bambu Studio and prints, and the charm sits on the real clip.

**Milestone 2: party batch.** A folder of photos becomes packed plates in one go, with the contact sheet, filament mapping and overrides, and the half-drawn card set. Done when eight cards become plates in one request.

**Milestone 3: clicker.** Case, keycap and the glue-on fallback. Done when a real switch snaps in, clicks freely, and the keycap stays on.

**Milestone 4: adults.** Earring and pendant cards, adult color limits, PNG and SVG input, and the text mode. Done when an iPad drawing becomes a printed earring pair.

**Milestone 5: magnet figures and the stand.** The figure card, the magnet pocket, the stand, and the print notes. Done when a printed figure with a glued magnet holds on the fridge and stands on the stand. Ask Allen whether magnet figures are needed for the party; if yes, build this right after milestone 2.

If Allen gives a party date, reorder to fit it. The party needs milestones 0 to 2 at minimum.

## 10. Everyday runbook (copy into CLAUDE.md)

When Allen uploads photos or images:

1. Run the pipeline on all of them. Do not ask which product if the cards say it.
2. Show the contact sheet. In plain words, list the fixes and anything you were unsure of.
3. Ask only if a card is unreadable or a color mapping is genuinely unclear.
4. Hand over the plate files and say, for each plate, which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clips, studs, magnets), rings (keychains, earrings, pendants), switch insertion (clickers).

## 11. For Allen: things to have on hand

- **Glue:** gel super glue for magnets and clips, E6000 as an alternative for the clip pads, and optionally two-part epoxy for magnets that pop out. Test on the clip pad first; some plastics resist glue, and a light scuff with sandpaper helps. Glue in a ventilated room, adults only, and let it cure fully (E6000 needs about a day) before kids use the pieces.
- **Rings and findings:** 25 mm split key rings, small jump rings, earring hooks, glue-on stud posts with flat pads (hypoallergenic metal), necklace chains or cord.
- **Magnets and washers:** 10 × 2 mm neodymium disc magnets; 1-inch zinc-plated steel fender washers for the stands. Many stainless steel washers are not magnetic.
- **Switches:** the blue clicky switches (have).
- **Markers:** broad-tip black plus bright colors. Avoid pencil, crayon, glitter and very pale colors until tested.
- **Optional:** a cheap digital caliper makes the fit tests and pad measurement easier.
- **Safety:** glued charms and magnets are small parts. Check every glue joint before handing a piece over, and keep any magnet that pops loose away from young children.

## 12. Parked on purpose

Do not build these unless Allen asks:

- AI image-to-3D figurines (such as Meshy in MakerLab). That is a separate project.
- Raised or sculpted designs, lithophanes, more than 4 colors.
- Sealed-in magnets and print pauses.
- More flat products: ornaments, gift tags, bookmarks, name plates, jigsaw puzzles, Play-Doh stamps and cutters (keep the config ready for them).
- Printing a whole hair clip.
- A web or iPad app version of this tool.

## 13. Files to keep in the repository

- `README.md`: what the tool is and how to use it, in plain language
- `CLAUDE.md`: the everyday runbook (section 10)
- `DECISIONS.md`: each choice you made that this file did not settle, one line each
- `CHANGELOG.md`: what changed in each milestone
- The config file and this file
