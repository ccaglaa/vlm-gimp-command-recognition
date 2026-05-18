#!/usr/bin/env python3
"""
Usage:
    python generate_dataset.py \
        --images_dir ./source_images \
        --output_dir ./dataset \
        --commands all \
        --params default

Output structure:
    dataset/
        train/
            0001_gaussian_blur/
                image_in.jpg
                image_out.jpg
                label.json
            ...
        val/
            ...
        metadata.json
"""

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path


COMMANDS = {
    "gaussian_blur": {
        "label": "Gaussian Blur",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-gauss RUN-NONINTERACTIVE image drawable {h} {v} 0)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "h": {"type": "int", "range": [3, 51], "default": 9, "step": 2},   # must be odd
            "v": {"type": "int", "range": [3, 51], "default": 9, "step": 2},
        },
        "force_odd": ["h", "v"],
    },

    "motion_blur": {
        "label": "Motion Blur",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-mblur RUN-NONINTERACTIVE image drawable 0 {length} {angle})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "length": {"type": "int", "range": [10, 80], "default": 20},
            "angle":  {"type": "float", "range": [0.0, 360.0], "default": 0.0},
        },
    },

    "sharpen": {
        "label": "Sharpen",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-unsharp-mask RUN-NONINTERACTIVE image drawable {radius} {amount} {threshold})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "radius":    {"type": "float", "range": [1.0, 10.0], "default": 2.0},
            "amount":    {"type": "float", "range": [0.3, 2.0],  "default": 0.5},
            "threshold": {"type": "int",   "range": [0, 30],     "default": 0},
        },
    },

    "pixelize": {
        "label": "Pixelize",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-pixelize RUN-NONINTERACTIVE image drawable {pixelwidth} {pixelheight})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "pixelwidth":  {"type": "int", "range": [5, 40],  "default": 10},
            "pixelheight": {"type": "int", "range": [5, 40],  "default": 10},
        },
    },

    "emboss": {
        "label": "Emboss",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-emboss RUN-NONINTERACTIVE image drawable {azimuth} {elevation} {depth} TRUE)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "azimuth":   {"type": "float", "range": [0.0, 360.0], "default": 315.0},
            "elevation": {"type": "float", "range": [10.0, 80.0], "default": 45.0},
            "depth":     {"type": "int",   "range": [1, 15],      "default": 3},
        },
    },

    "edge_detect": {
        "label": "Edge Detect",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-edge RUN-NONINTERACTIVE image drawable {amount} 1 {edgemode})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "amount":   {"type": "float", "range": [1.0, 6.0], "default": 1.0},
            "edgemode": {"type": "int",   "range": [0, 5],     "default": 1},
        },
    },

    "oilify": {
        "label": "Oilify",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-oilify RUN-NONINTERACTIVE image drawable {mask_size} 1)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "mask_size": {"type": "int", "range": [4, 20], "default": 8},
        },
    },

    "spread": {
        "label": "Spread",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-spread RUN-NONINTERACTIVE image drawable {sx} {sy})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "sx": {"type": "float", "range": [3.0, 30.0], "default": 5.0},
            "sy": {"type": "float", "range": [3.0, 30.0], "default": 5.0},
        },
    },

    "ripple": {
        "label": "Ripple",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-ripple RUN-NONINTERACTIVE image drawable {period} {amplitude} 0 0 0 1 0 FALSE)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "period":    {"type": "int", "range": [10, 80],  "default": 20},
            "amplitude": {"type": "int", "range": [3, 30],   "default": 5},
        },
    },

    "whirl_pinch": {
        "label": "Whirl and Pinch",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-whirl-pinch RUN-NONINTERACTIVE image drawable {whirl_angle} {pinch_amount} 1.0)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "whirl_angle":  {"type": "float", "range": [45.0, 360.0], "default": 90.0},
            "pinch_amount": {"type": "float", "range": [-0.5, 0.5],   "default": 0.0},
        },
    },

    "wind": {
        "label": "Wind",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-wind RUN-NONINTERACTIVE image drawable 0 {threshold} {direction} {strength} {style} 0)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "threshold": {"type": "int", "range": [5, 30],  "default": 10},
            "direction": {"type": "int", "range": [0, 1],   "default": 0},
            "strength":  {"type": "int", "range": [20, 80], "default": 40},
            "style":     {"type": "int", "range": [0, 1],   "default": 0},
        },
    },

    "hsv_noise": {
        "label": "HSV Noise",
        "category": "filter",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-hsv-noise RUN-NONINTERACTIVE image drawable {dulling} {sat_noise} {hue_dist} {val_dist})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "dulling":    {"type": "int", "range": [1, 8],   "default": 2},
            "sat_noise":  {"type": "int", "range": [0, 50],  "default": 3},
            "hue_dist":   {"type": "int", "range": [0, 60],  "default": 3},
            "val_dist":   {"type": "int", "range": [10, 80], "default": 25},
        },
    },

    "brightness_contrast": {
        "label": "Brightness-Contrast",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-brightness-contrast drawable {brightness} {contrast})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "brightness": {"type": "int", "range": [-80, 80],  "default": 0},
            "contrast":   {"type": "int", "range": [-60, 80],  "default": 0},
        },
    },

    "hue_saturation": {
        "label": "Hue-Saturation",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-drawable-hue-saturation drawable HUE-RANGE-ALL {hue_offset} {lightness} {saturation} 0)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "hue_offset": {"type": "float", "range": [-120.0, 120.0], "default": 0.0},
            "lightness":  {"type": "float", "range": [-40.0, 40.0],   "default": 0.0},
            "saturation": {"type": "float", "range": [-60.0, 80.0],   "default": 0.0},
        },
    },

    "colorize": {
        "label": "Colorize",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-drawable-colorize-hsl drawable {hue} {saturation} {lightness})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "hue":        {"type": "float", "range": [0.0, 360.0],    "default": 180.0},
            "saturation": {"type": "float", "range": [20.0, 80.0],    "default": 40.0},
            "lightness":  {"type": "float", "range": [-20.0, 20.0],   "default": 0.0},
        },
    },

    "invert": {
        "label": "Invert Colors",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-drawable-invert drawable FALSE)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {}, 
    },

    "posterize": {
        "label": "Posterize",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-drawable-posterize drawable {levels})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "levels": {"type": "int", "range": [2, 6], "default": 3},
        },
    },

    "threshold": {
        "label": "Threshold",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-threshold drawable {low_threshold} {high_threshold})
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "low_threshold":  {"type": "int", "range": [80,  160], "default": 127},
            "high_threshold": {"type": "int", "range": [161, 255], "default": 255},
        },
    },

    "desaturate": {
        "label": "Desaturate",
        "category": "color",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-drawable-desaturate drawable DESATURATE-LUMINOSITY)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {},
    },

    "rotate_90cw": {
        "label": "Rotate 90° CW",
        "category": "geometry",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-image-rotate image ROTATE-90)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {},
    },

    "rotate_180": {
        "label": "Rotate 180°",
        "category": "geometry",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-image-rotate image ROTATE-180)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {},
    },

    "flip_horizontal": {
        "label": "Flip Horizontal",
        "category": "geometry",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-image-flip image ORIENTATION-HORIZONTAL)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {},
    },

    "flip_vertical": {
        "label": "Flip Vertical",
        "category": "geometry",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (gimp-image-flip image ORIENTATION-VERTICAL)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {},
    },

    "whirl_pinch_geo": {
        "label": "Whirl Pinch (geo)",
        "category": "geometry",
        "script": """
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input}" "{input}")))
       (drawable (car (gimp-image-get-active-drawable image))))
  (plug-in-whirl-pinch RUN-NONINTERACTIVE image drawable {whirl_angle} 0.0 1.0)
  (file-jpeg-save RUN-NONINTERACTIVE image (car (gimp-image-get-active-drawable image)) "{output}" "{output}" 0.9 0 0 0 "" 0 1 0 2))
""",
        "params": {
            "whirl_angle": {"type": "float", "range": [90.0, 360.0], "default": 90.0},
        },
    },
}



