"""
DolphinID — Application configuration.

All paths and settings are centralized here. The application expects:
  - A trained model checkpoint (.ckpt)
  - A gallery pickle file (dolphin_gallery.pkl)
  - A YOLO-World weights file (.pt)

These are configured via environment variables or the defaults below.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


def _project_root() -> Path:
    """Return the dolphin-id project root directory."""
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with sensible defaults for local desktop use."""

    # --- Project paths ---
    project_root: Path = _project_root()
    data_dir: Path = _project_root() / "data"

    # --- ML Artifacts ---
    model_checkpoint: Path = _project_root() / "data" / "models" / "best_model_overall.ckpt"
    gallery_pkl: Path = _project_root() / "data" / "gallery" / "dolphin_gallery.pkl"
    yolo_weights: Path = _project_root() / "data" / "models" / "yolov8x-worldv2.pt"

    # Gallery images base path — the PKL stores relative paths
    # that are resolved against this directory (e.g. the train-model-cli root)
    gallery_base_path: Path = _project_root().parent / "reId-scripts" / "train-model-cli"

    # --- Database ---
    database_url: str = ""

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000

    # --- YOLO Detection ---
    yolo_confidence: float = 0.15
    yolo_crop_padding: int = 20
    yolo_classes: list[str] = ["dolphin", "dorsal fin", "dolphin dorsal fin", "cetacean"]

    # --- Inference ---
    embedding_size: int = 512
    top_k_matches: int = 5

    class Config:
        env_prefix = "DOLPHIN_ID_"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "dolphin_id.db"

    @property
    def crops_dir(self) -> Path:
        return self.data_dir / "crops"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def gallery_dir(self) -> Path:
        return self.data_dir / "gallery"

    def resolve_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.db_path}"

    def ensure_directories(self) -> None:
        """Create all required data directories."""
        for d in [self.data_dir, self.crops_dir, self.uploads_dir, self.models_dir, self.gallery_dir, self.db_path.parent]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
