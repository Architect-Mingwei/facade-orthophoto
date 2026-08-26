# Facade Orthophoto

Generate a seamless, metric ortho-elevation (正射立面) of a building facade from
overlapping photos. Built on COLMAP/pycolmap, with automatic quality checks for
level/plumb lines, uniform brightness, full coverage, sharpness, and invisible
seams.

## Example

![Example facade ortho-elevation](assets/example-facade-orthophoto.jpg)

The pipeline stitches several overlapping facade photos into one frontal,
scale-true image, then deskews it so facade lines are horizontal and vertical.

## Prerequisites

- Python 3.10+
- `pycolmap` (COLMAP Python bindings)
- `opencv-python-headless==4.10` (the stitching module is broken in some 5.x
  wheels, so pin to 4.x)
- `numpy`

```bash
pip install pycolmap opencv-python-headless==4.10 numpy
```

> Dense reconstruction (true per-pixel depth) requires an NVIDIA GPU and CUDA.
> This skill works on CPU using a planar facade model, which is enough for
> most flat facades. Facade relief (windows, columns) causes small parallax
> seams that are minimized, but not mathematically eliminated, without dense
> reconstruction.

## Installation

### Method 1: install the skill directly

```bash
codex skill install facade-orthophoto \
  --repo Architect-Mingwei/facade-orthophoto \
  --path skills/facade-orthophoto
```

After installation, the skill is available as `facade-orthophoto` (or triggers
on requests like "make a facade ortho-elevation from these photos").

### Method 2: add this repository as a plugin marketplace

```bash
git clone https://github.com/Architect-Mingwei/facade-orthophoto.git
codex plugin marketplace add ./facade-orthophoto
```

Then install the `facade-orthophoto` plugin from the marketplace in the Codex
app.

## Usage

Put overlapping facade photos in one folder (roughly 70%+ overlap works best),
then run:

```bash
python skills/facade-orthophoto/scripts/facade_ortho.py \
  --image_dir ./facade_photos \
  --output_dir ./out
```

Re-runs that only tune blending can skip SfM:

```bash
python skills/facade-orthophoto/scripts/facade_ortho.py \
  --image_dir ./facade_photos \
  --output_dir ./out \
  --skip_sfm --bands 5 --seam_scale 0.25
```

The script prints a `[final]` metrics block. Check and adjust rather than
treating the defaults as fixed:

- `coverage` should be ~100%.
- `brightness L/M/R` should be close (no dark side).
- `line_dev H/V` should be near 0 deg (level/plumb).
- `sharpness` should be high (low values mean a low-resolution photo is
  dominating, the homography direction is wrong, or the output is oversampled).
- For seams: blurry -> lower `--bands`; faint hard line -> raise `--bands`; use
  `--seam_scale` for finer/coarser seam placement.

Full thresholds and the exact knob for each failure are in
[`skills/facade-orthophoto/references/quality_checks.md`](skills/facade-orthophoto/references/quality_checks.md).

## Repository layout

```
.
├── LICENSE
├── README.md
├── assets/
│   └── example-facade-orthophoto.jpg
├── .agents/plugins/marketplace.json   # marketplace entry for this repo
└── plugins/facade-orthophoto/         # the Codex plugin
    ├── .codex-plugin/plugin.json
    └── skills/facade-orthophoto/
        ├── SKILL.md
        ├── scripts/
        │   ├── facade_ortho.py
        │   └── check_ortho.py
        └── references/
            └── quality_checks.md
```

## License

[MIT](LICENSE)
