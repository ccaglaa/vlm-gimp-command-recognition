"""
Usage:
    python audit_dataset_v3.py \
        --train_jsonl ./data_v3/manifests/train_v3.jsonl \
        --val_jsonl   ./data_v3/manifests/val_v3.jsonl \
        --output_plots ./data_v3/plots
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from tqdm import tqdm


DEAD_SAMPLE_THRESHOLD = 0.5   
HARD_THRESHOLD = 15.0  
EASY_THRESHOLD = 50.0  

def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            r = json.loads(line.strip())
            if r:
                records.append(r)
    return records


def compute_mean_delta(record: dict) -> float | None:
    try:
        img = np.array(Image.open(record["image"]).convert("RGB"), dtype=np.float32)
        w   = img.shape[1]
        pw  = w // 3
        before = img[:, :pw, :]
        after  = img[:, pw:2*pw, :]
        return float(np.abs(after - before).mean())
    except Exception:
        return None


def audit(train_records: list, val_records: list, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    all_classes = sorted(set(r["label"] for r in train_records + val_records))

    print(f"\n{'='*70}")
    print(f"  AI2D V3 Dataset Audit")
    print(f"{'='*70}")
    print(f"  Train: {len(train_records)} samples  |  Val: {len(val_records)} samples")
    print(f"  Classes: {len(all_classes)}")

    train_counts = Counter(r["label"] for r in train_records)
    val_counts   = Counter(r["label"] for r in val_records)

    print(f"\n{'Command':<25}  {'Train':>6}  {'Val':>5}")
    print("-" * 45)
    issues = []
    for cls in all_classes:
        tc = train_counts.get(cls, 0)
        vc = val_counts.get(cls, 0)
        flag = ""
        if tc < 100:
            flag = "LOW TRAIN"
            issues.append(f"  {cls}: only {tc} train samples")
        if vc < 20:
            flag += " LOW VAL"
            issues.append(f"  {cls}: only {vc} val samples")
        print(f"  {cls:<25}  {tc:>6}  {vc:>5}  {flag}")

    if issues:
        print("\nIssues found:")
        for i in issues:
            print(i)
    else:
        print("\n All classes have sufficient samples")

    # Imbalance ratio
    min_t = min(train_counts.values()) if train_counts else 0
    max_t = max(train_counts.values()) if train_counts else 0
    ratio = max_t / max(min_t, 1)
    print(f"\n  Train imbalance ratio: {ratio:.2f}x  "
          f"(min={min_t}, max={max_t})")

    print(f"\nComputing pixel deltas ")
    deltas_by_class = defaultdict(list)
    dead_samples = []

    for r in tqdm(train_records, desc="Train"):
        d = compute_mean_delta(r)
        if d is not None:
            deltas_by_class[r["label"]].append(d)
            if d < DEAD_SAMPLE_THRESHOLD:
                dead_samples.append(r)

    print(f"\n{'Command':<25}  {'mean_Δ':>7}  {'std_Δ':>6}  {'min_Δ':>6}  {'Tier'}")
    print("-" * 65)
    for cls in all_classes:
        ds = deltas_by_class.get(cls, [])
        if not ds:
            print(f"  {cls:<25}  {'N/A':>7}")
            continue
        mean_d = np.mean(ds)
        std_d  = np.std(ds)
        min_d  = np.min(ds)
        if mean_d < HARD_THRESHOLD:
            tier = " Hard"
        elif mean_d < EASY_THRESHOLD:
            tier = " Medium"
        else:
            tier = " Easy"
        print(f"  {cls:<25}  {mean_d:>7.2f}  {std_d:>6.2f}  {min_d:>6.2f}  {tier}")

    if dead_samples:
        print(f"\n {len(dead_samples)} dead samples (Δ < {DEAD_SAMPLE_THRESHOLD}):")
        for r in dead_samples[:10]:
            print(f"    {r['id']}  {r['label']}  Δ={compute_mean_delta(r):.2f}")
    else:
        print(f"\n No dead samples found (Δ ≥ {DEAD_SAMPLE_THRESHOLD} for all)")

    print("\nChecking image dimensions…")
    dim_issues = []
    for r in train_records[:100]:  # sample check
        try:
            img = Image.open(r["image"])
            if img.size != (896, 448):
                dim_issues.append((r["id"], img.size))
        except Exception as e:
            dim_issues.append((r["id"], str(e)))
    if dim_issues:
        print(f"   {len(dim_issues)} dimension issues found (sample of 100)")
    else:
        print("  All sampled images are 896×448")

    missing = [r for r in train_records + val_records
               if not Path(r["image"]).exists()]
    if missing:
        print(f"\n  {len(missing)} missing image files!")
    else:
        print("  All image files present")

    _plot_class_distribution(train_counts, val_counts, all_classes,
                              output_dir / "v3_class_distribution.png")
    _plot_pixel_deltas(deltas_by_class, all_classes,
                       output_dir / "v3_pixel_deltas.png")

    print(f"\nPlots saved to {output_dir}")
    print("="*70)


def _plot_class_distribution(train_counts, val_counts, classes, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, counts, title in [
        (axes[0], train_counts, f"Train ({sum(train_counts.values())} samples)"),
        (axes[1], val_counts,   f"Val ({sum(val_counts.values())} samples)"),
    ]:
        sorted_cls = sorted(classes, key=lambda c: -counts.get(c, 0))
        vals = [counts.get(c, 0) for c in sorted_cls]
        bars = ax.barh(sorted_cls, vals, color=plt.cm.viridis(
            np.linspace(0, 1, len(sorted_cls))))
        for bar, v in zip(bars, vals):
            ax.text(v + 0.3, bar.get_y() + bar.get_height()/2,
                    str(v), va="center", fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("Count")
    plt.suptitle("AI2D V3 — Class Distribution", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def _plot_pixel_deltas(deltas_by_class, classes, out_path):
    sorted_cls = sorted(classes,
                         key=lambda c: -np.mean(deltas_by_class.get(c, [0])))
    means = [np.mean(deltas_by_class.get(c, [0])) for c in sorted_cls]
    stds  = [np.std(deltas_by_class.get(c,  [0])) for c in sorted_cls]

    colors = ["#d62728" if m > EASY_THRESHOLD else
              "#aec7e8" if m > HARD_THRESHOLD else "#1f77b4"
              for m in means]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(sorted_cls, means, xerr=stds, color=colors, alpha=0.85,
            capsize=3)
    ax.axvline(HARD_THRESHOLD, color="orange", linestyle="--", label=f"Hard threshold ({HARD_THRESHOLD})")
    ax.axvline(EASY_THRESHOLD, color="red", linestyle="--", label=f"Easy threshold ({EASY_THRESHOLD})")
    ax.set_xlabel("Mean absolute pixel difference (0-255 scale)")
    ax.set_title("V3 Per-command visual difficulty")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_jsonl", type=str, required=True)
    parser.add_argument("--val_jsonl", type=str, required=True)
    parser.add_argument("--output_plots", type=str, default="./data_v3/plots")
    args = parser.parse_args()

    train_records = load_jsonl(args.train_jsonl)
    val_records = load_jsonl(args.val_jsonl)
    audit(train_records, val_records, Path(args.output_plots))
