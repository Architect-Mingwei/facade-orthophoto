#!/usr/bin/env python3
"""Check an existing ortho-facade image and print the same quality metrics."""

import argparse
import numpy as np
import cv2


def line_devs(img, maxdim=1800):
    h, w = img.shape[:2]
    s = maxdim / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (5, 5), 1.0)
    e = cv2.Canny(g, 50, 180)
    lines = cv2.HoughLinesP(e, 1, np.pi / 180, threshold=80, minLineLength=80, maxLineGap=8)
    hd, vd = [], []
    if lines is not None:
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            a = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180.0
            d = a if a <= 90 else a - 180.0
            (hd if abs(d) < 45 else vd).append(d)
    vd = [x - 90 if x > 0 else x + 90 for x in vd]
    return (float(np.median(hd)) if hd else 0.0,
            float(np.median(vd)) if vd else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    args = ap.parse_args()
    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"cannot read {args.image}")
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    mask = g > 3
    cov = 100.0 * mask.mean()
    lap = cv2.Laplacian(g, cv2.CV_64F).var()
    lm = g[:, : w // 4][mask[:, : w // 4]].mean()
    mm = g[:, w // 2 - w // 8 : w // 2 + w // 8][mask[:, w // 2 - w // 8 : w // 2 + w // 8]].mean()
    rm = g[:, 3 * w // 4 :][mask[:, 3 * w // 4 :]].mean()
    hd, vd = line_devs(img)
    # column brightness profile for detecting dark/light bands or edges
    cols = g.mean(axis=0)
    edges = [round(float(cols[min(int(f * (w - 1)), w - 1)]), 1) for f in (0, 0.2, 0.5, 0.8, 1.0)]
    print(f"size={w}x{h}")
    print(f"coverage={cov:.1f}%  sharpness={lap:.1f}")
    print(f"brightness L/M/R = {lm:.1f}/{mm:.1f}/{rm:.1f}")
    print(f"column brightness @0/0.2/0.5/0.8/1.0 = {edges}")
    print(f"line deviation H/V = {hd:.2f}/{vd:.2f} deg")


if __name__ == "__main__":
    main()
