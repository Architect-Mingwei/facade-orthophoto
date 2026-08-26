#!/usr/bin/env python3
"""Build a seamless, metric facade ortho-elevation from overlapping photos.

The pipeline is intentionally NOT a fixed recipe: it prints quality metrics so
an agent can check them and re-run with adjusted parameters (see references/
quality_checks.md). The main adjustment knobs are exposed as CLI flags.
"""

import argparse
import os
import re
import shutil
import sys

import numpy as np
import cv2

try:
    import pycolmap
except ImportError:
    sys.exit("pycolmap is required: pip install pycolmap")


def sanitize_images(image_dir, work_dir):
    """Copy images to ASCII filenames (pycolmap breaks on non-ASCII paths)."""
    src_dir = os.path.abspath(image_dir)
    dst_dir = os.path.join(work_dir, "images")
    os.makedirs(dst_dir, exist_ok=True)
    exts = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
    names = []
    for i, fn in enumerate(sorted(os.listdir(src_dir)), 1):
        if not fn.lower().endswith(exts):
            continue
        ext = os.path.splitext(fn)[1].lower()
        new_name = f"img_{i:04d}{ext}"
        shutil.copy2(os.path.join(src_dir, fn), os.path.join(dst_dir, new_name))
        names.append(new_name)
    if not names:
        sys.exit(f"no images found in {src_dir}")
    return dst_dir, names


def run_sfm(image_dir, names, work_dir):
    db = os.path.join(work_dir, "database.db")
    sparse = os.path.join(work_dir, "sparse_bin")
    os.makedirs(sparse, exist_ok=True)
    # AUTO so images with different focal lengths get separate intrinsics
    pycolmap.extract_features(db, image_dir, image_names=names,
                              camera_mode=pycolmap.CameraMode.AUTO,
                              device=pycolmap.Device.cpu)
    pycolmap.match_exhaustive(db)
    recs = pycolmap.incremental_mapping(db, image_dir, work_dir)
    best = max(recs.values(), key=lambda r: r.num_reg_images())
    best.write_binary(sparse)
    return sparse, best.num_reg_images(), len(names)


def ransac_plane(P, n_iter=4000, thresh_ratio=0.03, seed=0):
    N = len(P)
    centroid = P.mean(axis=0)
    scale = float(np.median(np.linalg.norm(P - centroid, axis=1)))
    thresh = max(thresh_ratio * scale, 1e-9)
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_iter):
        idx = rng.choice(N, 3, replace=False)
        p0, p1, p2 = P[idx]
        nn = np.cross(p1 - p0, p2 - p0)
        nl = np.linalg.norm(nn)
        if nl < 1e-12:
            continue
        nn = nn / nl
        d = (P - p0) @ nn
        inl = np.abs(d) <= thresh
        cnt = int(inl.sum())
        if best is None or cnt > best[0]:
            best = (cnt, nn, inl)
    _, _, inl = best
    center = P[inl].mean(axis=0)
    C = P[inl] - center
    _, _, Vt = np.linalg.svd(C, full_matrices=False)
    n = Vt[-1]
    n = n / np.linalg.norm(n)
    return center, n, inl


def skew_angle(img, maxdim=1800):
    h, w = img.shape[:2]
    s = maxdim / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (5, 5), 1.0)
    e = cv2.Canny(g, 50, 180)
    lines = cv2.HoughLinesP(e, 1, np.pi / 180, threshold=80, minLineLength=80, maxLineGap=8)
    if lines is None:
        return 0.0
    ss = cc = 0.0
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        a = np.radians((np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180.0) * 4.0)
        ln = float(np.hypot(x2 - x1, y2 - y1))
        ss += ln * np.sin(a)
        cc += ln * np.cos(a)
    return 0.25 * np.degrees(np.arctan2(ss, cc))


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


