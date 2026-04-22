import os
from app.config import Settings

def test_settings_load_defaults():
    # Testa se as configurações default carregam corretamente e validam tipos
    settings = Settings()
    
    assert settings.top_k_matches == 5
    assert settings.yolo_confidence == 0.15
    assert isinstance(settings.yolo_classes, list)
    assert "dolphin" in settings.yolo_classes