def sample_params(cmd_def: dict, mode: str = "default") -> dict:
    result = {}
    for pname, pdef in cmd_def["params"].items():
        if mode == "default":
            result[pname] = pdef["default"]
        elif mode == "random":
            lo, hi = pdef["range"]
            if pdef["type"] == "int":
                v = random.randint(lo, hi)
                if pname in cmd_def.get("force_odd", []):
                    if v % 2 == 0:
                        v = max(lo, v - 1)
                result[pname] = v
            elif pdef["type"] == "float":
                result[pname] = round(random.uniform(lo, hi), 2)
            else:
                result[pname] = pdef["default"]
        else:
            raise ValueError(f"Unknown mode: {mode}")
    return result


def build_script(cmd_def: dict, input_path: str, output_path: str, params: dict) -> str:
    template = cmd_def["script"].strip()
    filled = template.format(input=input_path, output=output_path, **params)
    return filled



def run_gimp_script(script: str, gimp_bin: str = "gimp") -> bool:
    full_script = f'(begin {script} (gimp-quit 0))'
    cmd = [gimp_bin, "--no-interface", "--batch", full_script]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"  [GIMP ERROR] {result.stderr[:200]}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  [TIMEOUT] GIMP took too long", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"  [ERROR] GIMP binary not found: {gimp_bin}", file=sys.stderr)
        return False



