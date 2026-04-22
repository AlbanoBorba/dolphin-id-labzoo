"""
DolphinID — Browse & Upload router.

Provides endpoints for:
  - Browsing local directories and listing images
  - Serving thumbnails from local paths
  - Uploading images directly from the browser
"""
import io
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from PIL import Image as PILImage

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browse", tags=["Browse"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
THUMBNAIL_SIZE = (200, 200)


@router.get("")
def browse_directory(path: str = Query(..., description="Absolute path to a directory")):
    """
    List image files in a local directory.

    Returns filenames and basic metadata for preview.
    """
    dir_path = Path(path)
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    images = []
    try:
        for f in sorted(dir_path.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                images.append({
                    "name": f.name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

    # Also list subdirectories
    subdirs = []
    try:
        for f in sorted(dir_path.iterdir()):
            if f.is_dir() and not f.name.startswith("."):
                # Count images in subdir (non-recursive for speed)
                img_count = sum(1 for c in f.iterdir()
                               if c.is_file() and c.suffix.lower() in IMAGE_EXTENSIONS)
                subdirs.append({
                    "name": f.name,
                    "path": str(f),
                    "image_count": img_count,
                })
    except PermissionError:
        pass

    return {
        "directory": str(dir_path),
        "parent": str(dir_path.parent) if dir_path.parent != dir_path else None,
        "total_images": len(images),
        "images": images,
        "subdirectories": subdirs,
    }


@router.get("/thumbnail")
def serve_thumbnail(
    path: str = Query(..., description="Absolute path to an image file"),
    size: int = Query(default=200, ge=50, le=800, description="Max thumbnail dimension"),
):
    """
    Generate and serve a thumbnail for a local image.

    Resizes the image to fit within `size x size` pixels while maintaining aspect ratio.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not an image file")

    try:
        img = PILImage.open(file_path)
        img.thumbnail((size, size), PILImage.Resampling.LANCZOS)

        # Convert to JPEG bytes
        buf = io.BytesIO()
        # Handle RGBA → RGB conversion for JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)

        return Response(
            content=buf.read(),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate thumbnail: {e}")


@router.get("/image")
def serve_full_image(path: str = Query(..., description="Absolute path to an image file")):
    """Serve a full-resolution local image."""
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.is_file() or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not a valid image file")

    return FileResponse(str(file_path), media_type="image/jpeg")
