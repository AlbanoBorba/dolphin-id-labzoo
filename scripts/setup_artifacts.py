#!/usr/bin/env python
"""
DolphinID — Setup script for ML artifacts.

Copies the trained model checkpoint, gallery PKL, and YOLO weights
from the train-model-cli experiments directory to dolphin-id/data/.

Usage:
    python scripts/setup_artifacts.py --source ../reId-scripts/train-model-cli

This script is designed to be run once on the lab machine to set up
the required ML artifacts without making them public.
"""
import argparse
import shutil
from pathlib import Path


def find_best_model(experiments_dir: Path) -> Path | None:
    """Find the best model checkpoint across all experiment directories."""
    # Look for the known best experiment first
    priority_dirs = [
        "train_catalogo_completo_hard_mining_v5_true_metrics_mAP",
    ]

    for dirname in priority_dirs:
        ckpt = experiments_dir / dirname / "best_model_overall.ckpt"
        if ckpt.exists():
            return ckpt

    # Fallback: search any experiment dir
    for exp_dir in sorted(experiments_dir.iterdir(), reverse=True):
        if exp_dir.is_dir():
            ckpt = exp_dir / "best_model_overall.ckpt"
            if ckpt.exists():
                return ckpt

    return None


def find_gallery(experiments_dir: Path) -> Path | None:
    """Find the gallery PKL file."""
    priority_dirs = [
        "train_catalogo_completo_hard_mining_v5_true_metrics_mAP",
    ]

    for dirname in priority_dirs:
        pkl = experiments_dir / dirname / "dolphin_gallery.pkl"
        if pkl.exists():
            return pkl

    for exp_dir in sorted(experiments_dir.iterdir(), reverse=True):
        if exp_dir.is_dir():
            pkl = exp_dir / "dolphin_gallery.pkl"
            if pkl.exists():
                return pkl

    return None


def find_yolo_weights(source_dir: Path) -> Path | None:
    """Find YOLO-World weights file."""
    for name in ["yolov8x-worldv2.pt", "yolov8l-worldv2.pt"]:
        path = source_dir / name
        if path.exists():
            return path
    return None


def main():
    parser = argparse.ArgumentParser(description="Setup DolphinID ML artifacts")
    parser.add_argument(
        "--source",
        type=str,
        default="../reId-scripts/train-model-cli",
        help="Path to train-model-cli directory (default: ../reId-scripts/train-model-cli)",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Destination data directory (default: ./data)",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve() if args.dest else Path(__file__).resolve().parent.parent / "data"

    print("🐬 DolphinID — Artifact Setup")
    print(f"   Source: {source}")
    print(f"   Destination: {dest}")
    print()

    if not source.exists():
        print(f"❌ Source directory not found: {source}")
        return

    experiments_dir = source / "experiments"
    if not experiments_dir.exists():
        print(f"❌ Experiments directory not found: {experiments_dir}")
        return

    # Create dest dirs
    models_dir = dest / "models"
    gallery_dir = dest / "gallery"
    models_dir.mkdir(parents=True, exist_ok=True)
    gallery_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy best model
    print("📦 Looking for best model checkpoint...")
    model_path = find_best_model(experiments_dir)
    if model_path:
        dest_model = models_dir / "best_model_overall.ckpt"
        print(f"   Found: {model_path}")
        print(f"   Copying to: {dest_model}")
        shutil.copy2(model_path, dest_model)
        print(f"   ✅ Model copied ({dest_model.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("   ⚠️  No model checkpoint found!")

    # 2. Copy gallery
    print("\n📦 Looking for gallery PKL...")
    gallery_path = find_gallery(experiments_dir)
    if gallery_path:
        dest_gallery = gallery_dir / "dolphin_gallery.pkl"
        print(f"   Found: {gallery_path}")
        print(f"   Copying to: {dest_gallery}")
        shutil.copy2(gallery_path, dest_gallery)
        print(f"   ✅ Gallery copied ({dest_gallery.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("   ⚠️  No gallery PKL found!")

    # 3. Copy YOLO weights
    print("\n📦 Looking for YOLO-World weights...")
    yolo_path = find_yolo_weights(source)
    if yolo_path:
        dest_yolo = models_dir / yolo_path.name
        print(f"   Found: {yolo_path}")
        print(f"   Copying to: {dest_yolo}")
        if not dest_yolo.exists():
            shutil.copy2(yolo_path, dest_yolo)
            print(f"   ✅ YOLO weights copied ({dest_yolo.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"   ℹ️  Already exists, skipping.")
    else:
        print("   ⚠️  No YOLO weights found!")

    print("\n🎉 Setup complete!")
    print(f"   Run the app with: python run.py")


if __name__ == "__main__":
    main()
