"""
DolphinID — Individual model.

Represents a known dolphin individual from the gallery.
Image/crop counts are computed dynamically from CatalogImage/CatalogCrop tables.
"""
from typing import Optional

from sqlmodel import Field, SQLModel


class Individual(SQLModel, table=True):
    """A known dolphin individual."""

    __tablename__ = "individuals"

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(unique=True, index=True)  # e.g. "#5", "#12"
    nickname: Optional[str] = None
    notes: Optional[str] = None
