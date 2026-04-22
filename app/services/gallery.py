"""
DolphinID — Gallery service.

Loads and manages the dolphin gallery (PKL file with embeddings + metadata).
This is the core reference data used for matching unknown dolphins.
"""
import pickle
import logging
from pathlib import Path
from dataclasses import dataclass, field

import torch
import torch.nn.functional as F
import numpy as np

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


# Singleton instance
gallery_service = GalleryService()
