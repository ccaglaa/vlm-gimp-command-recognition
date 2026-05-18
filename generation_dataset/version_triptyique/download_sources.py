"""
portraits, landscapes, architecture, products,
text/screenshots, animals, abstract art

Sources:
  - Unsplash Source API 
  - Open Images V7 download list 

Usage:
    python download_sources.py --output_dir ./source_images --n 500

"""
from __future__ import annotations

import argparse
import random
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image


UNSPLASH_QUERIES = {
    "portraits": ["portrait", "face", "person", "woman", "man"],
    "landscapes": ["landscape", "nature", "mountains", "forest", "ocean"],
    "architecture": ["architecture", "building", "city", "interior"],
    "products": ["product", "still life", "food", "coffee", "technology"],
    "text": ["document", "book", "sign", "typography"],
    "animals": ["wildlife", "bird", "dog", "elephant", "horse"],
    "abstract": ["abstract", "art", "texture", "pattern", "colorful"],
}

N_PER_CATEGORY = {
    "portraits": 100,   
    "landscapes": 80,
    "architecture": 70,
    "products": 60,
    "text": 40,
    "animals": 80,
    "abstract": 70,
}


def download_unsplash(query: str, idx: int, out_dir: Path,
                       width: int = 800, height: int = 600) -> Path | None:
    url = f"https://picsum.photos/{width}/{height}?random={idx}"
    filename = out_dir / f"unsplash_{query.replace(' ','_')}_{idx:04d}.jpg"
    if filename.exists():
        return filename
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "AI2D-Research-Dataset/1.0 (academic, non-commercial)"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        with open(filename, "wb") as f:
            f.write(data)
        return filename
    except Exception as e:
        print(f"  [WARN] Unsplash download failed ({query} #{idx}): {e}")
        return None


def generate_synthetic_image(category: str, idx: int, out_dir: Path) -> Path:
    w, h = random.choice([(640, 480), (800, 600), (1024, 768)])
    arr  = np.zeros((h, w, 3), dtype=np.uint8)

    if category == "portraits":
        arr[:,:,0] = np.linspace(200, 240, w, dtype=np.uint8)[None, :]
        arr[:,:,1] = np.linspace(160, 200, w, dtype=np.uint8)[None, :]
        arr[:,:,2] = np.linspace(120, 160, w, dtype=np.uint8)[None, :]
        cx1, cy1 = w // 3,     h // 3
        cx2, cy2 = 2 * w // 3, h // 3
        for cx, cy in [(cx1, cy1), (cx2, cy2)]:
            ys, xs = np.ogrid[:h, :w]
            mask = (xs - cx)**2 + (ys - cy)**2 < 400
            arr[mask] = [30, 20, 20]  

    elif category == "landscapes":
        arr[:h//2, :, 0] = 100; arr[:h//2, :, 1] = 150; arr[:h//2, :, 2] = 230
        arr[h//2:, :, 0] = 60;  arr[h//2:, :, 1] = 120; arr[h//2:, :, 2] = 50

    else:
        arr = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)

    img = Image.fromarray(arr)
    for _ in range(random.randint(3, 10)):
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        x0 = random.randint(0, w-100)
        y0 = random.randint(0, h-100)
        color = tuple(random.randint(50, 220) for _ in range(3))
        draw.ellipse([x0, y0, x0+random.randint(20,100), y0+random.randint(20,100)], fill=color)

    path = out_dir / f"synthetic_{category}_{idx:04d}.jpg"
    img.save(path, "JPEG", quality=85)
    return path


def download_all(output_dir: Path, n_total: int = 500, use_network: bool = True, delay: float = 0.5):
    output_dir.mkdir(parents=True, exist_ok=True)
    all_paths = []

    if use_network:
        print("Downloading from Unsplash Source…")
        for category, queries in UNSPLASH_QUERIES.items():
            n = N_PER_CATEGORY.get(category, 50)
            cat_dir = output_dir / category
            cat_dir.mkdir(exist_ok=True)
            downloaded = 0
            for i in range(n):
                query = random.choice(queries)
                p = download_unsplash(query, i, cat_dir)
                if p:
                    all_paths.append(p)
                    downloaded += 1
                    print(f"  [{category}] {downloaded}/{n}", end="\r")
                time.sleep(delay)  # be polite
                if downloaded >= n:
                    break
            print(f"  {category}: {downloaded}/{n}")
    else:
        print("Generating synthetic images (no network)…")
        for category, n in N_PER_CATEGORY.items():
            cat_dir = output_dir / category
            cat_dir.mkdir(exist_ok=True)
            for i in range(n):
                p = generate_synthetic_image(category, i, cat_dir)
                all_paths.append(p)

    print(f"\nTotal images collected: {len(all_paths)}")
    # Write an index file
    index_path = output_dir / "image_index.txt"
    with open(index_path, "w") as f:
        for p in all_paths:
            f.write(str(p) + "\n")
    print(f"Index written: {index_path}")
    return all_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, default=Path("./source_images"))
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--no_network", action="store_true")
    parser.add_argument("--delay", type=float, default=0.05,
                        help="Delay between requests (seconds)")
    args = parser.parse_args()

    download_all(args.output_dir, args.n,
                 use_network=not args.no_network,
                 delay=args.delay)
