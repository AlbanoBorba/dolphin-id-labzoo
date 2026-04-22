"""
DolphinID — Gallery router.

Provides endpoints for exploring the gallery of known individuals,
viewing their reference photos, and visualizing the embedding space.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
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
def get_embedding_map(max_points: int = Query(default=500, le=2000)):
    """
    Get a 2D projection (t-SNE) of all gallery embeddings for visualization.

    This is computed on-demand and cached in memory.
    """
    if not gallery_service.is_loaded:
        gallery_service.load()

    gallery = gallery_service.gallery
    if gallery.size == 0:
        return {"points": []}

    import numpy as np
    from sklearn.manifold import TSNE

    # Subsample if too many points
    n = min(max_points, gallery.size)
    if n < gallery.size:
        indices = np.random.choice(gallery.size, n, replace=False)
        embeddings = gallery.embeddings_tensor[indices].numpy()
        labels = [gallery.labels[i] for i in indices]
    else:
        embeddings = gallery.embeddings_tensor.numpy()
        labels = gallery.labels

    # Compute t-SNE
    perplexity = min(30, n - 1) if n > 1 else 1
    tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, max_iter=1000)
    coords = tsne.fit_transform(embeddings)

    points = []
    for i in range(len(labels)):
        points.append({
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
            "label": labels[i],
        })

    # Get unique labels for color mapping
    unique_labels = sorted(set(labels))

    return {
        "total_points": len(points),
        "unique_labels": unique_labels,
        "points": points,
    }
