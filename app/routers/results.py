"""
DolphinID — Results router.

Handles individual result actions (serve images, list crops) and
crop-level review actions (approve, classify, reject).
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models.result import ProcessingResult, Crop
from app.services.gallery import gallery_service

router = APIRouter(prefix="/api/results", tags=["Results"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    """Request to classify a crop to a known individual."""
    individual_label: str
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_result_status(result_id: int, db: Session):
    """
    After a crop status change, check whether ALL crops of the parent result
    have been resolved (i.e. none are still 'pending').
    If so, set the result to 'cataloged' (at least one approved/classified)
    or 'discarded' (all discarded).
    """
    crops = db.exec(select(Crop).where(Crop.result_id == result_id)).all()
    all_resolved = all(c.status != "pending" for c in crops)
    any_approved = any(c.status in ("approved", "classified") for c in crops)
    if all_resolved:
        result = db.get(ProcessingResult, result_id)
        result.status = "cataloged" if any_approved else "discarded"
        db.add(result)
        db.commit()


# ---------------------------------------------------------------------------
# Result-level endpoints
# ---------------------------------------------------------------------------

@router.get("/{result_id}/original")
def serve_original(result_id: int, db: Session = Depends(get_session)):
    """Serve the original image for a result."""
    result = db.get(ProcessingResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    path = Path(result.original_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original file not found on disk")

    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/{result_id}/crops")
def get_result_crops(result_id: int, db: Session = Depends(get_session)):
    """Return all crops for a given result with their data."""
    result = db.get(ProcessingResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    crops = db.exec(
        select(Crop).where(Crop.result_id == result_id).order_by(Crop.crop_index)
    ).all()

    items = []
    for c in crops:
        items.append({
            "id": c.id,
            "crop_index": c.crop_index,
            "crop_path": c.crop_path,
            "yolo_confidence": c.yolo_confidence,
            "bbox": {"x": c.bbox_x, "y": c.bbox_y, "w": c.bbox_w, "h": c.bbox_h},
            "predicted_id": c.predicted_id,
            "match_confidence": c.match_confidence,
            "top5_matches": json.loads(c.top5_matches) if c.top5_matches else [],
            "confirmed_id": c.confirmed_id,
            "status": c.status,
            "reviewer_notes": c.reviewer_notes,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        })

    return {
        "result_id": result_id,
        "original_filename": result.original_filename,
        "status": result.status,
        "total_crops": len(items),
        "crops": items,
    }


@router.post("/{result_id}/discard")
def discard_result(result_id: int, db: Session = Depends(get_session)):
    """Discard an entire image — sets the result and all pending crops to 'discarded'."""
    result = db.get(ProcessingResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    result.status = "discarded"
    db.add(result)

    # Discard all pending crops belonging to this result
    crops = db.exec(select(Crop).where(Crop.result_id == result_id)).all()
    for c in crops:
        if c.status == "pending":
            c.status = "discarded"
            c.reviewed_at = datetime.utcnow()
            db.add(c)

    db.commit()
    return {"status": "ok", "result_id": result_id, "new_status": "discarded"}


# ---------------------------------------------------------------------------
# Crop-level endpoints
# ---------------------------------------------------------------------------

@router.get("/crop/{crop_id}/image")
def serve_crop_image(crop_id: int, db: Session = Depends(get_session)):
    """Serve the crop image file."""
    crop = db.get(Crop, crop_id)
    if not crop or not crop.crop_path:
        raise HTTPException(status_code=404, detail="Crop not found")

    path = Path(crop.crop_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Crop file not found on disk")

    return FileResponse(str(path), media_type="image/jpeg")


@router.post("/crop/{crop_id}/approve")
def approve_crop(crop_id: int, db: Session = Depends(get_session)):
    """
    Approve a crop without assigning an individual.

    Sets crop.status='approved', adds it to the catalog (unclassified),
    and checks whether the parent result is fully resolved.
    """
    crop = db.get(Crop, crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")

    result = db.get(ProcessingResult, crop.result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Parent result not found")

    crop.status = "approved"
    crop.reviewed_at = datetime.utcnow()
    db.add(crop)
    db.commit()

    # Add to catalog (unclassified)
    gallery_service.add_to_catalog(crop, result, individual_label=None, db=db)

    _update_result_status(crop.result_id, db)

    return {"status": "ok", "crop_id": crop.id, "new_status": "approved"}


@router.post("/crop/{crop_id}/classify")
def classify_crop(crop_id: int, req: ClassifyRequest, db: Session = Depends(get_session)):
    """
    Approve and classify a crop, assigning it to a known individual.

    Sets crop.status='classified', crop.confirmed_id=label, adds it to
    the catalog under the given individual, and checks result resolution.
    """
    crop = db.get(Crop, crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")

    result = db.get(ProcessingResult, crop.result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Parent result not found")

    crop.status = "classified"
    crop.confirmed_id = req.individual_label
    crop.reviewer_notes = req.notes
    crop.reviewed_at = datetime.utcnow()
    db.add(crop)
    db.commit()

    # Add to catalog under the specified individual
    gallery_service.add_to_catalog(crop, result, individual_label=req.individual_label, db=db)

    _update_result_status(crop.result_id, db)

    return {
        "status": "ok",
        "crop_id": crop.id,
        "new_status": "classified",
        "confirmed_id": req.individual_label,
    }


@router.post("/crop/{crop_id}/reject")
def reject_crop(crop_id: int, db: Session = Depends(get_session)):
    """
    Discard a crop (e.g. false positive detection).

    Sets crop.status='discarded' and checks whether the parent result
    is fully resolved.
    """
    crop = db.get(Crop, crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")

    crop.status = "discarded"
    crop.reviewed_at = datetime.utcnow()
    db.add(crop)
    db.commit()

    _update_result_status(crop.result_id, db)

    return {"status": "ok", "crop_id": crop.id, "new_status": "discarded"}
