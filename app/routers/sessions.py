"""
DolphinID — Sessions router.

Handles creating processing sessions and tracking their progress.
Supports both folder-path-based and file-upload-based session creation.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models.session import ProcessingSession
from app.models.result import ProcessingResult
from app.services.pipeline import start_pipeline

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    """Request body for creating a new processing session."""
    source_dir: str
    year: int
    name: Optional[str] = None
    notes: Optional[str] = None


class SessionResponse(BaseModel):
    """Session data returned to the frontend."""
    id: int
    name: str
    year: int
    notes: Optional[str]
    source_dir: str
    status: str
    total_images: int
    processed_images: int
    failed_images: int
    created_at: str
    completed_at: Optional[str]


class SessionProgressResponse(BaseModel):
    """Detailed progress of a processing session."""
    id: int
    status: str
    total_images: int
    processed_images: int
    failed_images: int
    progress_percent: float
    status_breakdown: dict[str, int]


def _session_to_response(s: ProcessingSession) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        name=s.name,
        year=s.year,
        notes=s.notes,
        source_dir=s.source_dir,
        status=s.status,
        total_images=s.total_images,
        processed_images=s.processed_images,
        failed_images=s.failed_images,
        created_at=s.created_at.isoformat() if s.created_at else "",
        completed_at=s.completed_at.isoformat() if s.completed_at else None,
    )


@router.post("", response_model=SessionResponse)
def create_session(req: CreateSessionRequest, db: Session = Depends(get_session)):
    """Create a new processing session and start the pipeline."""
    source = Path(req.source_dir)
    if not source.exists():
        raise HTTPException(status_code=400, detail=f"Directory not found: {req.source_dir}")
    if not source.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {req.source_dir}")

    name = req.name or source.name
    session = ProcessingSession(
        name=name,
        year=req.year,
        notes=req.notes,
        source_dir=str(source),
        status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Start pipeline in background
    start_pipeline(session.id)

    return _session_to_response(session)


@router.get("", response_model=list[SessionResponse])
def list_sessions(db: Session = Depends(get_session)):
    """List all processing sessions, newest first."""
    sessions = db.exec(
        select(ProcessingSession).order_by(ProcessingSession.created_at.desc())
    ).all()
    return [_session_to_response(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionProgressResponse)
def get_session_progress(session_id: int, db: Session = Depends(get_session)):
    """Get detailed progress for a session."""
    session = db.get(ProcessingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Count results by status
    results = db.exec(
        select(ProcessingResult).where(ProcessingResult.session_id == session_id)
    ).all()

    breakdown: dict[str, int] = {}
    for r in results:
        breakdown[r.status] = breakdown.get(r.status, 0) + 1

    total = session.total_images or 1
    progress = (session.processed_images / total * 100) if total > 0 else 0

    return SessionProgressResponse(
        id=session.id,
        status=session.status,
        total_images=session.total_images,
        processed_images=session.processed_images,
        failed_images=session.failed_images,
        progress_percent=round(progress, 1),
        status_breakdown=breakdown,
    )


@router.get("/{session_id}/results")
def get_session_results(
    session_id: int,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    db: Session = Depends(get_session),
):
    """Get all results for a session with optional filtering."""
    session = db.get(ProcessingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    query = select(ProcessingResult).where(ProcessingResult.session_id == session_id)

    if status:
        query = query.where(ProcessingResult.status == status)

    results = db.exec(query.order_by(ProcessingResult.match_confidence.desc())).all()

    # Apply confidence filter in Python (SQLite doesn't handle None well with comparisons)
    if min_confidence is not None:
        results = [r for r in results if r.match_confidence and r.match_confidence >= min_confidence]

    items = []
    for r in results:
        top5 = json.loads(r.top5_matches) if r.top5_matches else []
        items.append({
            "id": r.id,
            "original_filename": r.original_filename,
            "original_path": r.original_path,
            "crop_path": r.crop_path,
            "status": r.status,
            "yolo_confidence": r.yolo_confidence,
            "predicted_id": r.predicted_id,
            "match_confidence": r.match_confidence,
            "top5_matches": top5,
            "confirmed_id": r.confirmed_id,
            "reviewer_notes": r.reviewer_notes,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        })

    return {"session_id": session_id, "total": len(items), "results": items}


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


@router.post("/upload", response_model=SessionResponse)
async def create_session_from_upload(
    files: list[UploadFile] = File(..., description="Image files to process"),
    year: int = Form(...),
    name: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    db: Session = Depends(get_session),
):
    """
    Create a new processing session from uploaded files.

    Accepts multiple image files via multipart form data,
    saves them to data/uploads/{session_id}/, and starts the pipeline.
    """
    # Filter to valid image files
    valid_files = [
        f for f in files
        if f.filename and Path(f.filename).suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not valid_files:
        raise HTTPException(
            status_code=400,
            detail="No valid image files found. Supported: JPG, PNG, BMP, TIFF, WEBP",
        )

    # Create session first to get an ID
    session_name = name or f"upload-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    session = ProcessingSession(
        name=session_name,
        year=year,
        notes=notes,
        source_dir="",  # Will be set after saving files
        status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Save uploaded files to data/uploads/{session_id}/
    upload_dir = settings.uploads_dir / str(session.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    for upload_file in valid_files:
        dest_path = upload_dir / upload_file.filename
        # Handle duplicate filenames
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = upload_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            content = await upload_file.read()
            with open(dest_path, "wb") as f:
                f.write(content)
            saved_count += 1
        except Exception as e:
            # Log but continue with other files
            import logging
            logging.getLogger(__name__).warning(f"Failed to save {upload_file.filename}: {e}")

    if saved_count == 0:
        # Clean up empty session
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=400, detail="Failed to save any files")

    # Update session with the upload directory as source
    session.source_dir = str(upload_dir)
    db.add(session)
    db.commit()
    db.refresh(session)

    # Start pipeline in background
    start_pipeline(session.id)

    return _session_to_response(session)

