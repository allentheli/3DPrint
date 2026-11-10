# Charm Maker: build instructions for Claude Code

Last updated: November 9, 2026. Simplified: every product for everyone (earrings for adults), sideways loops for pendants and earrings, glued-on magnets, and colors kept as separate parts that Allen assigns in Bambu Studio.

**The one thing that matters most:** turn a drawing, consistently, into a print file that fits a hair clip, keychain, clicker keychain, magnet figure or necklace, and for adults also earrings. Everything else is secondary.

You are building a small tool that turns a photo of a hand drawing into a ready-to-print file for Allen's Bambu Lab X2D with AMS. Read this whole file before writing code.

## 1. What you are building

Kids (and adults) draw on printed design cards. Allen takes a photo of each card and uploads it to a Claude Code session. You turn every photo into a print file for one of the products below, plus a preview picture, without asking questions unless something is unreadable.

| Product | Made by | What it is |
| --- | --- | --- |
| Hair clip charm | Anyone | A flat charm glued onto a hair clip's round pad |
| Keychain | Anyone | A flat charm with a ring tab |
| Clicker keychain | Anyone | A small case holding a clicky keyboard switch, with the design as the keycap, and a ring tab |
| Magnet figure | Anyone | A flat character with a magnet glued onto its flat back. It goes on the fridge or stands up on the universal stand |
| Figure stand | (no drawing) | One stand design that holds any magnet figure |
| Necklace pendant | Anyone | A flat charm with a loop on top; the chain goes through it left to right |
| Earrings | Adults | A matching pair of light flat charms with a loop on top for the hook (left to right), or a flat back for stud posts |

First use: a design party for four girls aged 5 and 8 (two families), with the parents making earrings and pendants. The tool should keep working for later parties and one-off drawings.

## 2. Who you are working with

- Allen owns the project and does not write code. Do the work yourself, run it, and tell him in plain words how to see the result.
- He prints with Bambu Studio and is comfortable opening 3MF files from MakerWorld. He has no 3D modeling experience.
- When he has to do something by hand (create a repository, print a test, measure a part), give numbered steps with exact button names.
- Ask at most one question at a time, and only when the answer changes what you build. Otherwise pick the simplest option, make it a setting, and record it in `DECISIONS.md`.
- Never report something as working unless you ran it. Say plainly what you could not test (anything that needs the real printer, the real clip or the real magnets).

## 3. Hard rules

1. **Stay faithful to the drawing.** Fix only what is needed to print: thicken thin lines, remove specks, add a border, round sharp corners. Never redraw, restyle or "improve" a design. No AI image generation or AI image-to-3D in the pipeline.
2. **Flat by default, shaped on request.** The default is a flat plate with its colors flush on the front face, printed face-down (and built mirrored, so the face reads right when the piece is turned over). Optional styles for every product: puffy, a raised outline, or both (section 5). They print face-up with the colors on top. Raised parts are rounded so they snag and snap less.
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
| Magnet figure | 30 to 55 mm | About 3.2 mm | Flat back; the magnet is glued on | 1 |
| Earrings | 15 to 35 mm | 1.8 mm | Top loop with a 2.0 mm hole running left to right*, or a flat back for glue-on studs | 2 |
| Pendant | 25 to 45 mm | 2.6 mm | Top loop with a 3.5 mm hole running left to right* | 1 |

### Shape styles

Every product can be flat (the default) or shaped. All shapes come straight from the drawing; nothing is redrawn.

- **Puffy:** the piece swells into a pillow, from a base slab at the edge to full height in the middle, with a rounded quarter-circle rise. The height at a point comes from its distance to the outline.
- **Outlined:** the drawing's dark outline (black, or the darkest ink if it is dark enough) stands up as a rounded 0.6 mm ridge.
- **Puffy-outlined:** both.
- Shaped pieces print face-up with the colors on top, back flat on the bed. The clip pocket stays on the back (the printer bridges over it); loops stay flush with the back; magnets still glue onto the flat back.
- Per product base and puff heights live in config. The style is chosen per run or per card in plain words ("make card 3 puffy").
- Trade-off: colors change over more layers, so shaped pieces print slower and purge more, and the front shows fine layer lines instead of the glossy bed finish.
- **Figurine:** the drawing's front inflated like a balloon or a plush toy. The height at each point follows how wide the drawing is there (the largest circle inside the outline that covers it), so a wide body becomes a fat round body and an arm a round tube. Still no redrawing: the outline and colors are the kid's, and the depth is a guess from the outline only.
  - **Flat back (default):** only the front is rounded. It stays the card's product at the card's size: the clip pocket, the glued-on magnet, the ring tab and the loops all work as on the other shaped styles. It prints face-up, back on the bed, no supports. The dome is capped per product (hair clip 5 mm, earrings 4 mm, pendant 6 mm, keychain 8 mm, magnet figure 10 mm), scaled as a whole so it stays round.
  - **Round back (on request):** a standalone figure about 60 mm tall, rounded on both sides; the card's ring, clip or loop is not used. The back is blank (a character should not have eyes on the back) or a mirror of the front (patterns, ornaments seen from both sides). The bottom is cut flat so it stands, or gets a round disc stand, or stays round. Prints lying on its back with tree supports, on its own plate, at 0.16 mm layers. Supports are fine here (Allen's call).
  - One solid split into color parts, like the other shaped styles. Colors change over many layers, so figurines purge the most.

