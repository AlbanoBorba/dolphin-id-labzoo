"""
DolphinID — Export router.

Handles CSV and HTML report exports for processing sessions.
"""
import csv
import io
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.session import ProcessingSession
from app.models.result import ProcessingResult

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/{session_id}/csv")
def export_csv(session_id: int, db: Session = Depends(get_session)):
    """Export session results as a CSV file."""
    session = db.get(ProcessingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    results = db.exec(
        select(ProcessingResult)
        .where(ProcessingResult.session_id == session_id)
        .order_by(ProcessingResult.original_filename)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "filename", "status", "predicted_id", "match_confidence",
        "confirmed_id", "yolo_confidence", "reviewer_notes",
    ])

    for r in results:
        final_id = r.confirmed_id or r.predicted_id or ""
        writer.writerow([
            r.original_filename,
            r.status,
            r.predicted_id or "",
            f"{r.match_confidence:.4f}" if r.match_confidence else "",
            r.confirmed_id or "",
            f"{r.yolo_confidence:.4f}" if r.yolo_confidence else "",
            r.reviewer_notes or "",
        ])

    output.seek(0)
    filename = f"dolphin_id_{session.name}_{session.year}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/report", response_class=HTMLResponse)
def export_report(session_id: int, db: Session = Depends(get_session)):
    """Generate an HTML report for a processing session."""
    session = db.get(ProcessingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    results = db.exec(
        select(ProcessingResult)
        .where(ProcessingResult.session_id == session_id)
        .order_by(ProcessingResult.match_confidence.desc())
    ).all()

    # Stats
    total = len(results)
    identified = sum(1 for r in results if r.status == "identified")
    confirmed = sum(1 for r in results if r.status == "confirmed")
    no_detect = sum(1 for r in results if r.status == "no_detection")
    failed = sum(1 for r in results if r.status == "failed")

    # Build HTML
    rows = ""
    for r in results:
        final_id = r.confirmed_id or r.predicted_id or "—"
        conf = f"{r.match_confidence:.1%}" if r.match_confidence else "—"
        status_color = {
            "confirmed": "#2A9D8F",
            "identified": "#E9C46A",
            "no_detection": "#6B6B6B",
            "failed": "#E76F51",
        }.get(r.status, "#333")

        top5_str = ""
        if r.top5_matches:
            matches = json.loads(r.top5_matches)
            top5_str = " | ".join(f'{m["id"]} ({m["score"]:.0%})' for m in matches)

        rows += f"""
        <tr>
            <td>{r.original_filename}</td>
            <td style="color:{status_color};font-weight:600">{r.status}</td>
            <td style="font-weight:700;font-size:1.1em">{final_id}</td>
            <td>{conf}</td>
            <td style="font-size:0.85em;color:#555">{top5_str}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>DolphinID — Relatório: {session.name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: #F4F4F2; color: #2D3142; padding: 40px; }}
        h1 {{ color: #0A3D62; margin-bottom: 8px; }}
        .meta {{ color: #6B6B6B; margin-bottom: 32px; }}
        .stats {{ display: flex; gap: 16px; margin-bottom: 32px; }}
        .stat {{ background: white; padding: 16px 24px; border-radius: 12px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; min-width: 100px; }}
        .stat .number {{ font-size: 2em; font-weight: 700; color: #0A3D62; }}
        .stat .label {{ font-size: 0.85em; color: #6B6B6B; }}
        table {{ width: 100%; border-collapse: collapse; background: white;
                 border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        th {{ background: #0A3D62; color: white; padding: 12px 16px; text-align: left; }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #E0E0E0; }}
        tr:hover {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <h1>🐬 DolphinID — Relatório de Sessão</h1>
    <p class="meta">{session.name} | Ano: {session.year} | Gerado em: {session.completed_at or session.created_at}</p>

    <div class="stats">
        <div class="stat"><div class="number">{total}</div><div class="label">Total</div></div>
        <div class="stat"><div class="number">{identified}</div><div class="label">Identificadas</div></div>
        <div class="stat"><div class="number">{confirmed}</div><div class="label">Confirmadas</div></div>
        <div class="stat"><div class="number">{no_detect}</div><div class="label">Sem Detecção</div></div>
        <div class="stat"><div class="number">{failed}</div><div class="label">Falharam</div></div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Arquivo</th>
                <th>Status</th>
                <th>ID Final</th>
                <th>Confiança</th>
                <th>Top-5 Matches</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>"""

    return HTMLResponse(content=html)
