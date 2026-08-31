"""
DolphinID — FastAPI application entry point.

Serves the API and static frontend from a single process.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import sessions, results, gallery, export, browse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dolphin-id")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("Starting DolphinID...")
    settings.ensure_directories()
    init_db()
    logger.info("Database initialized")

    # Pre-load gallery if available
    from app.services.gallery import gallery_service
    try:
        gallery_service.load()

        # Auto-import PKL into catalog DB on first run
        from app.database import get_engine
        from sqlmodel import Session, select
        from app.models.catalog import CatalogCrop
        engine = get_engine()
        with Session(engine) as db:
            existing = db.exec(select(CatalogCrop).limit(1)).first()
            if existing is None:
                logger.info("Catalog DB is empty — importing from PKL...")
                count = gallery_service.import_from_pkl(db)
                logger.info(f"Imported {count} entries from PKL into catalog DB")

        # Pre-compute UMAP 2D projection so the embedding map is ready instantly
        gallery_service.compute_2d_projection()
    except FileNotFoundError:
        logger.warning("Gallery PKL not found -- run setup_artifacts.py first")

    yield

    logger.info("Shutting down DolphinID...")


app = FastAPI(
    title="DolphinID",
    description="Ferramenta de identificação automática de botos via foto-identificação de nadadeira dorsal",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)

# API routers
app.include_router(sessions.router)
app.include_router(results.router)
app.include_router(gallery.router)
app.include_router(export.router)
app.include_router(browse.router)

# Serve static files (frontend)
static_dir = settings.project_root / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serve the main frontend page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "DolphinID API is running. Visit /docs for API documentation."}


@app.get("/health")
async def health():
    """Health check."""
    from app.services.gallery import gallery_service
    return {
        "status": "healthy",
        "gallery_loaded": gallery_service.is_loaded,
        "gallery_size": gallery_service.gallery.size if gallery_service.is_loaded else 0,
        "model_checkpoint": str(settings.model_checkpoint),
        "model_exists": settings.model_checkpoint.exists(),
        "yolo_exists": settings.yolo_weights.exists(),
    }


@app.get("/api/config")
async def get_config():
    """Return current configuration (for frontend display)."""
    from app.services.gallery import gallery_service
    return {
        "model_checkpoint": settings.model_checkpoint.name,
        "model_exists": settings.model_checkpoint.exists(),
        "gallery_file": settings.gallery_pkl.name,
        "gallery_loaded": gallery_service.is_loaded,
        "gallery_individuals": len(gallery_service.gallery.get_individual_labels()) if gallery_service.is_loaded else 0,
        "gallery_images": gallery_service.gallery.size if gallery_service.is_loaded else 0,
        "yolo_weights": settings.yolo_weights.name,
        "yolo_exists": settings.yolo_weights.exists(),
        "yolo_confidence": settings.yolo_confidence,
        "yolo_crop_min_confidence": settings.yolo_crop_min_confidence,
        "top_k_matches": settings.top_k_matches,
    }


def cli_entry():
    """Entry point for the 'dolphin-id' CLI command."""
    import uvicorn
    print("DolphinID -- Starting server...")
    print(f"   Open http://{settings.host}:{settings.port} in your browser")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
