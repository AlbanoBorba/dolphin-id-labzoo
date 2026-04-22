"""
DolphinID — ProcessingResult model.

Represents the result of processing a single image through the pipeline.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ProcessingResult(SQLModel, table=True):
    """Result for a single image processed through detection + identification."""

    __tablename__ = "results"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)
    original_path: str
    original_filename: str
    crop_path: Optional[str] = None
    status: str = Field(default="pending")  # pending | detected | identified | confirmed | no_detection | failed

    # Detection (YOLO)
    yolo_confidence: Optional[float] = None
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_w: Optional[int] = None
    bbox_h: Optional[int] = None

    # Identification (EfficientNet + Gallery)
    predicted_id: Optional[str] = None
    match_confidence: Optional[float] = None
    top5_matches: Optional[str] = None  # JSON string: [{"id": "#5", "score": 0.87}, ...]

    # Human review
    confirmed_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # EXIF metadata
    capture_date: Optional[datetime] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None

    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
