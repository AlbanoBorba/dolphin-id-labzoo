"""
DolphinID — Individual model.

Represents a known dolphin individual from the gallery.
"""
from typing import Optional

from sqlmodel import Field, SQLModel


class Individual(SQLModel, table=True):
    """A known dolphin individual, populated from the gallery PKL."""

    __tablename__ = "individuals"

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(unique=True, index=True)  # e.g. "#5", "#12"
    nickname: Optional[str] = None
    total_gallery_images: int = Field(default=0)
    notes: Optional[str] = None