def build_dataset(
    images_dir: Path,
    output_dir: Path,
    commands: list[str],
    param_mode: str,
    train_ratio: float,
    gimp_bin: str,
    dry_run: bool,
    samples_per_command: int,
):
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    source_images = [
        p for p in images_dir.rglob("*")
        if p.suffix.lower() in extensions
    ]
    if not source_images:
        print(f"[ERROR] No images found in {images_dir}")
        sys.exit(1)
    print(f"Found {len(source_images)} source images.")

    random.shuffle(source_images)
    n_train = int(len(source_images) * train_ratio)
    split_map = {}
    for i, img in enumerate(source_images):
        split_map[img] = "train" if i < n_train else "val"

    for split in ["train", "val"]:
        (output_dir / split).mkdir(parents=True, exist_ok=True)

    metadata = []
    sample_id = 0
    ok_count = 0
    err_count = 0

    for cmd_name in commands:
        if cmd_name not in COMMANDS:
            print(f"[WARN] Unknown command '{cmd_name}', skipping.")
            continue
        cmd_def = COMMANDS[cmd_name]
        print(f"\n── {cmd_def['label']} ({cmd_name}) ──")

        pool = source_images[:] 
        if samples_per_command and samples_per_command < len(pool):
            pool = random.sample(pool, samples_per_command)

        for src_img in pool:
            sample_id += 1
            split = split_map[src_img]
            params = sample_params(cmd_def, mode=param_mode)

            folder_name = f"{sample_id:05d}_{cmd_name}"
            sample_dir = output_dir / split / folder_name
            sample_dir.mkdir(parents=True, exist_ok=True)

            img_in_path  = sample_dir / "image_in.jpg"
            img_out_path = sample_dir / "image_out.jpg"
            label_path   = sample_dir / "label.json"

            if not dry_run:
                import shutil
                shutil.copy2(src_img, img_in_path)

            # Build and run GIMP script
            script = build_script(
                cmd_def,
                input_path=str(img_in_path.resolve()),
                output_path=str(img_out_path.resolve()),
                params=params,
            )

            if dry_run:
                print(f"  [DRY-RUN] {folder_name} | params={params}")
                ok_count += 1
            else:
                success = run_gimp_script(script, gimp_bin=gimp_bin)
                if success and img_out_path.exists():
                    ok_count += 1
                    print(f"  ✓ {folder_name}")
                else:
                    err_count += 1
                    print(f"  ✗ {folder_name} (FAILED)")
                    continue

            label = {
                "id": sample_id,
                "command": cmd_name,
                "label": cmd_def["label"],
                "category": cmd_def["category"],
                "params": params,
                "split": split,
                "source_image": str(src_img.name),
            }
            if not dry_run:
                with open(label_path, "w") as f:
                    json.dump(label, f, indent=2)

            metadata.append(label)

    meta_path = output_dir / "metadata.json"
    summary = {
        "total": sample_id,
        "ok": ok_count,
        "errors": err_count,
        "commands": commands,
        "param_mode": param_mode,
        "train_ratio": train_ratio,
        "samples": metadata,
    }
    if not dry_run:
        with open(meta_path, "w") as f:
            json.dump(summary, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Done. {ok_count} samples OK, {err_count} errors.")
    print(f"Dataset written to: {output_dir}")



def parse_args():
    p = argparse.ArgumentParser(description="AI2D dataset generator")
    p.add_argument("--images_dir",  required=True, type=Path,
                   help="Directory containing source images")
    p.add_argument("--output_dir",  required=True, type=Path,
                   help="Where to write the dataset")
    p.add_argument("--commands",    nargs="+", default=["all"],
                   help="Commands to apply. Use 'all' or list names. "
                        "Categories: 'filter', 'color', 'geometry'")
    p.add_argument("--params",      choices=["default", "random"], default="default",
                   help="Parameter sampling mode")
    p.add_argument("--train_ratio", type=float, default=0.8,
                   help="Fraction of source images used for train split")
    p.add_argument("--gimp_bin",    default="gimp",
                   help="Path to GIMP executable")
    p.add_argument("--dry_run",     action="store_true",
                   help="Print what would be done without calling GIMP")
    p.add_argument("--samples_per_command", type=int, default=None,
                   help="Max images to process per command (None = all)")
    p.add_argument("--seed",        type=int, default=42,
                   help="Random seed for reproducibility")
    return p.parse_args()


def resolve_commands(spec: list[str]) -> list[str]:
    if spec == ["all"]:
        return list(COMMANDS.keys())
    resolved = []
    for s in spec:
        if s in ("filter", "color", "geometry"):
            resolved += [k for k, v in COMMANDS.items() if v["category"] == s]
        elif s in COMMANDS:
            resolved.append(s)
        else:
            print(f"[WARN] '{s}' is not a known command or category, skipping.")
    return resolved


def main():
    args = parse_args()
    random.seed(args.seed)

    commands = resolve_commands(args.commands)
    print(f"Commands to process ({len(commands)}): {commands}")

    build_dataset(
        images_dir=args.images_dir,
        output_dir=args.output_dir,
        commands=commands,
        param_mode=args.params,
        train_ratio=args.train_ratio,
        gimp_bin=args.gimp_bin,
        dry_run=args.dry_run,
        samples_per_command=args.samples_per_command,
    )


if __name__ == "__main__":
    main()
