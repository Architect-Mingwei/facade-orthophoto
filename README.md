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

### Method 1: add this repository as a plugin marketplace

```bash
codex plugin marketplace add Architect-Mingwei/facade-orthophoto
codex plugin add facade-orthophoto@facade-orthophoto
```

The marketplace and the plugin are both named `facade-orthophoto`, so the
selector above reads `PLUGIN@MARKETPLACE`. You can also add the marketplace
with `codex plugin marketplace add ./facade-orthophoto` after cloning, or add
it in the Codex app and install the plugin from there.

### Method 2: install the skill without the plugin

The skill itself lives at `plugins/facade-orthophoto/skills/facade-orthophoto/`.
Copy that folder into your skills directory, which defaults to
`$CODEX_HOME/skills` (`~/.codex/skills`):

```bash
git clone --depth 1 https://github.com/Architect-Mingwei/facade-orthophoto.git
mkdir -p ~/.codex/skills
cp -R facade-orthophoto/plugins/facade-orthophoto/skills/facade-orthophoto \
  ~/.codex/skills/
```

On Windows PowerShell the same two steps are `New-Item -ItemType Directory` and
`Copy-Item -Recurse` into `$env:CODEX_HOME\skills` (default
`$HOME\.codex\skills`).

If you have the `skill-installer` skill, the equivalent fetch is:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo Architect-Mingwei/facade-orthophoto \
  --path plugins/facade-orthophoto/skills/facade-orthophoto
```

Either way the skill is available as `facade-orthophoto` (or triggers on
requests like "make a facade ortho-elevation from these photos").

## Usage

Put overlapping facade photos in one folder (roughly 70%+ overlap works best),
then run:

```bash
python plugins/facade-orthophoto/skills/facade-orthophoto/scripts/facade_ortho.py \
  --image_dir ./facade_photos \
  --output_dir ./out
```

Re-runs that only tune blending can skip SfM:

```bash
python plugins/facade-orthophoto/skills/facade-orthophoto/scripts/facade_ortho.py \
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
[`references/quality_checks.md`](plugins/facade-orthophoto/skills/facade-orthophoto/references/quality_checks.md).

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
