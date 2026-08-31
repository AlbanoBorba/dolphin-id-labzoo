"""
DolphinID — Catalog models.

CatalogImage represents an original image that has been accepted into the catalog.
CatalogCrop represents a crop (dorsal fin) extracted from that image, with its embedding.

An individual may have multiple CatalogImages.
A CatalogImage may have multiple CatalogCrops (rare, but possible).
CatalogImage.individual_label can be NULL for unclassified images.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CatalogImage(SQLModel, table=True):
    """
    An original image accepted into the catalog.

    Links to an Individual via label. If individual_label is NULL,
    the image is in the catalog but not yet classified to any individual
    (appears in the "Unclassified" section).
    """

    __tablename__ = "catalog_images"

    id: Optional[int] = Field(default=None, primary_key=True)
    individual_label: Optional[str] = Field(default=None, index=True)

    # Stored original image (copied to catalog dir when confirmed)
    original_image_path: str

    # Provenance
    source_session_id: Optional[int] = None
    source_result_id: Optional[int] = None

    added_at: datetime = Field(default_factory=datetime.utcnow)


class CatalogCrop(SQLModel, table=True):
    """
    A crop belonging to a catalog image, with its stored embedding.

    The embedding_json field stores the 512-dim vector as a JSON array,
    used to rebuild the FAISS index on demand.
    """

    __tablename__ = "catalog_crops"

    id: Optional[int] = Field(default=None, primary_key=True)
    catalog_image_id: int = Field(foreign_key="catalog_images.id", index=True)

    # Stored crop image
    crop_path: str

    # Bounding box in the original image
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_w: Optional[int] = None
    bbox_h: Optional[int] = None

    # Embedding for FAISS indexing
    embedding_json: Optional[str] = None  # JSON array of 512 floats

    created_at: datetime = Field(default_factory=datetime.utcnow)
