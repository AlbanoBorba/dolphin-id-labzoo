"""
DolphinID — Gallery service.

Loads and manages the dolphin gallery (PKL file with embeddings + metadata).
This is the core reference data used for matching unknown dolphins.

Provides methods to:
  - Load gallery from PKL file
  - Find matches against the FAISS/cosine-similarity index
  - Import PKL entries into the catalog DB
  - Add new catalog entries from approved crops
  - Rebuild the FAISS index from the DB
"""
import json
import pickle
import logging
import shutil
import time
from pathlib import Path
from dataclasses import dataclass, field

import torch
import torch.nn.functional as F
import numpy as np

from sqlmodel import Session, select

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GalleryEntry:
    """A single entry in the dolphin gallery."""
    label: str           # e.g. "#5"
    embedding: np.ndarray  # 512-dim vector
    image_path: str      # Path to the source crop image


@dataclass
class GalleryData:
    """Loaded gallery with pre-computed tensors for fast matching."""
    entries: list[GalleryEntry] = field(default_factory=list)
    embeddings_tensor: torch.Tensor | None = None  # [N x 512] normalized
    labels: list[str] = field(default_factory=list)
    individuals: dict[str, list[int]] = field(default_factory=dict)  # label -> [indices]
    embedding_map_2d: np.ndarray | None = None  # [N x 2] UMAP projection (cached)

    @property
    def size(self) -> int:
        return len(self.entries)

    def get_individual_labels(self) -> list[str]:
        """Return sorted list of unique individual labels."""
        return sorted(self.individuals.keys())

    def get_individual_entries(self, label: str) -> list[GalleryEntry]:
        """Return all gallery entries for a given individual."""
        indices = self.individuals.get(label, [])
        return [self.entries[i] for i in indices]


