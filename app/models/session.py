"""
DolphinID — ProcessingSession model.

Represents a batch processing session (a folder of images submitted for identification).
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ProcessingSession(SQLModel, table=True):
    """A processing session groups a batch of images submitted together."""

    __tablename__ = "sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    year: int
    notes: Optional[str] = None
    source_dir: str
    status: str = Field(default="pending")  # pending | processing | completed | failed
    total_images: int = Field(default=0)
    processed_images: int = Field(default=0)
    failed_images: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
