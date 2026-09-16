"""Caption images with BLIP and save results to JSON.

Reads all images in data/YYYY-MM-DD/images/ and writes:
    data/YYYY-MM-DD/captions.json

Run with the `img2txt` conda env (torch + transformers already installed):
    ~/miniforge3/envs/img2txt/bin/python caption.py
"""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = REPO_ROOT / "data"

MODEL_ID = "Salesforce/blip-image-captioning-base"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def caption_folder(images_dir: Path, run_date: str, device: str, limit: int = 0) -> Path:
    images_dir = images_dir.resolve()
    files = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if limit:
        files = files[:limit]
    if not files:
        raise SystemExit(f"No images found in {images_dir}")

    print(f"Loading {MODEL_ID} on {device}...")
    processor = BlipProcessor.from_pretrained(MODEL_ID)
    model = BlipForConditionalGeneration.from_pretrained(MODEL_ID).to(device)
    model.eval()

    items = []
    for i, path in enumerate(files, 1):
        image = Image.open(path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=30)
        text = processor.decode(output_ids[0], skip_special_tokens=True).strip()
        items.append({"file": path.name, "caption": text})
        print(f"[{i}/{len(files)}] {path.name}: {text}")

    payload = {
        "date": run_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL_ID,
        "images_dir": str(images_dir.relative_to(REPO_ROOT)) if images_dir.is_relative_to(REPO_ROOT) else str(images_dir),
        "count": len(items),
        "items": items,
    }
    out_file = DATA_ROOT / run_date / "captions.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote {out_file} ({len(items)} captions)")
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Caption a day's images with BLIP")
    parser.add_argument("--date", default=date.today().isoformat(), help="day folder (YYYY-MM-DD)")
    parser.add_argument("--images-dir", default=None, help="override the images folder path")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--limit", type=int, default=0, help="caption only the first N images (0 = all)")
    args = parser.parse_args()

    folder = Path(args.images_dir) if args.images_dir else DATA_ROOT / args.date / "images"
    caption_folder(folder, args.date, pick_device(args.device), args.limit)