### Loops for pendants and earrings

- The hole runs left to right, parallel to the face, so the chain or the earring hook goes straight through and the piece hangs facing forward. No jump ring needed.
- The loop sits on top, above the piece's balance point (not on its highest bump), so it hangs straight. It bridges a dip such as the top of a heart.
- The loop's front is flush with the face; it stands taller than the charm on the back, because the hole needs plastic all around it. The hole is a flat-topped teardrop so it prints face-down without supports.
- The loop never covers the colors on the front face. Nothing within 3 mm either side may stand above the hole, so the chain passes freely.

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

- A plain flat back. Allen glues a 10 × 2 mm disc magnet onto it after printing. No pockets, no sealed magnets, no print pauses.
- Print notes say to glue it about 12 mm above the figure's bottom, so it lines up with the washer in the stand, with gel super glue (two-part epoxy if it pops off).

### Figure stand

- One stand design fits every magnet figure: a wide base that does not tip, a ledge for the figure's bottom, and an upright back tilted slightly backward.
- A steel fender washer (about 25 mm, zinc-plated steel) is glued into a recess cut from the back of the upright, centered at the standard magnet height above the ledge. Leave a thin front wall (start at 0.6 mm) so the magnet grips through as little plastic as possible. A washer, not a magnet, so polarity never matters.
- One filament, no kid design on the stand for now. Print it in whatever orientation needs no supports.

### Earrings

- For adults. Always a pair on the same plate from one drawing: identical by default, or the second one mirrored (setting).
- Two styles: hook (the top loop above, with a 2.0 mm hole running left to right) or stud (no loop, flat back for a glue-on post).
- Keep them light: 1.8 mm thick and 35 mm at most.

### Pendant

- The top loop above, with a 3.5 mm hole running left to right for the chain.

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
  - Earrings: one box; the drawing becomes a matching pair.
  - Pendant: a box with a small loop picture at the top.
- Picture rules on every card, each with a small picture: "Use the colors in the printer" (a small printer), "Big and bold," "Color it in." The same cards serve kids and adults.
- A name line outside the drawing box. Do not read the name with OCR. Just crop that area into the preview so Allen can match pieces to kids.
- **Half-drawn cards (optional, off by default; Allen does not think they are needed):** the same cards with a simple outline pre-printed in black (a cloud, a heart, a cat head, a star, a bow). The reader treats the printed black outline as ink, so the outline is part of the kid's design.
- **Corner markers, explained for parents:** the four square markers look like QR codes but are position markers. They straighten a tilted photo, set the exact size, and say which product and card number it is.
- **Marker calibration card (optional):** generated from the loaded slots in config (section 8). Same corner markers as the other cards, and one box per loaded filament, labeled with its slot number and spool name. Allen fills each box solid with the marker that matches that spool and scans the card. The reader stores each marker's photographed color with its slot and from then on reads kid ink by the nearest calibrated marker. Allen rescans it whenever he changes spools or markers. The white base spool gets no box, because white is the paper.

### Other inputs to accept

- A photo of a drawing on any paper (no markers): ask which product, find the drawing, and scale it to the product's default size.
- A digital image (PNG or SVG) from an adult's iPad drawing: same, without the photo cleanup.
- Text: "a keychain that says Mia." Use one bold, rounded, open-license font bundled in the repository.

## 7. From photo to print file

1. **Read the card:** find the markers, straighten and crop the photo, get the exact scale, read the card type and number. If the markers are not found, use the fallback above.
2. **Clean:** even out lighting and shadows, then remove the paper and the printed guides.
3. **Separate the inks:** every distinct ink color in the drawing becomes its own part, so the file shows the color separation. Colors are told apart mostly by hue: a streaky fill of one marker stays one color, an orange next to a yellow stays two. Up to 3 ink colors plus the white base (one AMS); a fourth merges into its nearest and the preview says so. Paper areas inside the outline become the base color.
4. **Shape:** the outer edge of all the ink, filled in, is the piece's outline.
5. **Fix for printing**, and log every fix for the preview:
   - Ink areas narrower than 1.0 mm at real size get thickened. Specks smaller than about 1 square mm are removed. Tiny holes are filled.
   - The outline gets a border, 1.5 mm by default, in the base color, like the white edge on a die-cut sticker. It joins separate pieces into one and protects thin bits like whiskers and sun rays. On by default for everyone; a setting turns it off.
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

