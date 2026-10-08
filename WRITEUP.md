# Writeup

## Approach

Detection uses classical image processing with OpenCV. There is no trained model.

1. **Ink mask.** Each pixel is reduced to the maximum of its three color channels, then thresholded with Otsu's method. Tinted backgrounds, colored stamps, and colored pen ink have at least one high channel and read as paper; only black and gray read as ink.
2. **Straight strokes.** A morphological opening with horizontal and vertical 12 px kernels keeps box borders and table rules, and removes diagonal marks and most text. After this step, a marked box looks the same as an empty one.
3. **Enclosed regions.** A checkbox is a paper region, roughly rectangular, fully enclosed by straight strokes and with a thin border. It must be 15 to 120 px per side and close to square: width / height from 0.7 to 1.5.
4. **Typical size.** The boxes on a page share a size. Candidates are grouped by similar width and height, and the group that covers the most area is kept; the rest are discarded.
5. **Classification.** A box is marked when more than 8% of its interior is ink, measured after skipping 20% on each side so the border does not count.

I annotated the 288 checkboxes in the four samples by hand before writing the detector, and chose each step by measuring against them. The scripts are in `experiments/`.

## Why this and not something else

- **A trained detector.** There are four images. That is enough to tune a few thresholds, not to train and validate a model.
- **A vision language model.** Its coordinates are approximate; the same image can give different answers, and a reviewer would need an API key to run the project.
- **Connected components or contours on the raw ink.** I measured both. Looking for rectangular blobs found 214 of 288 boxes, because boxes attached to table rules merge into one blob. Looking for enclosed regions on the raw ink found 241, because an X that touches the border splits the interior into four. Removing the diagonal strokes first solved both and found 285.

## Tradeoffs

- **Two services.** One Python service would have been enough for this scope. I split it so that the public side is Go and does real work before any image is decoded: it checks the format from the file's bytes, enforces size limits, caps concurrent requests and cancels the worker call when the client disconnects. The cost is a second service and an internal contract to keep in sync.
- **Rules instead of learning.** Every decision can be traced to a threshold, and the result is deterministic. The price is that a checkbox is defined solely by its geometry, which leads to most of the limitations below.
- **Fixed pixel sizes.** The 12 px stroke length worked for boxes from 16 to 57 px, and the 15 px minimum side sits between the largest letter interior seen (14 px at 300 DPI) and the smallest checkbox (16 px). Both are tied to resolution: a scan far from 150 to 300 DPI would need them scaled.

## Results

`docker compose run --rm eval` prints the full table on the four samples: 285 of 288 boxes found, one false detection, and 284 of 285 labels correct. Detection takes between 50 and 330 ms per sample on a CPU.

The detection parameters were tuned on the same images, so these numbers are upper bounds. The classification threshold is less of a concern: empty boxes measure 0.000 ink, and the faintest mark measures 0.156 ink, so a threshold chosen on any three images will classify the fourth image in the same way, apart from the two cases listed below.

To check that, I annotated seven more pages from public forms, 168 checkboxes, in three rounds. Each round was run once, on pages the detector had not seen.

1. Two pages of the Fannie Mae loan application, one at 150 DPI, and IRS form SS-4. The loan application gave 36 of 36. The SS-4 gave 0 of 44: every checkbox was found as a candidate, but the enclosed regions inside letters such as b, d and p formed a group just as numerous, 44 against 44, and the typical-size step kept the letters.
2. I changed that step to keep the group that covers the most area instead of the one with the most members, which fixed the SS-4, and ran IRS forms 1040 and W-9. They gave 0 of 61. The step now kept label cells and digit cells, which are few but large.
3. The cause was earlier in the pipeline. The shape limits accepted any region from 12 px and from 0.6 to 1.8 in width / height, far looser than a real checkbox, which measures 0.94 to 1.27 on every page. I tightened them to 15 px and 0.7 to 1.5 and ran USCIS form I-9 and VA form 26-1880: 27 of 27, every label correct, no false detections.

With the final parameters the seven pages give 168 of 168 and the four samples are unchanged. Only the 27 boxes of the last round count as unseen; the other five pages were used to find the problem or to choose the values. `docker compose run --rm eval` prints both tables.

## Known limitations

On the samples:

- **A very faint box is missed** (`sample2`, "Neighborhood Boundaries"). Otsu sets one threshold per page, and the box border is much lighter than the rest of the ink.
- **A box whose border is broken is missed.** In `sample2`, a scribble erased 3 px of the border, and in `sample4` a red watermark replaces a corner. Either way, the region is no longer enclosed.
- **A pen stroke through an empty box reads as marked** (`sample2`, "No Zoning"). Classification counts ink and does not look at shape.
- **The crossed-out X in `sample2` is ambiguous.** I annotated it as unmarked because the person tried to cancel it. An ink ratio cannot tell the two apart.
- **One false detection in `sample1`.** A gap between two neighboring boxes is itself an enclosed rectangle of the right size.

On six synthetic forms I made to probe specific cases, which are not annotated:

- **Square character fields are detected as checkboxes.** A row of small squares holding one digit each is geometrically identical to a row of checkboxes.
- **A box that is filled in completely is missed.** There is no paper left inside it to enclose. The same property is what keeps solid square bullets out.
- A pale, translucent stamp over a box and a skew of about 2 degrees caused no errors. A stamp in dark ink or a larger skew would.

On the public forms:

- **The typical-size step keeps one group per page.** A page with checkboxes of two sizes loses the smaller ones, and a page with few checkboxes and many other square regions of 15 px or more could lose them all. This is the step that failed on the SS-4, the 1040 and the W-9 before the shape limits were tightened.
- **Round option buttons are not detected.** The loan application has them next to the checkboxes and none was returned. The detector only follows straight strokes.
- **Checkboxes under 15 px, or far from square, are rejected.**
- **Tall digit cells are rejected; square ones would not be.** The digit cells of the W-9 measure 0.60 in width / height and fall below the aspect limit.

## What I would do next

- Straighten the page before detection, to tolerate skewed scans.
- Use context to recover boxes the geometry misses: a solid blob or a three-sided box of the typical size, aligned with detected boxes, is very likely a checkbox.
- Collect and annotate real forms. The cases that depend on mark meaning, such as a crossed-out X or a digit in a square, require a trained classifier and its data.
- Accept PDF by rendering each page before detection, and read the form fields directly when the PDF already has them.
- Run the stroke step a second time with the stroke length scaled to the box size found, so that letter interiors are removed by geometry instead of by a pixel limit.
- Validate on more unseen pages. Twenty-seven boxes on two pages show the last change was not fitted to one form; they do not show it works on any form.
