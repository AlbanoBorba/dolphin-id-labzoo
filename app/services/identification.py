"""
DolphinID — Identification service (embedding extraction + gallery matching).

Loads the trained EfficientNet model and extracts embeddings for query images,
then matches against the pre-loaded gallery.
"""
import logging
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded singleton
_model = None
_device = None

# Standard inference transform (must match training preprocessing)
_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def _get_model():
    """Load trained model from checkpoint (lazy singleton)."""
    global _model, _device
    if _model is None:
        from ml.module import DolphinReIDLightningModule

        ckpt_path = settings.model_checkpoint
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {ckpt_path}")

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading model from {ckpt_path} on {_device}...")

        wrapper = DolphinReIDLightningModule.load_from_checkpoint(
            str(ckpt_path), map_location=_device, strict=False
        )
        _model = wrapper.model
        _model.eval()
        _model.to(_device)
        logger.info("Model loaded successfully.")
    return _model, _device


def unload_model() -> None:
    """Explicitly unload model to free VRAM."""
    global _model, _device
    if _model is not None:
        del _model
        _model = None
        if _device and _device.type == "cuda":
            torch.cuda.empty_cache()
        _device = None
        logger.info("Identification model unloaded.")


def extract_embedding(image_path: str | Path) -> torch.Tensor:
    """
    Extract a normalized 512-dim embedding from a crop image.

    Args:
        image_path: Path to the crop image

    Returns:
        Normalized embedding tensor [512]
    """
    model, device = _get_model()

    img = Image.open(str(image_path)).convert("RGB")
    img_tensor = _transform(img).unsqueeze(0).to(device)

    with torch.no_grad():
        embedding = model(img_tensor)
        embedding = F.normalize(embedding, p=2, dim=1)

    return embedding.squeeze(0).cpu()


def extract_embeddings_batch(image_paths: list[str | Path], batch_size: int = 16) -> list[torch.Tensor]:
    """
    Extract embeddings for multiple images efficiently in batches.

    Args:
        image_paths: List of paths to crop images
        batch_size: Number of images per GPU batch

    Returns:
        List of normalized embedding tensors [512]
    """
    model, device = _get_model()
    embeddings = []

    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i:i + batch_size]
        batch_tensors = []

        for path in batch_paths:
            try:
                img = Image.open(str(path)).convert("RGB")
                batch_tensors.append(_transform(img))
            except Exception as e:
                logger.warning(f"Could not load {path}: {e}")
                # Append a zero tensor as placeholder
                batch_tensors.append(torch.zeros(3, 224, 224))

        batch = torch.stack(batch_tensors).to(device)

        with torch.no_grad():
            emb = model(batch)
            emb = F.normalize(emb, p=2, dim=1)

        embeddings.extend(emb.cpu().unbind(0))

    return embeddings