def report_metrics(ortho, label):
    g = cv2.cvtColor(ortho, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    mask = g > 3
    cov = 100.0 * mask.mean()
    lap = cv2.Laplacian(g, cv2.CV_64F).var()
    lm = g[:, : w // 4][mask[:, : w // 4]].mean()
    mm = g[:, w // 2 - w // 8 : w // 2 + w // 8][mask[:, w // 2 - w // 8 : w // 2 + w // 8]].mean()
    rm = g[:, 3 * w // 4 :][mask[:, 3 * w // 4 :]].mean()
    hd, vd = line_devs(ortho)
    print(f"[{label}] size={w}x{h} coverage={cov:.1f}% sharpness={lap:.1f}")
    print(f"[{label}] brightness L/M/R={lm:.1f}/{mm:.1f}/{rm:.1f}  line_dev H/V={hd:.2f}/{vd:.2f} deg")


def build_ortho(recon, image_dir, out_path, bands=7, seam_scale=0.25,
                max_px=9000, texture_filter=""):
    P = np.vstack([np.asarray(p.xyz, dtype=np.float64) for p in recon.points3D.values()])
    center, n, inl = ransac_plane(P)

    ups, ccs = [], []
    for im in recon.images.values():
        if im.has_pose:
            R = im.cam_from_world().rotation.matrix()
            t = im.cam_from_world().translation
            ups.append(-R[1])
            ccs.append(-R.T @ t)
    avg_up = np.mean(np.asarray(ups), axis=0)
    avg_up /= np.linalg.norm(avg_up)
    mc = np.mean(np.asarray(ccs), axis=0)
    if float((mc - center) @ n) < 0:
        n = -n
    v = avg_up - (avg_up @ n) * n
    v /= np.linalg.norm(v)
    u = np.cross(v, n)
    u /= np.linalg.norm(u)

    px = (P[inl] - center) @ u
    py = (P[inl] - center) @ v
    xmin, xmax = px.min(), px.max()
    ymin, ymax = py.min(), py.max()
    pad = 0.03
    xmin -= (xmax - xmin) * pad; xmax += (xmax - xmin) * pad
    ymin -= (ymax - ymin) * pad; ymax += (ymax - ymin) * pad

    med_d = float(np.median([abs(float((cc - center) @ n)) for cc in ccs]))
    res = med_d / 5000.0
    if max(xmax - xmin, ymax - ymin) / res > max_px:
        res = max(xmax - xmin, ymax - ymin) / max_px
    W = int(np.ceil((xmax - xmin) / res))
    H = int(np.ceil((ymax - ymin) / res))

    warped, masks = [], []
    for im in recon.images.values():
        if not im.has_pose:
            continue
        if texture_filter and texture_filter not in im.name:
            continue
        img = cv2.imread(os.path.join(image_dir, im.name))
        if img is None:
            continue
        cam = im.camera
        K = cam.calibration_matrix().astype(np.float64)
        f, cx, cy = cam.focal_length, cam.principal_point_x, cam.principal_point_y
        k1 = cam.params[3] if len(cam.params) >= 4 else 0.0
        img = cv2.undistort(img, K, np.array([k1, 0, 0, 0], dtype=np.float64), None, K)
        R = im.cam_from_world().rotation.matrix()
        t = im.cam_from_world().translation

        def o2i(c, r):
            x = xmin + (c + 0.5) * res
            y = ymax - (r + 0.5) * res
            Pw = center + x * u + y * v
            camv = R @ Pw + t
            z = camv[2]
            if z <= 1e-9:
                return None
            return (f * camv[0] / z + cx, f * camv[1] / z + cy)

        src = np.float32([[0, 0], [W - 1, 0], [0, H - 1], [W - 1, H - 1]])
        dst = []
        for c, r in src:
            q = o2i(float(c), float(r))
            if q is None:
                break
            dst.append(q)
        if len(dst) != 4:
            continue
        # image -> ortho (source -> destination) is the correct direction for warpPerspective
        Hm = cv2.getPerspectiveTransform(np.float32(dst), src)
        wimg = cv2.warpPerspective(img, Hm, (W, H), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        m = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), Hm, (W, H),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        warped.append(wimg)
        masks.append(m)

    n = len(warped)
    if n == 0:
        raise RuntimeError("no images to texture")

    # per-image brightness normalization (equalize channel means)
    means = np.array([w[m > 0].mean(axis=0) for w, m in zip(warped, masks)])
    target = np.median(means, axis=0)
    gains = target / np.maximum(means, 1.0)
    images16 = [np.clip(w.astype(np.float64) * gains[k], 0, 255).astype(np.int16)
                for k, w in enumerate(warped)]

    # graph-cut seam finding on a downscaled copy (masks are coarse but cheap)
    corners = [(0, 0)] * n
    seam_finder = cv2.detail.GraphCutSeamFinder("COST_COLOR")
    small_imgs = [cv2.resize(c.astype(np.uint8), None, fx=seam_scale, fy=seam_scale,
                             interpolation=cv2.INTER_AREA).astype(np.int16) for c in images16]
    small_masks = [cv2.resize(m, None, fx=seam_scale, fy=seam_scale,
                              interpolation=cv2.INTER_NEAREST) for m in masks]
    small_masks = seam_finder.find(small_imgs, corners, small_masks)
    seam_masks = [cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST) for m in small_masks]

    # multi-band blending; prepare() must be called before feed(), with a 4-elem rect
    blender = cv2.detail.MultiBandBlender()
    blender.setNumBands(bands)
    blender.prepare((0, 0, W, H))
    for i in range(n):
        blender.feed(images16[i], seam_masks[i], corners[i])
    dst = np.zeros((H, W, 3), dtype=np.int16)
    dst_mask = np.zeros((H, W), dtype=np.uint8)
    result, _ = blender.blend(dst, dst_mask)
    ortho = np.clip(result, 0, 255).astype(np.uint8)

    # deskew to make facade lines horizontal/vertical; rotate by +theta (not -theta)
    theta = skew_angle(ortho)
    M = cv2.getRotationMatrix2D((W / 2, H / 2), theta, 1.0)
    ortho = cv2.warpAffine(ortho, M, (W, H), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    g = cv2.cvtColor(ortho, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(g > 3)
    ortho = ortho[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cv2.imwrite(out_path, ortho)
    return ortho


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image_dir", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--skip_sfm", action="store_true")
    ap.add_argument("--bands", type=int, default=7)
    ap.add_argument("--seam_scale", type=float, default=0.25)
    ap.add_argument("--max_width", type=int, default=9000)
    ap.add_argument("--texture_filter", default="", help="only texture images whose name contains this")
    args = ap.parse_args()

    work_dir = os.path.abspath(args.output_dir)
    os.makedirs(work_dir, exist_ok=True)
    image_dir, names = sanitize_images(args.image_dir, work_dir)

    sparse = os.path.join(work_dir, "sparse_bin")
    if args.skip_sfm and os.path.isdir(sparse):
        print("skipping SfM")
    else:
        sparse, n_reg, n_tot = run_sfm(image_dir, names, work_dir)
        print(f"SfM: registered {n_reg}/{n_tot}")

    recon = pycolmap.Reconstruction()
    recon.read(sparse)
    out_path = os.path.join(work_dir, "ortho_facade.jpg")
    ortho = build_ortho(recon, image_dir, out_path, bands=args.bands,
                        seam_scale=args.seam_scale, max_px=args.max_width,
                        texture_filter=args.texture_filter)
    report_metrics(ortho, "final")
    print("saved:", out_path)


if __name__ == "__main__":
    main()
