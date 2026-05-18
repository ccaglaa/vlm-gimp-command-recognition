#!/usr/bin/env python3
"""
Run INSIDE GIMP via Script-Fu console or batch mode:

    gimp -i -b '(python-fu-eval "
        import sys
        sys.path.insert(0, \"/path/to/ai2d_v3\")
        from gimp_batch_processor import run_batch
        run_batch()
    ")' -b '(gimp-quit 0)'

Or from the GIMP Script-Fu console:
    (python-fu-eval "exec(open('/path/to/gimp_batch_processor.py').read())")

This script uses GIMP's native procedures for maximum accuracy, matching
what real users would actually apply.
"""

import json
import os
import random
import sys
from pathlib import Path

try:
    import gimp
    import gimpfu
    from gimpfu import *
    GIMP_AVAILABLE = True
except ImportError:
    GIMP_AVAILABLE = False
    print("[INFO] GIMP not available — using PIL fallback mode", file=sys.stderr)


PARAM_SAMPLERS = {
    "gaussian_blur": lambda: {
        "h": random.choice([3, 5, 7, 9, 11, 13]),
        "v": random.choice([3, 5, 7, 9, 11, 13]),
    },
    "sharpen": lambda: {
        "amount": round(random.uniform(0.3, 0.9), 2)
    },
    "brightness_contrast": lambda: {
        "brightness": random.randint(-60, 60),
        "contrast":   random.randint(-40, 60),
    },
    "hue_saturation": lambda: {
        "hue_offset": random.randint(-120, 120),
        "lightness":  random.randint(-30, 30),
        "saturation": random.randint(-60, 60),
    },
    "desaturate": lambda: {
        "mode": random.choice([DESATURATE_LUMINOSITY, DESATURATE_LUMA, DESATURATE_AVERAGE])
        if GIMP_AVAILABLE else "luminosity"
    },
    "invert": lambda: {},
    "threshold": lambda: {
        "low":  random.randint(60, 100),
        "high": random.randint(150, 200),
    },
    "posterize": lambda: {
        "levels": random.randint(2, 5)
    },
    "colorize": lambda: {
        "hue":        random.randint(0, 359),
        "saturation": random.randint(40, 80),
        "lightness":  random.randint(-20, 20),
    },
    "edge_detect": lambda: {
        "amount": round(random.uniform(0.5, 2.0), 1),
        "wrapmode": 0,
        "edgemode": 0,
    },
    "rotation": lambda: {
        "angle": random.choice([90, 180, 270])
    },
    "flip": lambda: {
        "axis": random.choice(["horizontal", "vertical"])
    },
}



def gimp_apply_gaussian_blur(image, drawable, params):
    """gimp-drawable-filter-new with gegl:gaussian-blur"""
    pdb.plug_in_gauss(image, drawable, params["h"]*2+1, params["v"]*2+1, 0)

def gimp_apply_sharpen(image, drawable, params):
    pdb.plug_in_unsharp_mask(image, drawable,
                              params["amount"] * 5,   
                              params["amount"],        
                              0)                       

def gimp_apply_brightness_contrast(image, drawable, params):
    pdb.gimp_brightness_contrast(drawable,
                                  params["brightness"],
                                  params["contrast"])

def gimp_apply_hue_saturation(image, drawable, params):
    # ALL_HUES = 0
    pdb.gimp_drawable_hue_saturation(drawable, 0,
                                      params["hue_offset"],
                                      params["lightness"],
                                      params["saturation"],
                                      0)

def gimp_apply_desaturate(image, drawable, params):
    mode = params.get("mode", DESATURATE_LUMINOSITY if GIMP_AVAILABLE else 0)
    pdb.gimp_drawable_desaturate(drawable, mode)

def gimp_apply_invert(image, drawable, params):
    pdb.gimp_drawable_invert(drawable, False)

def gimp_apply_threshold(image, drawable, params):
    pdb.gimp_threshold(drawable, params["low"], params["high"])

def gimp_apply_posterize(image, drawable, params):
    pdb.gimp_posterize(drawable, params["levels"])

def gimp_apply_colorize(image, drawable, params):
    pdb.gimp_drawable_colorize_hsl(drawable,
                                    params["hue"] / 360.0,
                                    params["saturation"] / 100.0,
                                    params["lightness"] / 100.0)

def gimp_apply_edge_detect(image, drawable, params):
    pdb.plug_in_edge(image, drawable,
                     params["amount"],
                     params["wrapmode"],
                     params["edgemode"])

def gimp_apply_rotation(image, drawable, params):
    angle = params["angle"]
    if angle == 90:
        pdb.gimp_image_rotate(image, ROTATE_90)
    elif angle == 180:
        pdb.gimp_image_rotate(image, ROTATE_180)
    elif angle == 270:
        pdb.gimp_image_rotate(image, ROTATE_270)