- **Color is Allen's call in Bambu Studio.** The file's job is to keep each color a separate, clearly named part ("clip-03 black", "clip-03 pink"). He assigns spools in Bambu Studio afterwards. The run never stops to ask about colors.
- **Loaded slots (optional head start):** config can record which spool is in which AMS slot. When it does, each color part starts on the nearest loaded spool, and the preview says when two parts start on the same spool. Allen can also override in plain words ("card 3's pink should be Magenta").
- **Optional extras, off the main path:** the marker calibration card (sharper matching), a strict mode that stops and asks about colors that aren't loaded, swap plates for spools that aren't loaded, and the filament chip plate for a printer tour.
- **Plate planner:** pack many designs onto each plate, at most N filaments per plate (setting, default 4, one AMS). Because the colors sit only in the first few layers, a full plate costs little extra purge.
- **Orientation:** design pieces face-down (including magnet figures); clicker cases upright; keycaps face-down with the socket up; stands in whatever orientation needs no supports. Give clicker cases and stands their own plates if their best layer heights differ from the charms'.
- **Print notes** with every output: suggested layer height (0.12 mm for charms, figures and earrings, 0.2 mm for clicker cases and stands), and plate choice (the smooth plate gives a glossy face, the textured plate a matte, sparkly face).

## 9. Build order

Finish and show each milestone before starting the next. Each ends with something Allen can print or hold.

**Milestone 0: fit test.** One small single-color plate with numbered test pieces: coupons with the three clip pocket sizes, three keyring hole sizes, three earring loops (sideways holes), three MX switch cutout coupons with the 1.5 mm plate, three keycap stem sockets, three necklace loops (sideways holes), and one figure stand with its washer recess. Give Allen numbered steps: print it, then try the real clip pad, a switch, a keycap stem test, a split ring, an earring hook, a necklace chain, and a magnet glued onto a coupon (checked on the fridge and on the stand with a washer). He reports which numbers fit, and you write the results into config. Done when config holds tested values.

**Milestone 1: cards, hair clips and keychains.** The card PDF (clip and keychain cards first), the reader, the full pipeline, previews and 3MF export. Done when Allen scans a test card with the iPhone Notes document scanner, uploads it, gets a file that opens in Bambu Studio and prints, and the charm sits on the real clip.

**Milestone 2: party batch.** A folder of photos becomes packed plates in one go, with the contact sheet, filament mapping and overrides, and the half-drawn card set. Also the loaded-palette pieces: loaded slots in config, the marker calibration card, the off-palette question, the filament chip plate, and the new kid card rule text. Done when eight cards become plates in one request and the chip plate slices under about 15 minutes.

**Milestone 3: clicker.** Case, keycap and the glue-on fallback. Done when a real switch snaps in, clicks freely, and the keycap stays on.

**Milestone 4: adults.** PNG and SVG input and the text mode (earring and pendant cards are already built). Done when an iPad drawing becomes a printed earring pair.

**Milestone 5: magnet figures and the stand.** The figure card (built: flat back, glued magnet), the stand, and the print notes. Done when a printed figure with a glued magnet holds on the fridge and stands on the stand. Ask Allen whether magnet figures are needed for the party; if yes, build this right after milestone 2.

If Allen gives a party date, reorder to fit it. The party needs milestones 0 to 2 at minimum.

## 10. Everyday runbook (copy into CLAUDE.md)

When Allen uploads photos or images:

1. Run the pipeline on all of them. Do not ask which product if the cards say it.
2. Show the contact sheet. In plain words, list the fixes and anything you were unsure of.
3. Ask only if a card is unreadable. Do not ask about colors: every color is its own part, and Allen assigns spools in Bambu Studio.
4. Hand over the plate files and say, for each plate, which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clips, studs, magnets), rings (keychains), hooks and chains straight through the loop (earrings, pendants), switch insertion (clickers).

When Allen says he swapped a spool ("pink is in slot 3 now"): update the loaded slots in config.

## 11. For Allen: things to have on hand

- **Glue:** gel super glue for magnets and clips, E6000 as an alternative for the clip pads, and optionally two-part epoxy for magnets that pop out. Test on the clip pad first; some plastics resist glue, and a light scuff with sandpaper helps. Glue in a ventilated room, adults only, and let it cure fully (E6000 needs about a day) before kids use the pieces.
- **Rings and findings:** 25 mm split key rings, earring hooks, glue-on stud posts with flat pads (hypoallergenic metal), necklace chains or cord thin enough to pass a 3.5 mm hole.
- **Magnets and washers:** 10 × 2 mm neodymium disc magnets, glued onto the flat back; 1-inch zinc-plated steel fender washers for the stands. Many stainless steel washers are not magnetic.
- **Switches:** the blue clicky switches (have).
- **Markers:** broad-tip markers, ideally one per loaded color so prints look like the drawings. White needs no marker: it is the paper.
- **Optional:** a cheap digital caliper makes the fit tests and pad measurement easier.
- **Safety:** glued charms and magnets are small parts. Check every glue joint before handing a piece over, and keep any magnet that pops loose away from young children.

## 12. Parked on purpose

Do not build these unless Allen asks:

- AI image-to-3D figurines (such as Meshy in MakerLab). That is a separate project; the figurine style (section 5) is the non-AI version.
- Lithophanes, more than 4 colors.
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