class GalleryService:
    """Manages loading and querying the dolphin gallery."""

    def __init__(self):
        self._gallery: GalleryData | None = None

    @property
    def is_loaded(self) -> bool:
        return self._gallery is not None

    @property
    def gallery(self) -> GalleryData:
        if self._gallery is None:
            raise RuntimeError("Gallery not loaded. Call load() first.")
        return self._gallery

    def load(self, pkl_path: Path | None = None) -> GalleryData:
        """Load gallery from PKL file."""
        path = pkl_path or settings.gallery_pkl
        if not path.exists():
            raise FileNotFoundError(f"Gallery file not found: {path}")

        logger.info(f"Loading gallery from {path}...")
        with open(path, "rb") as f:
            raw_gallery = pickle.load(f)

        entries: list[GalleryEntry] = []
        embeddings_list: list[torch.Tensor] = []
        labels: list[str] = []
        individuals: dict[str, list[int]] = {}

        for i, item in enumerate(raw_gallery):
            label = item["label"]
            embedding = np.array(item["embedding"], dtype=np.float32)
            # PKL uses 'path' key with relative paths (e.g. experiments/...)
            image_path = item.get("path", item.get("image_path", item.get("crop_path", "")))

            entries.append(GalleryEntry(label=label, embedding=embedding, image_path=image_path))
            emb_tensor = F.normalize(torch.tensor(embedding).float(), p=2, dim=0)
            embeddings_list.append(emb_tensor)
            labels.append(label)

            if label not in individuals:
                individuals[label] = []
            individuals[label].append(i)

        embeddings_tensor = torch.stack(embeddings_list) if embeddings_list else torch.empty(0, settings.embedding_size)

        self._gallery = GalleryData(
            entries=entries,
            embeddings_tensor=embeddings_tensor,
            labels=labels,
            individuals=individuals,
        )

        logger.info(f"Gallery loaded: {len(entries)} vectors, {len(individuals)} individuals")
        return self._gallery

    def resolve_image_path(self, relative_path: str) -> Path:
        """
        Resolve a gallery image path.

        PKL stores relative paths like 'experiments/train_.../dataset_crops/...'.
        These are resolved against gallery_base_path from settings.
        """
        p = Path(relative_path)
        if p.is_absolute() and p.exists():
            return p

        # Resolve against the configured base path
        resolved = settings.gallery_base_path / relative_path
        return resolved

    def compute_2d_projection(self) -> np.ndarray:
        """
        Compute a 2D UMAP projection of all gallery embeddings.

        The result is cached in GalleryData.embedding_map_2d so subsequent
        calls return instantly. Uses random_state=42 for deterministic output.
        """
        gallery = self.gallery

        # Return cached projection if available
        if gallery.embedding_map_2d is not None:
            return gallery.embedding_map_2d

        if gallery.size == 0:
            gallery.embedding_map_2d = np.empty((0, 2), dtype=np.float32)
            return gallery.embedding_map_2d

        import umap

        logger.info(f"Computing UMAP 2D projection for {gallery.size} embeddings...")
        t0 = time.time()

        embeddings = gallery.embeddings_tensor.numpy()
        n_neighbors = min(15, gallery.size - 1) if gallery.size > 1 else 1

        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=0.3,
            metric="cosine",
            random_state=42,
        )
        coords = reducer.fit_transform(embeddings).astype(np.float32)

        gallery.embedding_map_2d = coords
        elapsed = time.time() - t0
        logger.info(f"UMAP projection computed in {elapsed:.1f}s")

        return coords

    def find_matches(self, query_embedding: torch.Tensor, top_k: int = 5) -> list[dict]:
        """
        Find the top-k most similar individuals in the gallery.

        Args:
            query_embedding: Normalized embedding vector [512]
            top_k: Number of top matches to return

        Returns:
            List of {"id": str, "score": float} sorted by score descending
        """
        gallery = self.gallery
        if gallery.embeddings_tensor is None or gallery.size == 0:
            return []

        # Ensure normalized
        query = F.normalize(query_embedding.unsqueeze(0), p=2, dim=1)  # [1 x 512]

        # Cosine similarity
        similarities = torch.mm(query, gallery.embeddings_tensor.t()).squeeze(0)  # [N]

        # Get top-k
        top_scores, top_indices = similarities.topk(min(top_k * 3, gallery.size))

        # Deduplicate by individual (take best score per individual)
        seen: dict[str, float] = {}
        for score, idx in zip(top_scores.tolist(), top_indices.tolist()):
            label = gallery.labels[idx]
            if label not in seen:
                seen[label] = score
            if len(seen) >= top_k:
                break

        return [{"id": label, "score": round(score, 4)} for label, score in seen.items()]

    # ------------------------------------------------------------------
    # Catalog management methods
    # ------------------------------------------------------------------

    def import_from_pkl(self, db: Session) -> int:
        """
        Import all PKL gallery entries into the catalog DB.

        For each entry, creates:
          - Individual (if label doesn't already exist)
          - CatalogImage (PKL entries ARE crops, so this points to the crop path)
          - CatalogCrop (same crop path, with the stored embedding)

        Returns:
            Number of entries imported.
        """
        from app.models.individual import Individual
        from app.models.catalog import CatalogImage, CatalogCrop

        gallery = self.gallery  # Raises if not loaded

        imported = 0
        seen_labels: set[str] = set()

        for entry in gallery.entries:
            resolved_path = str(self.resolve_image_path(entry.image_path))

            # Create Individual if not already present
            if entry.label not in seen_labels:
                existing = db.exec(
                    select(Individual).where(Individual.label == entry.label)
                ).first()
                if existing is None:
                    db.add(Individual(label=entry.label))
                seen_labels.add(entry.label)

            # Create CatalogImage — PKL entries are crops, so both image and
            # crop point to the same file path
            catalog_image = CatalogImage(
                individual_label=entry.label,
                original_image_path=resolved_path,
            )
            db.add(catalog_image)
            db.flush()  # Need the id for CatalogCrop FK

            # Create CatalogCrop with the embedding
            catalog_crop = CatalogCrop(
                catalog_image_id=catalog_image.id,
                crop_path=resolved_path,
                embedding_json=json.dumps(entry.embedding.tolist()),
                bbox_x=None,
                bbox_y=None,
                bbox_w=None,
                bbox_h=None,
            )
            db.add(catalog_crop)
            imported += 1

        db.commit()
        logger.info(f"Imported {imported} PKL entries into catalog DB")
        return imported

    def add_to_catalog(
        self,
        crop: "Crop",
        result: "ProcessingResult",
        individual_label: str | None,
        db: Session,
    ) -> "CatalogImage":
        """
        Add an approved crop to the catalog.

        Copies files to the catalog directory structure, creates DB entries,
        and extracts a fresh embedding from the crop image.

        Args:
            crop: The approved Crop entry
            result: The parent ProcessingResult (for original image + session info)
            individual_label: Label to assign (e.g. "#5"), or None for unclassified
            db: Database session

        Returns:
            The newly created CatalogImage.
        """
        from app.models.individual import Individual
        from app.models.catalog import CatalogImage, CatalogCrop
        from app.services import identification

        subfolder = individual_label if individual_label else "unclassified"

        # Copy original image to catalog originals directory
        original_src = Path(result.original_path)
        originals_dest_dir = settings.catalog_originals_dir / subfolder
        originals_dest_dir.mkdir(parents=True, exist_ok=True)
        original_dest = originals_dest_dir / original_src.name
        # Avoid overwriting — add suffix if file exists
        original_dest = _unique_path(original_dest)
        shutil.copy2(str(original_src), str(original_dest))

        # Copy crop image to catalog crops directory
        crop_src = Path(crop.crop_path)
        crops_dest_dir = settings.catalog_crops_dir / subfolder
        crops_dest_dir.mkdir(parents=True, exist_ok=True)
        crop_dest = crops_dest_dir / crop_src.name
        crop_dest = _unique_path(crop_dest)
        shutil.copy2(str(crop_src), str(crop_dest))

        # Create Individual if needed
        if individual_label is not None:
            existing = db.exec(
                select(Individual).where(Individual.label == individual_label)
            ).first()
            if existing is None:
                db.add(Individual(label=individual_label))

        # Create CatalogImage
        catalog_image = CatalogImage(
            individual_label=individual_label,
            original_image_path=str(original_dest),
            source_session_id=result.session_id,
            source_result_id=result.id,
        )
        db.add(catalog_image)
        db.flush()

        # Extract fresh embedding from the crop
        embedding = identification.extract_embedding(str(crop_dest))
        embedding_json = json.dumps(embedding.tolist())

        # Create CatalogCrop
        catalog_crop = CatalogCrop(
            catalog_image_id=catalog_image.id,
            crop_path=str(crop_dest),
            bbox_x=crop.bbox_x,
            bbox_y=crop.bbox_y,
            bbox_w=crop.bbox_w,
            bbox_h=crop.bbox_h,
            embedding_json=embedding_json,
        )
        db.add(catalog_crop)
        db.commit()

        logger.info(
            f"Added crop {crop.id} to catalog as CatalogImage {catalog_image.id} "
            f"(label={individual_label or 'unclassified'})"
        )
        return catalog_image

    def rebuild_index_from_db(self, db: Session) -> dict:
        """
        Rebuild the in-memory gallery index from the catalog DB.

        Queries all CatalogCrop entries with non-null embedding_json,
        joins with CatalogImage to get individual_label, and reconstructs
        the full GalleryData (entries, embeddings_tensor, labels, individuals).

        Also resets the cached UMAP projection so it will be recomputed
        on next call to compute_2d_projection().

        Returns:
            Stats dict with keys: total_entries, total_individuals.
        """
        from app.models.catalog import CatalogImage, CatalogCrop

        # Query all catalog crops with embeddings, joined to their parent image
        statement = (
            select(CatalogCrop, CatalogImage)
            .join(CatalogImage, CatalogCrop.catalog_image_id == CatalogImage.id)
            .where(CatalogCrop.embedding_json.isnot(None))  # noqa: E711
        )
        rows = db.exec(statement).all()

        entries: list[GalleryEntry] = []
        embeddings_list: list[torch.Tensor] = []
        labels: list[str] = []
        individuals: dict[str, list[int]] = {}

        for i, (catalog_crop, catalog_image) in enumerate(rows):
            label = catalog_image.individual_label or "unclassified"
            embedding = np.array(json.loads(catalog_crop.embedding_json), dtype=np.float32)

            entries.append(GalleryEntry(
                label=label,
                embedding=embedding,
                image_path=catalog_crop.crop_path,
            ))
            emb_tensor = F.normalize(torch.tensor(embedding).float(), p=2, dim=0)
            embeddings_list.append(emb_tensor)
            labels.append(label)

            if label not in individuals:
                individuals[label] = []
            individuals[label].append(i)

        embeddings_tensor = (
            torch.stack(embeddings_list)
            if embeddings_list
            else torch.empty(0, settings.embedding_size)
        )

        self._gallery = GalleryData(
            entries=entries,
            embeddings_tensor=embeddings_tensor,
            labels=labels,
            individuals=individuals,
            embedding_map_2d=None,  # Reset cached projection
        )

        stats = {
            "total_entries": len(entries),
            "total_individuals": len(individuals),
        }
        logger.info(
            f"Gallery index rebuilt from DB: {stats['total_entries']} entries, "
            f"{stats['total_individuals']} individuals"
        )
        return stats

    def get_index_status(self, db: Session) -> dict:
        """
        Return current index status: indexed vs DB counts.

        Returns:
            Dict with keys:
              - indexed: number of embeddings in current in-memory index
              - total_in_db: total CatalogCrop entries with embeddings in DB
              - needs_rebuild: whether they differ
        """
        from app.models.catalog import CatalogCrop

        indexed = self._gallery.size if self._gallery else 0

        from sqlmodel import func
        total_in_db = db.exec(
            select(func.count(CatalogCrop.id)).where(
                CatalogCrop.embedding_json.isnot(None)  # noqa: E711
            )
        ).one()

        return {
            "indexed": indexed,
            "total_in_db": total_in_db,
            "needs_rebuild": indexed != total_in_db,
        }


def _unique_path(path: Path) -> Path:
    """Return a unique file path by appending _1, _2, etc. if the path exists."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# Singleton instance
gallery_service = GalleryService()
