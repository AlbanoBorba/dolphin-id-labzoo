"""
DolphinID — Gallery router.

Provides endpoints for exploring the gallery of known individuals,
viewing their reference photos, and visualizing the embedding space.
Also exposes catalog management endpoints for DB-backed images and crops.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.database import get_session
from app.models.catalog import CatalogImage, CatalogCrop
from app.models.individual import Individual
from app.services.gallery import gallery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gallery", tags=["Gallery"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ClassifyCatalogImageRequest(BaseModel):
    """Request to assign an individual label to a catalog image."""
    individual_label: str


# ---------------------------------------------------------------------------
# PKL-based gallery endpoints (backward compatibility)
# ---------------------------------------------------------------------------

@router.get("/individuals")
def list_individuals(db: Session = Depends(get_session)):
    """
    List all known individuals with their photo counts.

    Merges PKL-based gallery counts with DB catalog image counts so the
    frontend gets a unified view.
    """
    # --- PKL-based data ---
    pkl_individuals: dict[str, dict] = {}
    if gallery_service.is_loaded or True:
        try:
            if not gallery_service.is_loaded:
                gallery_service.load()
            gallery = gallery_service.gallery
            for label in gallery.get_individual_labels():
                entries = gallery.get_individual_entries(label)
                pkl_individuals[label] = {
                    "label": label,
                    "pkl_images": len(entries),
                    "catalog_images": 0,
                    "total_images": len(entries),
                    "sample_path": entries[0].image_path if entries else None,
                }
        except FileNotFoundError:
            pass  # No PKL file — rely solely on DB data

    # --- DB catalog counts ---
    catalog_counts = db.exec(
        select(CatalogImage.individual_label, func.count(CatalogImage.id))
        .where(CatalogImage.individual_label.isnot(None))  # noqa: E711
        .group_by(CatalogImage.individual_label)
    ).all()

    for label, count in catalog_counts:
        if label in pkl_individuals:
            pkl_individuals[label]["catalog_images"] = count
            pkl_individuals[label]["total_images"] += count
        else:
            pkl_individuals[label] = {
                "label": label,
                "pkl_images": 0,
                "catalog_images": count,
                "total_images": count,
                "sample_path": None,
            }

    # --- DB individuals table (for nickname / notes) ---
    db_individuals = db.exec(select(Individual)).all()
    for ind in db_individuals:
        if ind.label not in pkl_individuals:
            pkl_individuals[ind.label] = {
                "label": ind.label,
                "pkl_images": 0,
                "catalog_images": 0,
                "total_images": 0,
                "sample_path": None,
            }
        pkl_individuals[ind.label]["nickname"] = ind.nickname
        pkl_individuals[ind.label]["notes"] = ind.notes

    individuals = sorted(pkl_individuals.values(), key=lambda x: x["label"])

    return {
        "total_individuals": len(individuals),
        "individuals": individuals,
    }


@router.get("/individuals/{label}")
def get_individual_detail(label: str, db: Session = Depends(get_session)):
    """Get detailed info for a specific individual including all gallery images."""
    # PKL images
    pkl_images = []
    try:
        if not gallery_service.is_loaded:
            gallery_service.load()
        gallery = gallery_service.gallery
        entries = gallery.get_individual_entries(label)
        for i, entry in enumerate(entries):
            resolved = gallery_service.resolve_image_path(entry.image_path)
            pkl_images.append({
                "index": i,
                "image_path": str(resolved),
                "has_file": resolved.exists(),
                "source": "pkl",
            })
    except (FileNotFoundError, RuntimeError):
        entries = []

    # Catalog images
    catalog_images_rows = db.exec(
        select(CatalogImage).where(CatalogImage.individual_label == label)
    ).all()
    catalog_items = []
    for ci in catalog_images_rows:
        catalog_items.append({
            "catalog_image_id": ci.id,
            "original_image_path": ci.original_image_path,
            "has_file": Path(ci.original_image_path).exists(),
            "added_at": ci.added_at.isoformat() if ci.added_at else None,
            "source": "catalog",
        })

    # Individual metadata from DB
    individual = db.exec(select(Individual).where(Individual.label == label)).first()

    if not pkl_images and not catalog_items and not individual:
        raise HTTPException(status_code=404, detail=f"Individual '{label}' not found")

    return {
        "label": label,
        "nickname": individual.nickname if individual else None,
        "notes": individual.notes if individual else None,
        "pkl_images": pkl_images,
        "catalog_images": catalog_items,
        "total_images": len(pkl_images) + len(catalog_items),
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


# ---------------------------------------------------------------------------
# Catalog endpoints (DB-backed)
# ---------------------------------------------------------------------------

@router.get("/catalog/images")
def list_catalog_images(db: Session = Depends(get_session)):
    """List all catalog images with their individual label and crop count."""
    images = db.exec(
        select(CatalogImage).order_by(CatalogImage.added_at.desc())
    ).all()

    items = []
    for img in images:
        crop_count = db.exec(
            select(func.count(CatalogCrop.id))
            .where(CatalogCrop.catalog_image_id == img.id)
        ).one()
        items.append({
            "id": img.id,
            "individual_label": img.individual_label,
            "original_image_path": img.original_image_path,
            "source_session_id": img.source_session_id,
            "source_result_id": img.source_result_id,
            "crop_count": crop_count,
            "added_at": img.added_at.isoformat() if img.added_at else None,
        })

    return {"total": len(items), "images": items}


@router.get("/catalog/unclassified")
def list_unclassified_catalog_images(db: Session = Depends(get_session)):
    """List catalog images that have not been assigned to any individual."""
    images = db.exec(
        select(CatalogImage)
        .where(CatalogImage.individual_label.is_(None))  # noqa: E711
        .order_by(CatalogImage.added_at.desc())
    ).all()

    items = []
    for img in images:
        crop_count = db.exec(
            select(func.count(CatalogCrop.id))
            .where(CatalogCrop.catalog_image_id == img.id)
        ).one()
        items.append({
            "id": img.id,
            "original_image_path": img.original_image_path,
            "source_session_id": img.source_session_id,
            "source_result_id": img.source_result_id,
            "crop_count": crop_count,
            "added_at": img.added_at.isoformat() if img.added_at else None,
        })

    return {"total": len(items), "images": items}


@router.get("/catalog/images/{image_id}/original")
def serve_catalog_original(image_id: int, db: Session = Depends(get_session)):
    """Serve the original image for a catalog image."""
    catalog_image = db.get(CatalogImage, image_id)
    if not catalog_image:
        raise HTTPException(status_code=404, detail="Catalog image not found")

    path = Path(catalog_image.original_image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/catalog/images/{image_id}/crops")
def list_catalog_image_crops(image_id: int, db: Session = Depends(get_session)):
    """List all crops for a catalog image."""
    catalog_image = db.get(CatalogImage, image_id)
    if not catalog_image:
        raise HTTPException(status_code=404, detail="Catalog image not found")

    crops = db.exec(
        select(CatalogCrop).where(CatalogCrop.catalog_image_id == image_id)
    ).all()

    items = []
    for c in crops:
        items.append({
            "id": c.id,
            "crop_path": c.crop_path,
            "bbox": {
                "x": c.bbox_x, "y": c.bbox_y,
                "w": c.bbox_w, "h": c.bbox_h,
            } if c.bbox_x is not None else None,
            "has_embedding": c.embedding_json is not None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "catalog_image_id": image_id,
        "individual_label": catalog_image.individual_label,
        "total_crops": len(items),
        "crops": items,
    }


@router.get("/catalog/crops/{crop_id}/image")
def serve_catalog_crop_image(crop_id: int, db: Session = Depends(get_session)):
    """Serve a catalog crop image file."""
    crop = db.get(CatalogCrop, crop_id)
    if not crop or not crop.crop_path:
        raise HTTPException(status_code=404, detail="Catalog crop not found")

    path = Path(crop.crop_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Crop file not found on disk")

    return FileResponse(str(path), media_type="image/jpeg")


@router.post("/catalog/images/{image_id}/classify")
def classify_catalog_image(
    image_id: int,
    req: ClassifyCatalogImageRequest,
    db: Session = Depends(get_session),
):
    """Assign (or change) an individual label for a catalog image."""
    catalog_image = db.get(CatalogImage, image_id)
    if not catalog_image:
        raise HTTPException(status_code=404, detail="Catalog image not found")

    catalog_image.individual_label = req.individual_label
    db.add(catalog_image)
    db.commit()
    db.refresh(catalog_image)

    return {
        "status": "ok",
        "catalog_image_id": catalog_image.id,
        "individual_label": catalog_image.individual_label,
    }


# ---------------------------------------------------------------------------
# Index management endpoints
# ---------------------------------------------------------------------------

@router.post("/rebuild-index")
def rebuild_index(db: Session = Depends(get_session)):
    """Rebuild the FAISS index from catalog data stored in the database."""
    stats = gallery_service.rebuild_index_from_db(db)
    return {"status": "ok", "stats": stats}


@router.get("/index-status")
def get_index_status(db: Session = Depends(get_session)):
    """Return the current status of the gallery / FAISS index."""
    status = gallery_service.get_index_status(db)
    return status
