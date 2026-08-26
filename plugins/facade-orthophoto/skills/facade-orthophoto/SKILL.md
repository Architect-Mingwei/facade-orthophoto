---
name: facade-orthophoto
description: Generate a seamless, metric ortho-elevation (正射立面) of a building facade from overlapping photos using COLMAP/pycolmap, with automatic quality checks (level/plumb lines, uniform brightness, full coverage, sharpness, invisible seams) and parameter adjustments. Use when the user wants a rectified, scale-true facade image stitched from multiple facade photos.
---

# Facade orthophoto

Turn a folder of overlapping facade photos into a single seamless, metric,
frontal ortho-elevation. The default parameters are a starting point, not a
recipe: after each run, read the printed metrics, diagnose which check fails,
and adjust the corresponding knob until the result is seamless, uniformly
bright, level/plumb, fully covered, and sharp.

## Quick example

```bash
python scripts/facade_ortho.py --image_dir ./photos --output_dir ./out
```

Then read the `[final]` metrics and tune `--bands` / `--seam_scale` until the
checks in [references/quality_checks.md](references/quality_checks.md) pass.

## Workflow

1. Confirm dependencies: `pip install pycolmap opencv-python-headless==4.10 numpy`.
   The `cv2.detail` stitching module is broken in some OpenCV 5.x wheels, so pin
   to 4.x.
2. Run the pipeline:

   ```bash
   python scripts/facade_ortho.py \
     --image_dir /path/to/photos \
     --output_dir /path/to/output \
     [--bands 7] [--seam_scale 0.25] [--max_width 9000] \
     [--texture_filter DSC] [--skip_sfm]
   ```

   It copies photos to ASCII filenames, runs SfM, fits the facade plane,
   warps every photo onto the plane, applies brightness normalization,
   graph-cut seam finding, multi-band blending, deskew, and cropping.
3. Read the `[final]` metrics block it prints.
4. If a check fails, adjust and re-run (usually with `--skip_sfm` to avoid
   recomputing SfM). Use the detailed thresholds and the exact knob to change
   in [references/quality_checks.md](references/quality_checks.md).
5. If the user reports a visual seam problem, tune `--bands`/`--seam_scale` one
   knob at a time: blurry seams -> fewer bands; faint hard lines -> more bands.

## Key decisions

- Exclude a low-resolution full-view reference photo from texturing
  (`--texture_filter`), otherwise it dominates and softens the result.
- Facade relief (windows, columns) causes parallax, so a mathematically perfect
  seamless ortho is not possible without dense reconstruction (CUDA). Aim for
  the best blur-vs-line balance, and say so plainly if it is the limiting case.

## Files

- `scripts/facade_ortho.py` — the full pipeline (prints quality metrics).
- `scripts/check_ortho.py` — re-check an existing ortho image.
- `references/quality_checks.md` — metric thresholds and which knob to adjust.
