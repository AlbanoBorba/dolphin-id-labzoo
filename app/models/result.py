"""
DolphinID — ProcessingResult and Crop models.

ProcessingResult represents an original image submitted for processing.
Crop represents a single detection (dorsal fin crop) extracted from that image.
An image may have 0, 1, or multiple crops.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ProcessingResult(SQLModel, table=True):
    """
    Result for a single original image processed through the pipeline.

    Status flow:
      pending → no_detection  (YOLO found nothing above threshold)
      pending → needs_review   (1+ crops created, awaiting human review)
      needs_review → cataloged (at least 1 crop approved)
      needs_review → discarded (all crops discarded by reviewer)
      no_detection → discarded (reviewer confirms discard)
    """

    __tablename__ = "results"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)

    # Original image
    original_path: str
    original_filename: str

    # Status and crop summary
    status: str = Field(default="pending")  # pending|no_detection|needs_review|cataloged|discarded
    crop_count: int = Field(default=0)

    # EXIF metadata (extracted from original)
    capture_date: Optional[datetime] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None

    # Error tracking
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Crop(SQLModel, table=True):
    """
    A single detection crop extracted from an original image.

    Each crop goes through YOLO detection → embedding extraction → gallery matching.
    The reviewer then decides to approve (with or without classification) or discard.

    Status flow:
      pending → approved    (valid crop, no individual assigned yet)
      pending → classified  (valid crop, assigned to an individual)
      pending → discarded   (invalid crop, e.g. false positive)
      approved → classified (classified later from catalog)
    """

    __tablename__ = "crops"

    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: int = Field(foreign_key="results.id", index=True)
    crop_index: int = Field(default=0)

    # Crop image
    crop_path: str

    # YOLO detection
    yolo_confidence: float
    yolo_class: Optional[str] = None  # e.g. "dolphin dorsal fin", "dolphin"
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int

    # Identification (model prediction)
    predicted_id: Optional[str] = None
    match_confidence: Optional[float] = None
    top5_matches: Optional[str] = None  # JSON: [{"id": "#5", "score": 0.87}, ...]

    # Human review
    confirmed_id: Optional[str] = None
    status: str = Field(default="pending")  # pending|approved|classified|discarded
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
