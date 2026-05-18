"""
Generer triptyque composites [BEFORE | AFTER | DIFFx15] at 896x448px pour 15 GIMP commandes.

Usage:
    python generate_dataset_v3.py \
        --images_dir ./source_images \
        --output_dir ./data_v3 \
        --train_per_class 150 \
        --val_per_class   30

"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageChops
from tqdm import tqdm

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

TRIPTYCH_W = 896  
TRIPTYCH_H = 448  
PANEL_W    = TRIPTYCH_W // 3   
DIFF_GAIN  = 15.0             

def _clamp(v, lo=0, hi=255): return max(lo, min(hi, v))



def apply_gaussian_blur(img, p):
    radius = p.get("radius", random.randint(7, 15))
    return img.filter(ImageFilter.GaussianBlur(radius=radius)), {"radius": radius}

def apply_sharpen(img, p):
    factor = p.get("factor", round(random.uniform(3.0, 6.0), 1))
    enhancer = ImageEnhance.Sharpness(img)
    return enhancer.enhance(factor), {"factor": factor}

def apply_brightness_contrast(img, p):
    b = p.get("brightness", round(random.uniform(0.5, 2.0), 2))
    c = p.get("contrast",   round(random.uniform(0.5, 2.0), 2))
    img = ImageEnhance.Brightness(img).enhance(b)
    img = ImageEnhance.Contrast(img).enhance(c)
    # Ensure at least one param is non-trivial
    return img, {"brightness": b, "contrast": c}

def apply_hue_saturation(img, p):
    import colorsys
    sat_factor = p.get("saturation", round(random.uniform(0.1, 3.0), 2))
    # Shift hue by random degrees (0–360)
    hue_shift = p.get("hue_shift", random.randint(10, 350))
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    out = np.zeros_like(arr)
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            r, g, b = arr[y, x]
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            h = (h + hue_shift / 360.0) % 1.0
            s = min(1.0, s * sat_factor)
            out[y, x] = colorsys.hsv_to_rgb(h, s, v)
    result = Image.fromarray((out * 255).astype(np.uint8))
    if img.mode == "RGBA":
        result.putalpha(img.split()[3])
    return result, {"saturation": sat_factor, "hue_shift": hue_shift}

def apply_hue_saturation_fast(img, p):
    sat_factor = p.get("saturation", round(random.uniform(0.2, 3.0), 2))
    hue_shift  = p.get("hue_shift",  random.randint(15, 345))
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    # Convert RGB → HSV
    Cmax = arr.max(axis=2)
    Cmin = arr.min(axis=2)
    delta = Cmax - Cmin
    # Value
    V = Cmax
    # Saturation
    S = np.where(Cmax > 0, delta / Cmax, 0.0)
    # Hue
    R, G, B = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    H = np.zeros_like(R)
    mask = delta > 0
    # Red max
    m = mask & (Cmax == R)
    H[m] = ((G[m] - B[m]) / delta[m]) % 6
    # Green max
    m = mask & (Cmax == G)
    H[m] = (B[m] - R[m]) / delta[m] + 2
    # Blue max
    m = mask & (Cmax == B)
    H[m] = (R[m] - G[m]) / delta[m] + 4
    H = H / 6.0
    # Apply
    H = (H + hue_shift / 360.0) % 1.0
    S = np.clip(S * sat_factor, 0, 1)
    # HSV → RGB
    Hi = (H * 6).astype(int) % 6
    f  = H * 6 - np.floor(H * 6)
    p_ = V * (1 - S)
    q  = V * (1 - f * S)
    t  = V * (1 - (1 - f) * S)
    out = np.zeros_like(arr)
    for i, (r_, g_, b_) in enumerate([(V,t,p_),(q,V,p_),(p_,V,t),(p_,q,V),(t,p_,V),(V,p_,q)]):
        m = Hi == i
        out[:,:,0][m] = r_[m]
        out[:,:,1][m] = g_[m]
        out[:,:,2][m] = b_[m]
    result = Image.fromarray((out * 255).astype(np.uint8))
    return result, {"saturation": sat_factor, "hue_shift": hue_shift}

def apply_desaturate(img, p):
    rgb = img.convert("RGB")
    grey = ImageOps.grayscale(rgb)
    result = grey.convert("RGB")
    return result, {}

def apply_invert(img, p):
    rgb = img.convert("RGB")
    result = ImageOps.invert(rgb)
    return result, {}

def apply_threshold(img, p):
    level = p.get("level", random.randint(80, 180))
    rgb   = img.convert("L")
    result = rgb.point(lambda x: 255 if x > level else 0).convert("RGB")
    return result, {"level": level}

def apply_posterize(img, p):
    bits = p.get("bits", random.randint(2, 4))
    result = ImageOps.posterize(img.convert("RGB"), bits)
    return result, {"bits": bits}

def apply_colorize(img, p):
    hue = p.get("hue", random.randint(0, 359))
    sat = p.get("sat", random.randint(60, 100))
    import colorsys
    grey = np.array(ImageOps.grayscale(img.convert("RGB")), dtype=np.float32) / 255.0
    h, s, v_base = hue / 360.0, sat / 100.0, 1.0
    out = np.zeros((*grey.shape, 3), dtype=np.float32)
    for ch_idx, base in enumerate(colorsys.hsv_to_rgb(h, s, v_base)):
        out[:,:,ch_idx] = grey * base
    result = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    return result, {"hue": hue, "sat": sat}

def apply_edge_detect(img, p):
    rgb  = img.convert("RGB")
    grey = rgb.convert("L")
    edges = grey.filter(ImageFilter.FIND_EDGES)
    result = edges.convert("RGB")
    return result, {}

def apply_red_eye_removal(img, p):
    raise NotImplementedError("Use generate_red_eye_pair() instead")

def apply_rotation(img, p):
    angle = p.get("angle", random.choice([90, 180, 270]))
    result = img.rotate(-angle, expand=True)  # PIL rotates CCW
    result = result.resize(img.size, Image.LANCZOS)
    return result, {"angle": angle}

def apply_flip(img, p):
    axis = p.get("axis", random.choice(["horizontal", "vertical"]))
    if axis == "horizontal":
        result = ImageOps.mirror(img.convert("RGB"))
    else:
        result = ImageOps.flip(img.convert("RGB"))
    return result, {"axis": axis}


COMMANDS = {
    "gaussian_blur":        apply_gaussian_blur,
    "sharpen":              apply_sharpen,
    "brightness_contrast":  apply_brightness_contrast,
    "hue_saturation":       apply_hue_saturation_fast,
    "desaturate":           apply_desaturate,
    "invert":               apply_invert,
    "threshold":            apply_threshold,
    "posterize":            apply_posterize,
    "colorize":             apply_colorize,
    "edge_detect":          apply_edge_detect,
    "rotation":             apply_rotation,
    "flip":                 apply_flip,
}

ALL_COMMANDS = ["sharpen", "gaussian_blur"]


def build_triptych(before: Image.Image, after: Image.Image,
                   gain: float = DIFF_GAIN) -> Image.Image:
    """Stack [BEFORE | AFTER | DIFF×gain] into a single 896×448 image."""
    pw, ph = PANEL_W, TRIPTYCH_H
    def resize_panel(im):
        return im.convert("RGB").resize((pw, ph), Image.LANCZOS)

    b = resize_panel(before)
    a = resize_panel(after)

    arr_b = np.array(b, dtype=np.float32)
    arr_a = np.array(a, dtype=np.float32)
    diff  = np.abs(arr_a - arr_b) * gain
    diff  = np.clip(diff, 0, 255).astype(np.uint8)
    d     = Image.fromarray(diff)

    right_w = TRIPTYCH_W - 2 * pw
    canvas = Image.new("RGB", (TRIPTYCH_W, TRIPTYCH_H), (0, 0, 0))
    canvas.paste(b, (0,      0))
    canvas.paste(a, (pw,     0))
    d_wide = d.resize((right_w, ph), Image.LANCZOS)
    canvas.paste(d_wide, (2 * pw, 0))
    return canvas


def generate_red_eye_pair(img: Image.Image):
    arr = np.array(img.convert("RGB"), dtype=np.uint8).copy()
    h, w = arr.shape[:2]

    n_eyes = random.randint(2, 4)
    eye_positions = []
    for _ in range(n_eyes):
        cx = random.randint(w // 4, 3 * w // 4)
        cy = random.randint(h // 6, h // 2)
        r  = random.randint(5, 15)
        eye_positions.append((cx, cy, r))

    injected = arr.copy()
    for (cx, cy, r) in eye_positions:
        ys, xs = np.ogrid[-cy:h-cy, -cx:w-cx]
        mask = xs*xs + ys*ys <= r*r
        injected[mask, 0] = np.clip(injected[mask, 0].astype(int) * 0.3 + 220, 0, 255).astype(np.uint8)
        injected[mask, 1] = np.clip(injected[mask, 1].astype(int) * 0.2, 0, 255).astype(np.uint8)
        injected[mask, 2] = np.clip(injected[mask, 2].astype(int) * 0.2, 0, 255).astype(np.uint8)

    removed = injected.copy().astype(np.float32)
    r_ch = removed[:,:,0]
    g_ch = removed[:,:,1]
    b_ch = removed[:,:,2]
    red_mask = (r_ch > 150) & (r_ch > 2 * (g_ch + b_ch + 1))
    grey = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch
    removed[red_mask, 0] = grey[red_mask] * 0.6
    removed[red_mask, 1] = grey[red_mask] * 0.6
    removed[red_mask, 2] = grey[red_mask] * 0.6
    removed = np.clip(removed, 0, 255).astype(np.uint8)

    before = Image.fromarray(injected)  
    after  = Image.fromarray(removed)    
    return before, after, {"n_eyes": n_eyes, "positions": eye_positions}


def load_source_images(images_dir: Path, n: int) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    paths = [p for p in images_dir.rglob("*") if p.suffix.lower() in exts]
    if not paths:
        raise FileNotFoundError(f"No images found in {images_dir}")
    random.shuffle(paths)
    return paths[:n] if len(paths) >= n else (paths * (n // len(paths) + 1))[:n]


def generate_sample(cmd: str, img_path: Path, sample_id: str, out_dir: Path, params_override: dict | None = None) -> dict | None:
    try:
        img = Image.open(img_path).convert("RGB")
        if img.width < 64 or img.height < 64:
            return None

        params = params_override or {}

        if cmd == "red_eye_removal":
            before, after, params = generate_red_eye_pair(img)
            after_img = after  
        else:
            fn = COMMANDS[cmd]
            after_img, params = fn(img, params)
            before, after = img, after_img

        arr_b = np.array(before.convert("RGB"), dtype=np.float32)
        arr_a = np.array(after.convert("RGB"),  dtype=np.float32)  
        mean_delta = np.abs(arr_a - arr_b).mean()
        min_delta = 0.1 if cmd == "red_eye_removal" else 1.0
        if mean_delta < min_delta:
            return None  

        triptych = build_triptych(before, after)

        out_path = out_dir / f"{sample_id}.jpg"
        triptych.save(out_path, "JPEG", quality=92)

        return {
            "id":      sample_id,
            "image":   str(out_path),
            "label":   cmd,
            "command": cmd,
            "params":  params,
            "mean_delta": float(round(mean_delta, 2)),
            "source_image": str(img_path),
        }
    except Exception as e:
        print(f"  [WARN] {cmd}/{sample_id}: {e}", file=sys.stderr)
        return None


def generate_split(split: str, commands: list[str], source_images: list[Path], n_per_class: int, out_root: Path) -> list[dict]:
   
    split_dir = out_root / "images" / split / "composite"
    split_dir.mkdir(parents=True, exist_ok=True)

    records = []
    global_counter = 1

    for cmd in tqdm(commands, desc=f"[{split}] commands"):
        cmd_records = []
        img_pool = source_images.copy()
        random.shuffle(img_pool)
        attempts = 0

        while len(cmd_records) < n_per_class and attempts < n_per_class * 5:
            src = img_pool[attempts % len(img_pool)]
            attempts += 1
            sid = f"{split}_{global_counter:05d}"
            rec = generate_sample(cmd, src, sid, split_dir)
            if rec:
                rec["split"] = split
                cmd_records.append(rec)
                global_counter += 1

        if len(cmd_records) < n_per_class:
            print(f"  [WARN] {cmd}/{split}: only {len(cmd_records)}/{n_per_class} samples generated")
        records.extend(cmd_records)

    return records


def write_jsonl(records: list[dict], path: Path):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def main():
    parser = argparse.ArgumentParser(description="AI2D V3 dataset generator")
    parser.add_argument("--images_dir", type=Path, required=True,
                        help="Directory of diverse source images")
    parser.add_argument("--output_dir", type=Path, default=Path("./data_v3"),
                        help="Root output directory")
    parser.add_argument("--train_per_class", type=int, default=150)
    parser.add_argument("--val_per_class", type=int, default=30)
    parser.add_argument("--diff_gain", type=float, default=DIFF_GAIN)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print(f"Output dir : {args.output_dir}")
    print(f"Classes    : {ALL_COMMANDS}  ({len(ALL_COMMANDS)} total)")
    print(f"Train/class: {args.train_per_class}  |  Val/class: {args.val_per_class}")

    total_needed = (args.train_per_class + args.val_per_class) * len(ALL_COMMANDS)
    print(f"Loading source images from {args.images_dir} …")
    all_images = load_source_images(args.images_dir, total_needed)
    print(f"  {len(all_images)} images available")

    n_train_src = int(len(all_images) * 0.8)
    train_sources = all_images[:n_train_src]
    val_sources   = all_images[n_train_src:]

    manifests_dir = args.output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    print("\n─── Generating TRAIN split ───")
    train_records = generate_split(
        "train", ALL_COMMANDS, train_sources,
        args.train_per_class, args.output_dir)

    print("\n─── Generating VAL split ───")
    val_records = generate_split(
        "val", ALL_COMMANDS, val_sources,
        args.val_per_class, args.output_dir)

    # Write manifests
    train_path = manifests_dir / "train_v3.jsonl"
    val_path   = manifests_dir / "val_v3.jsonl"
    write_jsonl(train_records, train_path)
    write_jsonl(val_records,   val_path)

    print(f"\n Done!")
    print(f"   Train: {len(train_records)} samples → {train_path}")
    print(f"   Val  : {len(val_records)}   samples → {val_path}")

    from collections import Counter
    tc = Counter(r["label"] for r in train_records)
    vc = Counter(r["label"] for r in val_records)
    print("\nClass distribution (train | val):")
    for cmd in ALL_COMMANDS:
        print(f"  {cmd:<25s}  {tc.get(cmd,0):>4d}  |  {vc.get(cmd,0):>3d}")


if __name__ == "__main__":
    main()
