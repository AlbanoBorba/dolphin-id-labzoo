"""
DolphinID — Results router.

Handles individual result actions (confirm, correct, serve images).
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models.result import ProcessingResult

router = APIRouter(prefix="/api/results", tags=["Results"])


class ConfirmRequest(BaseModel):
    """Request to confirm or correct a result."""
    confirmed_id: str
    notes: Optional[str] = None


@router.post("/{result_id}/confirm")
def confirm_result(result_id: int, req: ConfirmRequest, db: Session = Depends(get_session)):
    """Confirm or correct the identification of a result."""
    result = db.get(ProcessingResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    result.confirmed_id = req.confirmed_id
    result.reviewer_notes = req.notes
    result.reviewed_at = datetime.utcnow()
    result.status = "confirmed"

    db.add(result)
    db.commit()
    db.refresh(result)

    return {"status": "ok", "result_id": result.id, "confirmed_id": result.confirmed_id}


@router.get("/{result_id}/crop")
def serve_crop(result_id: int, db: Session = Depends(get_session)):
    """Serve the crop image for a result."""
    result = db.get(ProcessingResult, result_id)
    if not result or not result.crop_path:
        raise HTTPException(status_code=404, detail="Crop not found")

    path = Path(result.crop_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Crop file not found on disk")

    return FileResponse(str(path), media_type="image/jpeg")


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