def gimp_apply_flip(image, drawable, params):
    axis = params["axis"]
    if axis == "horizontal":
        pdb.gimp_image_flip(image, ORIENTATION_HORIZONTAL)
    else:
        pdb.gimp_image_flip(image, ORIENTATION_VERTICAL)

def gimp_apply_red_eye_removal(image, drawable, params):
    """GIMP's built-in red-eye removal filter."""
    threshold = params.get("threshold", random.randint(50, 80))
    pdb.plug_in_red_eye_removal(image, drawable, threshold)
    return {"threshold": threshold}


GIMP_PROCEDURES = {
    "gaussian_blur":       gimp_apply_gaussian_blur,
    "sharpen":             gimp_apply_sharpen,
    "brightness_contrast": gimp_apply_brightness_contrast,
    "hue_saturation":      gimp_apply_hue_saturation,
    "desaturate":          gimp_apply_desaturate,
    "invert":              gimp_apply_invert,
    "threshold":           gimp_apply_threshold,
    "posterize":           gimp_apply_posterize,
    "colorize":            gimp_apply_colorize,
    "edge_detect":         gimp_apply_edge_detect,
    "rotation":            gimp_apply_rotation,
    "flip":                gimp_apply_flip,
    "red_eye_removal":     gimp_apply_red_eye_removal,
}



def process_one_gimp(src_path: str, cmd: str, out_before: str, out_after: str,
                     params: dict) -> dict:
    """
    Load src_path into GIMP, apply cmd, export before/after.
    Returns updated params dict.
    """
    image = pdb.gimp_file_load(src_path, src_path)
    drawable = pdb.gimp_image_get_active_drawable(image)

    pdb.file_jpeg_save(image, drawable, out_before, out_before, 0.9, 0, 0, 0, "", 0, 1, 0, 2, 0)

    proc = GIMP_PROCEDURES[cmd]
    result = proc(image, drawable, params)
    if result:
        params.update(result)

    drawable = pdb.gimp_image_flatten(image)
    pdb.file_jpeg_save(image, drawable, out_after, out_after, 0.9, 0, 0, 0, "", 0, 1, 0, 2, 0)

    pdb.gimp_image_delete(image)
    return params


def run_batch(manifest_path: str = None, output_dir: str = None):

    if manifest_path is None:
        manifest_path = os.environ.get("AI2D_MANIFEST", "gimp_batch_manifest.json")
    if output_dir is None:
        output_dir = os.environ.get("AI2D_OUTPUT", "./gimp_output")

    os.makedirs(output_dir, exist_ok=True)

    with open(manifest_path) as f:
        jobs = json.load(f)

    results = []
    for i, job in enumerate(jobs):
        src  = job["src"]
        cmd  = job["cmd"]
        params = job.get("params", PARAM_SAMPLERS.get(cmd, lambda: {})())
        sid  = job.get("id", f"sample_{i:05d}")

        out_before = os.path.join(output_dir, f"{sid}_before.jpg")
        out_after  = os.path.join(output_dir, f"{sid}_after.jpg")

        try:
            params = process_one_gimp(src, cmd, out_before, out_after, params)
            results.append({
                "id": sid, "cmd": cmd, "params": params,
                "before": out_before, "after": out_after, "ok": True
            })
        except Exception as e:
            results.append({"id": sid, "cmd": cmd, "ok": False, "error": str(e)})
            print(f"[ERR] {sid}: {e}", file=sys.stderr)

    out_results = os.path.join(output_dir, "gimp_results.json")
    with open(out_results, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Done. {sum(r['ok'] for r in results)}/{len(results)} OK → {out_results}")



def generate_gimp_manifest(images_dir: str, commands: list, n_per_class: int,
                             output_path: str = "gimp_batch_manifest.json"):

    from pathlib import Path
    import random

    paths = [str(p) for p in Path(images_dir).rglob("*")
             if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    random.shuffle(paths)

    jobs = []
    counter = 1
    for cmd in commands:
        sampler = PARAM_SAMPLERS.get(cmd, lambda: {})
        for i in range(n_per_class):
            src = paths[(counter + i) % len(paths)]
            jobs.append({
                "id":     f"sample_{counter:05d}",
                "src":    src,
                "cmd":    cmd,
                "params": sampler(),
            })
            counter += 1

    with open(output_path, "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"Manifest written: {output_path} ({len(jobs)} jobs)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["manifest", "batch"], default="manifest")
    p.add_argument("--images_dir", type=str, default="./source_images")
    p.add_argument("--output_manifest", type=str, default="gimp_batch_manifest.json")
    p.add_argument("--n_per_class", type=int, default=180)
    args = p.parse_args()

    ALL_COMMANDS = list(PARAM_SAMPLERS.keys())

    if args.mode == "manifest":
        generate_gimp_manifest(
            args.images_dir, ALL_COMMANDS, args.n_per_class,
            args.output_manifest)
    elif args.mode == "batch":
        if not GIMP_AVAILABLE:
            print("ERROR: batch mode requires GIMP Python-Fu environment")
            sys.exit(1)
        run_batch()
