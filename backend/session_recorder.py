"""
Grabación de sesiones remotas Centinela.
Captura frames JPEG/WebP del pipeline estándar y, al finalizar, arma un MP4 con ffmpeg
(si está disponible) o deja un índice + último frame usable.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("apollosupport.recorder")

RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", os.path.join(os.path.dirname(__file__), "recordings")))
RETENTION_DAYS = int(os.getenv("RECORDINGS_RETENTION_DAYS", "30"))
TARGET_FPS = float(os.getenv("RECORDINGS_FPS", "3"))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def recording_output_path(recording_id: int, when: Optional[datetime] = None) -> Path:
    when = when or datetime.utcnow()
    folder = RECORDINGS_DIR / f"{when.year:04d}" / f"{when.month:02d}"
    _ensure_dir(folder)
    return folder / f"rec_{recording_id}.mp4"


@dataclass
class ActiveRecording:
    recording_id: int
    device_id: int
    frames_dir: Path
    started_at: float = field(default_factory=time.time)
    duration_sec: float = 1800.0
    frame_count: int = 0
    last_frame_at: float = 0.0
    min_interval: float = 1.0 / TARGET_FPS


class SessionRecorderManager:
    """Registra grabaciones activas y recibe frames del ConnectionManager."""

    def __init__(self) -> None:
        self._active: Dict[int, ActiveRecording] = {}  # device_id -> ActiveRecording
        self._by_id: Dict[int, ActiveRecording] = {}
        self._lock = asyncio.Lock()

    def is_recording_device(self, device_id: int) -> bool:
        return device_id in self._active

    def active_device_ids(self) -> set:
        return set(self._active.keys())

    async def start(self, recording_id: int, device_id: int, duration_minutes: int) -> Path:
        async with self._lock:
            if device_id in self._active:
                raise RuntimeError(f"Ya hay grabación activa en device {device_id}")
            frames_dir = RECORDINGS_DIR / "_tmp" / f"rec_{recording_id}"
            if frames_dir.exists():
                shutil.rmtree(frames_dir, ignore_errors=True)
            _ensure_dir(frames_dir)
            rec = ActiveRecording(
                recording_id=recording_id,
                device_id=device_id,
                frames_dir=frames_dir,
                duration_sec=max(60, duration_minutes * 60),
                min_interval=1.0 / max(0.5, TARGET_FPS),
            )
            self._active[device_id] = rec
            self._by_id[recording_id] = rec
            logger.info("[REC] Start recording_id=%s device=%s dir=%s", recording_id, device_id, frames_dir)
            return frames_dir

    async def ingest_frame(self, device_id: int, frame_data: str, delta: dict = None) -> None:
        """Guarda frame completo (ignora dirty-rect parciales)."""
        rec = self._active.get(device_id)
        if not rec:
            return
        if delta:
            return  # solo frames completos
        now = time.time()
        if now - rec.last_frame_at < rec.min_interval:
            return
        raw = frame_data
        if "," in raw and raw.strip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            blob = base64.b64decode(raw)
        except Exception:
            return
        ext = "jpg"
        if blob[:4] == b"RIFF" or blob[:4] == b"WEBP":
            ext = "webp"
        elif blob[:3] == b"\xff\xd8\xff":
            ext = "jpg"
        elif blob[:8] == b"\x89PNG\r\n\x1a\n":
            ext = "png"
        rec.frame_count += 1
        rec.last_frame_at = now
        path = rec.frames_dir / f"frame_{rec.frame_count:06d}.{ext}"
        try:
            path.write_bytes(blob)
        except Exception as e:
            logger.warning("[REC] No se pudo escribir frame: %s", e)

    def should_stop(self, device_id: int) -> bool:
        rec = self._active.get(device_id)
        if not rec:
            return False
        return (time.time() - rec.started_at) >= rec.duration_sec

    async def stop(self, recording_id: int) -> dict:
        async with self._lock:
            rec = self._by_id.pop(recording_id, None)
            if not rec:
                return {"ok": False, "error": "Grabación no activa"}
            self._active.pop(rec.device_id, None)

        out_path = recording_output_path(recording_id)
        result = await asyncio.to_thread(self._encode_mp4, rec.frames_dir, out_path, rec.frame_count)
        # limpiar temporales
        try:
            shutil.rmtree(rec.frames_dir, ignore_errors=True)
        except Exception:
            pass
        result["recording_id"] = recording_id
        result["device_id"] = rec.device_id
        result["started_at"] = datetime.utcfromtimestamp(rec.started_at)
        result["ended_at"] = datetime.utcnow()
        return result

    def _encode_mp4(self, frames_dir: Path, out_path: Path, frame_count: int) -> dict:
        _ensure_dir(out_path.parent)
        frames = sorted(frames_dir.glob("frame_*.*"))
        if not frames:
            return {"ok": False, "error": "Sin frames capturados", "file_path": None, "file_size": 0}

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            # Normalizar a jpg secuencia si hay mezcla — usar pattern del primer tipo dominante
            ext = frames[0].suffix.lstrip(".")
            # Renumerar a secuencia contigua del mismo ext
            seq_dir = frames_dir / "seq"
            seq_dir.mkdir(exist_ok=True)
            for i, f in enumerate(frames, start=1):
                dest = seq_dir / f"img_{i:06d}{f.suffix}"
                try:
                    shutil.copy2(f, dest)
                except Exception:
                    pass
            pattern = str(seq_dir / f"img_%06d.{ext}")
            cmd = [
                ffmpeg, "-y",
                "-framerate", str(TARGET_FPS),
                "-i", pattern,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(out_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=600, check=False)
                if out_path.exists() and out_path.stat().st_size > 0:
                    return {
                        "ok": True,
                        "file_path": str(out_path),
                        "file_size": out_path.stat().st_size,
                        "frames": frame_count,
                    }
            except Exception as e:
                logger.error("[REC] ffmpeg falló: %s", e)

        # Fallback: guardar primer/último frame como evidencia + lista
        fallback = out_path.with_suffix(".webp" if frames[-1].suffix == ".webp" else ".jpg")
        try:
            shutil.copy2(frames[-1], fallback)
            return {
                "ok": True,
                "file_path": str(fallback),
                "file_size": fallback.stat().st_size,
                "frames": frame_count,
                "warning": "ffmpeg no disponible; se guardó frame final",
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "file_path": None, "file_size": 0}


recorder_manager = SessionRecorderManager()


def cleanup_old_recordings(retention_days: int = RETENTION_DAYS) -> int:
    if not RECORDINGS_DIR.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for root, _dirs, files in os.walk(RECORDINGS_DIR):
        if "_tmp" in root:
            continue
        for name in files:
            path = Path(root) / name
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                pass
    return removed


def sanitize_jitsi_room(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9\-]", "-", name)[:48].strip("-")
    return clean or "Sala"
