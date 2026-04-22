#!/usr/bin/env python
"""
DolphinID -- Simple launcher script.

Usage:
    python run.py
"""
import sys
import io
import uvicorn
from app.config import settings

# Fix Windows console encoding for emoji/unicode
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main():
    print("DolphinID - Ferramenta de identificacao de botos")
    print(f"  Abrindo em: http://{settings.host}:{settings.port}")
    print(f"  Documentacao API: http://{settings.host}:{settings.port}/docs")
    print()

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
