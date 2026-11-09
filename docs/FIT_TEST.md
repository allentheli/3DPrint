# Fit test (milestone 0)

Print this plate once, try the real hardware on every numbered piece, and tell
Claude which number fits best in each group. There are 18 numbered coupons and one
figure stand.

## 1. Print it

1. Open Bambu Studio.
2. Click **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...** and pick `fit-test.3mf`.
   If Bambu Studio asks whether to load it as a project or geometry, choose **Load geometry only**.
3. Leave every piece where it lands. If any piece is off the plate, click **Arrange** (the A key).
4. In the **Process** panel set **Layer height** to **0.12 mm**. Supports stay **off**.
5. Pick any one filament. Click **Slice plate**, then **Print plate**, and send it to the printer as usual.
6. When it is done, pop the pieces off. Every piece has its number raised on the top face.

## 2. Try the hardware

### 1. Hair clip pad pocket

| Piece | Tests |
| --- | --- |
| **1** | clip pad pocket 11.2 mm, 0.6 mm deep |
| **2** | clip pad pocket 11.5 mm, 0.6 mm deep |
| **3** | clip pad pocket 11.8 mm, 0.6 mm deep |

Press the clip's round pad into each pocket. Best = snug, pad fully seated, no rocking.

### 2. Split-ring hole

| Piece | Tests |
| --- | --- |
| **4** | split-ring hole 4.5 mm |
| **5** | split-ring hole 5.0 mm |
| **6** | split-ring hole 5.5 mm |

Thread a 25 mm split key ring through each hole. Best = goes on without forcing and turns freely.

### 3. Jump-ring hole

| Piece | Tests |
| --- | --- |
| **7** | jump-ring hole 1.8 mm |
| **8** | jump-ring hole 2.0 mm |
| **9** | jump-ring hole 2.3 mm |

Open a jump ring and pass it through each hole. Best = passes easily; the smallest that does.

### 4. Magnet pocket

| Piece | Tests |
| --- | --- |
| **10** | magnet pocket 10.2 mm, 1.9 mm deep |
| **11** | magnet pocket 10.4 mm, 1.9 mm deep |
| **12** | magnet pocket 10.6 mm, 1.9 mm deep |

Push a 10 x 2 mm magnet into each pocket. Best = snug, sits a hair proud, does not fall out upside down.

### 5. Switch cutout

| Piece | Tests |
| --- | --- |
| **13** | switch cutout 13.9 mm square in a 1.5 mm plate |
| **14** | switch cutout 14.0 mm square in a 1.5 mm plate |
| **15** | switch cutout 14.1 mm square in a 1.5 mm plate |

Push a switch into each square from the top until it clicks. Best = snaps in, no wobble, can be pulled out with effort.

### 6. Keycap stem socket

| Piece | Tests |
| --- | --- |
| **16** | stem socket arms 1.32 x 1.46 mm (clearance 0.15 mm) |
| **17** | stem socket arms 1.42 x 1.56 mm (clearance 0.25 mm) |
| **18** | stem socket arms 1.52 x 1.66 mm (clearance 0.35 mm) |

Press each boss onto a switch stem. Best = firm push-on, stays on when you shake it, comes off with a pull.

### 7. Stand and washer

1. Put a 1 inch zinc-plated steel fender washer into the round recess on the back of the stand's upright.
   It should drop in and sit flush or just below the surface. Glue it with gel super glue.
2. Glue a magnet into the best magnet pocket (from step 4) with gel super glue. Let it cure.
3. Stick that piece on the fridge. It should hold its own weight. Note the magnet sits about 0.1 mm proud, on purpose.
4. Stand the same piece on the stand, pocket side toward the upright, bottom edge in the slot behind the lip.
   It should snap gently to the upright and stay standing.

## 3. Report

Tell Claude one number per group, for example:

> clip 2, keyring 5, jump ring 8, magnet 11, switch 14, stem 17. Washer fits. Fridge and stand hold.

If nothing fits in a group, say whether everything was too tight or too loose, and Claude
will make a second plate with new sizes. Claude then runs `python -m charm_maker fit-results`
and the values go into `config.yaml`.

## Legend

| Group | Pieces | Candidates (mm) |
| --- | --- | --- |
| Hair clip pad pocket | 1, 2, 3 | 11.2, 11.5, 11.8 |
| Split-ring hole | 4, 5, 6 | 4.5, 5.0, 5.5 |
| Jump-ring hole | 7, 8, 9 | 1.8, 2.0, 2.3 |
| Magnet pocket | 10, 11, 12 | 10.2, 10.4, 10.6 |
| Switch cutout | 13, 14, 15 | 13.9, 14.0, 14.1 |
| Keycap stem socket | 16, 17, 18 | 0.15, 0.25, 0.35 |
