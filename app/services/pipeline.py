"""
DolphinID — Pipeline orchestrator.

Coordinates the full processing pipeline:
  1. Scan input folder for images
  2. Run YOLO-World detection on each image
  3. Filter crops by minimum confidence threshold
  4. Create a Crop DB entry for each valid detection
  5. Extract embeddings and match against gallery for each crop
  6. Store results in database — all crops start as 'pending' for human review
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.database import get_engine
from app.models.session import ProcessingSession
from app.models.result import ProcessingResult, Crop
from app.services import detection, identification
from app.services.gallery import gallery_service

logger = logging.getLogger(__name__)

# Track running pipelines
_running_sessions: dict[int, threading.Thread] = {}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def start_pipeline(session_id: int) -> None:
    """Start the processing pipeline in a background thread."""
    if session_id in _running_sessions and _running_sessions[session_id].is_alive():
        logger.warning(f"Pipeline already running for session {session_id}")
        return

    thread = threading.Thread(target=_run_pipeline, args=(session_id,), daemon=True)
    _running_sessions[session_id] = thread
    thread.start()


def _run_pipeline(session_id: int) -> None:
    """Execute the full pipeline for a session (runs in background thread)."""
    engine = get_engine()

    try:
        # Update session status
        with Session(engine) as db:
            session = db.get(ProcessingSession, session_id)
            if session is None:
                logger.error(f"Session {session_id} not found")
                return
            session.status = "processing"
            db.add(session)
            db.commit()
            source_dir = Path(session.source_dir)

        # Ensure gallery is loaded
        if not gallery_service.is_loaded:
            gallery_service.load()

        # Phase 1: Scan and create result entries
        image_files = [
            f for f in source_dir.rglob("*")
            if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file()
        ]

        with Session(engine) as db:
            session = db.get(ProcessingSession, session_id)
            session.total_images = len(image_files)
            db.add(session)

            for img_path in image_files:
                result = ProcessingResult(
                    session_id=session_id,
                    original_path=str(img_path),
                    original_filename=img_path.name,
                    status="pending",
                )
                db.add(result)
            db.commit()

        if not image_files:
            with Session(engine) as db:
                session = db.get(ProcessingSession, session_id)
                session.status = "completed"
                session.completed_at = datetime.utcnow()
                db.add(session)
                db.commit()
            return

        # Phase 2: Detection + Identification per image
        crops_dir = settings.crops_dir / str(session_id)
        crops_dir.mkdir(parents=True, exist_ok=True)

        processed = 0
        failed = 0

        with Session(engine) as db:
            results = db.query(ProcessingResult).filter(
                ProcessingResult.session_id == session_id
            ).all()

            for result in results:
                try:
                    _process_single_image(result, crops_dir, db)
                    processed += 1
                except Exception as e:
                    logger.error(f"Error processing {result.original_filename}: {e}")
                    result.status = "failed"
                    result.error_message = str(e)
                    failed += 1
                    db.add(result)

                # Update session progress
                session = db.get(ProcessingSession, session_id)
                session.processed_images = processed + failed
                session.failed_images = failed
                db.add(session)
                db.commit()

        # Finalize session
        with Session(engine) as db:
            session = db.get(ProcessingSession, session_id)
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            db.add(session)
            db.commit()

        logger.info(f"Session {session_id} completed: {processed} processed, {failed} failed")

    except Exception as e:
        logger.error(f"Pipeline failed for session {session_id}: {e}", exc_info=True)
        with Session(engine) as db:
            session = db.get(ProcessingSession, session_id)
            if session:
                session.status = "failed"
                db.add(session)
                db.commit()
    finally:
        # Clean up VRAM after pipeline completes
        detection.unload_yolo()
        identification.unload_model()


def _process_single_image(result: ProcessingResult, crops_dir: Path, db: Session) -> None:
    """
    Process a single image through detection and identification.

    For each valid YOLO detection (above yolo_crop_min_confidence):
      - Creates a Crop DB entry
      - Extracts embedding and runs gallery matching
      - Populates predicted_id, match_confidence, top5_matches

    All crops start as status='pending' — no auto-confirm.
    """
    image_path = Path(result.original_path)

    # Step 1: YOLO Detection (returns all detections sorted by confidence)
    detections = detection.detect_and_crop(image_path, crops_dir)

    # Step 2: Filter by minimum confidence threshold
    valid_detections = [
        d for d in detections
        if d["confidence"] >= settings.yolo_crop_min_confidence
    ]

    if not valid_detections:
        result.status = "no_detection"
        result.crop_count = 0
        db.add(result)
        return

    # Step 3: Create a Crop entry for each valid detection
    for det in valid_detections:
        bbox = det["bbox"]

        crop = Crop(
            result_id=result.id,
            crop_index=det["crop_index"],
            crop_path=det["crop_path"],
            yolo_confidence=det["confidence"],
            yolo_class=det.get("class_name"),
            bbox_x=bbox[0],
            bbox_y=bbox[1],
            bbox_w=bbox[2],
            bbox_h=bbox[3],
            status="pending",
        )

        # Step 4: Extract embedding and match against gallery
        try:
            embedding = identification.extract_embedding(crop.crop_path)
            matches = gallery_service.find_matches(embedding, top_k=settings.top_k_matches)

            if matches:
                crop.predicted_id = matches[0]["id"]
                crop.match_confidence = matches[0]["score"]
                crop.top5_matches = json.dumps(matches)
        except Exception as e:
            logger.warning(
                f"Embedding/matching failed for crop {crop.crop_index} "
                f"of {result.original_filename}: {e}",
                exc_info=True
            )
            # Crop is still saved — just without identification predictions

        db.add(crop)

    # Step 5: Update ProcessingResult summary
    result.crop_count = len(valid_detections)
    result.status = "needs_review"
    db.add(result)
