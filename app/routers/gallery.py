"""
DolphinID — Gallery router.

Provides endpoints for exploring the gallery of known individuals,
viewing their reference photos, and visualizing the embedding space.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.gallery import gallery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gallery", tags=["Gallery"])


@router.get("/individuals")
def list_individuals():
    """List all known individuals with their photo counts."""
    if not gallery_service.is_loaded:
        try:
            gallery_service.load()
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="Gallery not loaded — PKL file not found")

    gallery = gallery_service.gallery
    individuals = []

    for label in gallery.get_individual_labels():
        entries = gallery.get_individual_entries(label)
        individuals.append({
            "label": label,
            "total_images": len(entries),
            "sample_path": entries[0].image_path if entries else None,
        })

    return {
        "total_individuals": len(individuals),
        "total_images": gallery.size,
        "individuals": individuals,
    }


@router.get("/individuals/{label}")
def get_individual_detail(label: str):
    """Get detailed info for a specific individual including all gallery images."""
    if not gallery_service.is_loaded:
        gallery_service.load()

    gallery = gallery_service.gallery
    entries = gallery.get_individual_entries(label)

    if not entries:
        raise HTTPException(status_code=404, detail=f"Individual '{label}' not found in gallery")

    images = []
    for i, entry in enumerate(entries):
        resolved = gallery_service.resolve_image_path(entry.image_path)
        images.append({
            "index": i,
            "image_path": str(resolved),
            "has_file": resolved.exists(),
        })

    return {
        "label": label,
        "total_images": len(entries),
        "images": images,
    }


@router.get("/individuals/{label}/image/{index}")
def serve_gallery_image(label: str, index: int):
    """Serve a gallery image for a specific individual."""
    if not gallery_service.is_loaded:
        gallery_service.load()

    entries = gallery_service.gallery.get_individual_entries(label)
    if not entries or index >= len(entries):
        raise HTTPException(status_code=404, detail="Image not found")

    path = gallery_service.resolve_image_path(entries[index].image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image file not found: {path}")

    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/embedding-map")
def get_embedding_map():
    """
    Get a 2D UMAP projection of all gallery embeddings for interactive visualization.

    Returns cached coordinates computed at server startup. Each point includes
    an image URL so the frontend can display the photo on click.
    """
    if not gallery_service.is_loaded:
        gallery_service.load()

    gallery = gallery_service.gallery
    if gallery.size == 0:
        return {"total_points": 0, "unique_labels": [], "points": []}

    # Compute (or return cached) 2D projection
    coords = gallery_service.compute_2d_projection()

    # Build a mapping: for each (label, entry_index_within_label) -> global index
    # We need to find which image index within the individual this entry corresponds to
    label_counters: dict[str, int] = {}

    points = []
    for i in range(gallery.size):
        label = gallery.labels[i]

        # Track per-label image index for the image URL
        if label not in label_counters:
            label_counters[label] = 0
        img_idx = label_counters[label]
        label_counters[label] += 1

        import urllib.parse
        encoded_label = urllib.parse.quote(label, safe='')
        image_url = f"/api/gallery/individuals/{encoded_label}/image/{img_idx}"

        points.append({
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
            "label": label,
            "image_url": image_url,
        })

    unique_labels = sorted(set(gallery.labels))

    return {
        "total_points": len(points),
        "unique_labels": unique_labels,
        "points": points,
    }
