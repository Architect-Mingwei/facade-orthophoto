# Facade ortho: quality checks and adjustments

Run the pipeline, then read the printed metrics (or re-check an existing image
with `scripts/check_ortho.py <image>`). Do NOT treat the default parameters as
fixed: adjust them until all checks pass. Judge in this order.

## 1. Coverage (must be ~100%)

Metric: `coverage` (fraction of non-black pixels).

- If a whole side/edge is black, the facade extent is wider than the photos
  cover, or an image was skipped. Check:
  - `--texture_filter` is not accidentally excluding needed images.
  - The photos actually overlap the missing area (the facade may need more
    photos).
- Small black borders after the deskew rotation are normal and are cropped.

## 2. Brightness uniformity (no obvious dark bands)

Metrics: `brightness L/M/R` and the `column brightness` profile.

- Left/middle/right means should be close (roughly within ~30%). The column
  profile should not have a large step or a dark half.
- A dark side usually means one or more source photos were underexposed. The
  per-image brightness normalization handles most of it; if a side is still
  dark, prefer more-evenly exposed source photos or add local brightness
  correction (for example, a gentle horizontal equalization of the final image).

## 3. Level / plumb lines ("heng ping shu zhi")

Metric: `line deviation H/V` (median angular deviation of detected horizontal
and vertical lines, in degrees). Both should be close to 0 (typically <= ~1).

- The deskew step rotates by the dominant skew angle automatically. If H/V are
  still off, the facade plane "up" axis may be wrong; check that camera poses
  are sensible and re-run.

## 4. Sharpness

Metric: `sharpness` (Laplacian variance of the gray image).

- Very low (< ~40) usually means the image is smeared/blurry. Common causes:
  - A low-resolution overview/reference photo is being used as a texture and
    dominating (exclude it with `--texture_filter`, or remove it).
  - The homography direction is wrong (must be image->ortho).
  - The output resolution is finer than the source photos' native GSD.
- Sharpness above ~150 is generally good; values ~100-150 are acceptable if
  the facade itself is smooth.

## 5. Seams (the main tradeoff)

There is no single right value for `--bands` and `--seam_scale`. Facades have
relief (windows, columns), so adjacent photos disagree slightly at seams
(parallax). The knobs trade off "blur" vs "faint line":

- Seams look **blurry/soft**: lower `--bands` (e.g. 7 -> 5 -> 3) so the
  multi-band transition is narrower.
- Seams show a **faint hard line**: raise `--bands` (3 -> 5 -> 7), or lower
  `--seam_scale` (0.5 -> 0.25) to make the graph-cut seam coarser but smoother.
- `--seam_scale` controls graph-cut resolution: higher is more precise but
  slower; 0.25 is a good default, 0.5 when seams need finer placement.

Start from `--bands 7 --seam_scale 0.25` and adjust toward the middle based on
the user's feedback. Never change both knobs at once when tuning.

## Non-obvious implementation invariants

- `cv2.warpPerspective(src, H, dsize)` treats `H` as the source->destination
  transform. To warp an image onto the ortho grid, build
  `H = cv2.getPerspectiveTransform(image_corners, ortho_corners)` (image->ortho).
- `cv2.detail.MultiBandBlender` requires `prepare((x, y, w, h))` (a 4-element
  rect) **before** `feed()`, and needs OpenCV 4.x (the 5.x detail module is
  broken in some wheels).
- `pycolmap` cannot read non-ASCII image paths on Windows; copy to ASCII names.
- Photos with different focal lengths must use `CameraMode.AUTO` so each gets
  its own intrinsics.
- Deskew rotation sign: rotate by `+theta` where theta is the circular mean of
  `4 * line_angle`; rotating by `-theta` doubles the tilt.
- Prefer per-image channel-mean normalization for brightness; OpenCV's
  `ExposureCompensator` can produce dark/soft results in some builds.
