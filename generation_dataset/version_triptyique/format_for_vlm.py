"""
Usage:
    python format_for_vlm.py \
        --train_jsonl ./data_v3/manifests/train_v3.jsonl \
        --val_jsonl   ./data_v3/manifests/val_v3.jsonl \
        --output_dir  ./data_v3/manifests/formatted
"""

import argparse
import json
import os
import random
from pathlib import Path

LABEL_SET_V3 = [
    "gaussian_blur", "sharpen", "brightness_contrast", "hue_saturation",
    "desaturate", "invert", "threshold", "posterize", "colorize",
    "edge_detect", "red_eye_removal", "rotation", "flip",
]
LABEL_SET_DISPLAY = {
    "gaussian_blur":       "Gaussian Blur",
    "sharpen":             "Sharpen",
    "brightness_contrast": "Brightness-Contrast",
    "hue_saturation":      "Hue-Saturation",
    "desaturate":          "Desaturate",
    "invert":              "Invert",
    "threshold":           "Threshold",
    "posterize":           "Posterize",
    "colorize":            "Colorize",
    "edge_detect":         "Edge Detect",
    "red_eye_removal":     "Red Eye Removal",
    "rotation":            "Rotation",
    "flip":                "Flip",
}

SYSTEM_PROMPT = (
    "You are a GIMP image-editing analysis assistant. "
    "You will be shown a triptych image: "
    "the LEFT panel is the ORIGINAL image, "
    "the CENTER panel is the RESULT after exactly ONE GIMP operation was applied, "
    "and the RIGHT panel is an amplified pixel difference map. "
    "Your task is to identify that single operation. "
    "Reply with ONLY the operation name from the provided list — "
    "no explanation, no punctuation."
)


def make_label_set_hint(true_label: str, n_distractors: int = 8) -> str:
    distractors = [l for l in LABEL_SET_V3 if l != true_label]
    chosen = random.sample(distractors, min(n_distractors, len(distractors)))
    hint_set = chosen + [true_label]
    random.shuffle(hint_set)
    return ", ".join(LABEL_SET_DISPLAY.get(l, l) for l in hint_set)


def make_instruction(record: dict) -> str:
    display = LABEL_SET_DISPLAY.get(record["label"], record["label"])
    params  = record.get("params", {})
    param_str = ""
    if params:
        parts = [f"{k}={v}" for k, v in params.items()
                 if v is not None and k not in ("n_eyes", "positions")]
        if parts:
            param_str = " Use parameters: " + ", ".join(parts) + "."
    return (f"Apply '{display}' to transform the left image into the center image."
            + param_str)


def format_record(record: dict) -> dict:
    label     = record["label"]
    label_set = ", ".join(LABEL_SET_DISPLAY.get(l, l) for l in LABEL_SET_V3)

    user_text = (
        "The LEFT panel is BEFORE, the CENTER is AFTER, "
        "the RIGHT is the amplified difference (x15).\n\n"
        f"Valid operations:\n{label_set}\n\n"
        "What single GIMP operation was applied?"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image"},
            {"type": "text",  "text": user_text},
        ]},
        {"role": "assistant", "content": label},
    ]

    out = dict(record)
    out["messages"]       = messages
    out["target"]         = label
    out["label_set_hint"] = make_label_set_hint(label)
    out["instruction"]    = make_instruction(record)
    return out


def format_split(records: list[dict]) -> list[dict]:
    return [format_record(r) for r in records]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_jsonl", type=str, required=True)
    parser.add_argument("--val_jsonl",   type=str, required=True)
    parser.add_argument("--output_dir",  type=str, default="./data_v3/manifests/formatted")
    parser.add_argument("--seed",        type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    for split, path in [("train", args.train_jsonl), ("val", args.val_jsonl)]:
        records = []
        with open(path) as f:
            for line in f:
                r = json.loads(line.strip())
                if r:
                    records.append(r)

        formatted = format_split(records)

        out_path = Path(args.output_dir) / f"{split}_composed.jsonl"
        with open(out_path, "w") as f:
            for r in formatted:
                f.write(json.dumps(r) + "\n")

        print(f"{split}: {len(formatted)} records → {out_path}")

        # Quick sanity check
        sample = formatted[0]
        print(f"\n  Sample record ({split}_00001):")
        print(f"    label          = {sample['label']}")
        print(f"    target         = {sample['target']}")
        print(f"    instruction    = {sample['instruction'][:80]}…")
        print(f"    label_set_hint = {sample['label_set_hint'][:80]}…")
        print(f"    messages[0]    = {sample['messages'][0]['role']}: "
              f"{str(sample['messages'][0]['content'])[:60]}…")


if __name__ == "__main__":
    main()
