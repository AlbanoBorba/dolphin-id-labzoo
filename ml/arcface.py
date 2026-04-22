"""
DolphinID — ML model definitions.

Copied from train-model-cli/src/models/ with minimal changes.
These are needed to load .ckpt checkpoints for inference.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models


class ArcFace(nn.Module):
    """ArcFace (Additive Angular Margin) layer for metric learning."""

    def __init__(self, in_features: int, out_features: int, s: float = 30.0, m: float = 0.50):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.s = s
        self.m = m
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, input: torch.Tensor, label: torch.Tensor) -> torch.Tensor:
        cosine = F.linear(F.normalize(input), F.normalize(self.weight))
        sine = torch.sqrt(1.0 - torch.pow(cosine, 2))
        phi = cosine * self.cos_m - sine * self.sin_m
        phi = torch.where(cosine > self.th, phi, cosine - self.mm)

        one_hot = torch.zeros(cosine.size(), device=input.device)
        one_hot.scatter_(1, label.view(-1, 1).long(), 1)

        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.s

        return output


class DolphinReIDModel(nn.Module):
    """
    EfficientNet-B0 backbone with embedding projection head.

    Architecture: EfficientNet features → GAP → BN → Dropout → FC → BN → 512-dim embedding
    """

    def __init__(self, num_classes: int, embedding_size: int = 512):
        super().__init__()
        efficientnet = models.efficientnet_b0(weights="IMAGENET1K_V1")
        self.backbone = efficientnet.features

        self.bn1 = nn.BatchNorm1d(1280)
        self.dropout = nn.Dropout(0.4)
        self.fc = nn.Linear(1280, embedding_size)
        self.bn2 = nn.BatchNorm1d(embedding_size)

        self.arcface = ArcFace(embedding_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Extract normalized embedding vector."""
        features = self.backbone(x)
        features = F.adaptive_avg_pool2d(features, (1, 1))
        features = features.view(features.size(0), -1)

        features = self.bn1(features)
        features = self.dropout(features)
        embeddings = self.fc(features)
        embeddings = self.bn2(embeddings)

        return embeddings
