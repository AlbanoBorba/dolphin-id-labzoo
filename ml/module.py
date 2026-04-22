"""
DolphinID — Lightning Module (for checkpoint loading).

Minimal version of train-model-cli/src/models/module.py.
Only the structure needed to load .ckpt files — no training logic.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import pytorch_lightning as pl
import torchmetrics
from ml.arcface import DolphinReIDModel


class DolphinReIDLightningModule(pl.LightningModule):
    """
    Lightning wrapper around DolphinReIDModel.

    This class exists solely to allow loading .ckpt checkpoints produced
    by train-model-cli. Only the __init__ and forward methods matter for inference.
    """

    def __init__(
        self,
        num_classes: int = 1,
        learning_rate: float = 1e-3,
        embedding_size: int = 512,
        weight_decay: float = 1e-4,
        class_weights: torch.Tensor | None = None,
    ):
        super().__init__()
        self.save_hyperparameters(ignore=["class_weights"])
        self.model = DolphinReIDModel(num_classes, embedding_size)

        # These are needed so the checkpoint can be loaded, but we never train here
        self.criterion_arcface = nn.CrossEntropyLoss(
            weight=class_weights,
            label_smoothing=0.1,
        )
        self.triplet_margin = 0.5
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay

        task = "multiclass"
        self.train_acc = torchmetrics.Accuracy(task=task, num_classes=num_classes)
        self.train_f1 = torchmetrics.F1Score(task=task, num_classes=num_classes, average="weighted")
        self.val_acc = torchmetrics.Accuracy(task=task, num_classes=num_classes)
        self.val_f1 = torchmetrics.F1Score(task=task, num_classes=num_classes, average="weighted")

        self._val_embeddings: list[torch.Tensor] = []
        self._val_labels: list[torch.Tensor] = []

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    def configure_optimizers(self):
        optimizer = optim.AdamW(self.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=5)
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "monitor": "val_retrieval_mAP"},
        }
