"""
Agenda ApolloSupport: grabaciones programadas + videoconferencias Jitsi.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
import urllib.parse
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from database import SessionLocal, get_db
from session_recorder import cleanup_old_recordings, recorder_manager, sanitize_jitsi_room

logger = logging.getLogger("apollosupport.agenda")

JITSI_BASE_URL = os.getenv("JITSI_BASE_URL", "https://meet.jit.si").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@ultimate.net.ar")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") not in ("0", "false", "False")

router = APIRouter(prefix="/api/agenda", tags=["Agenda"])

_manager = None
_send_push = None


def build_meeting_message(meeting: models.ScheduledMeeting, client_name: str = "") -> str:
    when = meeting.starts_at.strftime("%d/%m/%Y %H:%M") if meeting.starts_at else ""
    who = client_name or "cliente"
    lines = [
        f"Hola, te esperamos en videoconferencia Apollo Support ({meeting.title}) el {when} (hora servidor).",
        f"Cliente: {who}",
        f"Unirse: {meeting.join_url}",
    ]
    if meeting.agenda:
        lines.append(f"Agenda: {meeting.agenda}")
    return "\n".join(lines)


def build_wa_url(phone: Optional[str], message: str) -> Optional[str]:
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return None
    if len(digits) <= 10:
        digits = "54" + digits
    return f"https://wa.me/{digits}?text={urllib.parse.quote(message)}"


def build_mailto(email: Optional[str], subject: str, body: str) -> Optional[str]:
    if not email:
        return None
    return f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"


def send_smtp_email(to_addr: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not to_addr:
        logger.warning("[AGENDA] SMTP no configurado o sin destinatario")
        return False
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls(context=ssl.create_default_context())
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        logger.error("[AGENDA] Error SMTP: %s", e)
        return False


def enqueue_outbox(
    db: Session,
    channel: str,
    body: str,
    send_at: datetime,
    target: str = None,
    subject: str = None,
    ref_type: str = None,
    ref_id: int = None,
):
    row = models.NotificationOutbox(
        channel=channel,
        target=target,
        subject=subject,
        body=body,
        send_at=send_at,
        status="pending",
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(row)
    return row


def recording_out(row: models.ScheduledRecording) -> schemas.ScheduledRecordingOut:
    client_name = row.client.razon_social if row.client else None
    device_name = row.device.device_name if row.device else None
    assist_id = row.device.assist_id if row.device else None
    tech_name = None
    if row.technician:
        tech_name = row.technician.full_name or getattr(row.technician, "nombre", None) or row.technician.email
    has_video = bool(row.file_path and Path(row.file_path).exists())
    duration_seconds = None
    if row.started_at and row.ended_at:
        duration_seconds = int((row.ended_at - row.started_at).total_seconds())
    return schemas.ScheduledRecordingOut(
        id=row.id,
        client_id=row.client_id,
        device_id=row.device_id,
        technician_id=row.technician_id,
        scheduled_at=row.scheduled_at,
        duration_minutes=row.duration_minutes or 30,
        status=row.status,
        support_session_id=row.support_session_id,
        file_path=row.file_path,
        file_size=row.file_size,
        started_at=row.started_at,
        ended_at=row.ended_at,
        error_message=row.error_message,
        notes=row.notes,
        created_at=row.created_at,
        client_name=client_name,
        device_name=device_name,
        assist_id=assist_id,
        technician_name=tech_name,
        has_video=has_video,
        duration_seconds=duration_seconds,
    )


def meeting_out(row: models.ScheduledMeeting) -> schemas.ScheduledMeetingOut:
    client_name = row.client.razon_social if row.client else None
    host_name = None
    if row.host:
        host_name = row.host.full_name or getattr(row.host, "nombre", None) or row.host.email
    return schemas.ScheduledMeetingOut(
        id=row.id,
        client_id=row.client_id,
        host_user_id=row.host_user_id,
        title=row.title,
        agenda=row.agenda,
        starts_at=row.starts_at,
        duration_minutes=row.duration_minutes or 30,
        join_url=row.join_url,
        status=row.status,
        notify_minutes_before=row.notify_minutes_before or 15,
        client_email=row.client_email,
        client_phone=row.client_phone,
        alert_sent_at=row.alert_sent_at,
        created_at=row.created_at,
        client_name=client_name,
        host_name=host_name,
    )


async def notify_client_devices(client_id: int, message: str) -> bool:
    if _manager is None:
        return False
    device_ids = list(getattr(_manager, "active_clients", {}).get(client_id, []) or [])
    if not device_ids:
        db = SessionLocal()
        try:
            device_ids = [
                d.id
                for d in db.query(models.CentinelaDevice)
                .filter(
                    models.CentinelaDevice.client_id == client_id,
                    models.CentinelaDevice.is_online == True,  # noqa: E712
                )
                .all()
            ]
        finally:
            db.close()
    sent = False
    for did in device_ids:
        ok = await _manager.send_json_safe(
            did,
            {"type": "chat_message", "message": message, "tech_name": "Agenda Apollo"},
        )
        if ok:
            sent = True
            await _manager.send_json_safe(did, {"type": "agenda_alert", "message": message})
    return sent


async def start_recording_job(row_id: int):
    db = SessionLocal()
    try:
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == row_id).first()
        if not row or row.status != "scheduled":
            return
        device_online = row.device_id in getattr(_manager, "active_connections", {})
        if not device_online:
            row.status = "failed"
            row.error_message = "Dispositivo offline a la hora programada"
            row.ended_at = datetime.utcnow()
            db.commit()
            return

        row.status = "running"
        row.started_at = datetime.utcnow()
        sess = models.SupportSession(
            device_id=row.device_id,
            technician_id=row.technician_id,
            start_time=datetime.utcnow(),
            comments=f"Grabación programada #{row.id}",
        )
        db.add(sess)
        db.flush()
        row.support_session_id = sess.id
        db.commit()

        await recorder_manager.start(row.id, row.device_id, row.duration_minutes or 30)
        await _manager.send_json_safe(row.device_id, {"type": "technician_joined", "name": "Grabador Agenda"})
        await _manager.send_json_safe(
            row.device_id, {"type": "active_technicians", "technicians": ["Grabador Agenda"]}
        )
        await _manager.send_json_safe(row.device_id, {"type": "refresh_frame"})

        tech = db.query(models.User).filter(models.User.id == row.technician_id).first()
        token = getattr(tech, "expo_push_token", None) if tech else None
        if token and _send_push:
            await _send_push(token, "Grabación iniciada", f"Device #{row.device_id} — {row.duration_minutes} min")
    except Exception as e:
        logger.exception("[AGENDA] Error iniciando grabación %s", row_id)
        try:
            row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == row_id).first()
            if row:
                row.status = "failed"
                row.error_message = str(e)
                row.ended_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def finish_recording_job(row_id: int):
    result = await recorder_manager.stop(row_id)
    db = SessionLocal()
    try:
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == row_id).first()
        if not row:
            return
        row.ended_at = result.get("ended_at") or datetime.utcnow()
        if result.get("ok"):
            row.status = "completed"
            row.file_path = result.get("file_path")
            row.file_size = result.get("file_size") or 0
            if result.get("warning"):
                row.error_message = result["warning"]
        else:
            row.status = "failed"
            row.error_message = result.get("error") or "Error al finalizar grabación"
        if row.support_session_id:
            sess = db.query(models.SupportSession).filter(models.SupportSession.id == row.support_session_id).first()
            if sess and not sess.end_time:
                sess.end_time = datetime.utcnow()
        if _manager and not _manager.has_any_viewers(row.device_id):
            await _manager.send_json_safe(row.device_id, {"type": "active_technicians", "technicians": []})
        db.commit()
    finally:
        db.close()


async def process_outbox_once():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        pending = (
            db.query(models.NotificationOutbox)
            .filter(
                models.NotificationOutbox.status == "pending",
                models.NotificationOutbox.send_at <= now,
            )
            .limit(50)
            .all()
        )
        for item in pending:
            ok = False
            err = None
            try:
                if item.channel == "email" and item.target:
                    ok = send_smtp_email(item.target, item.subject or "Apollo Support", item.body)
                elif item.channel == "push" and item.target:
                    uid = int(item.target)
                    user = db.query(models.User).filter(models.User.id == uid).first()
                    token = getattr(user, "expo_push_token", None) if user else None
                    if token and _send_push:
                        await _send_push(token, item.subject or "Apollo", item.body)
                    ok = True
                    if not token:
                        err = "sin expo_push_token"
                elif item.channel == "agent" and item.target:
                    ok = await notify_client_devices(int(item.target), item.body)
                elif item.channel == "internal":
                    ok = True
                else:
                    err = f"canal no soportado: {item.channel}"
            except Exception as e:
                err = str(e)
            item.status = "sent" if ok else "failed"
            item.sent_at = datetime.utcnow()
            item.error_message = err
            if item.ref_type == "meeting" and item.ref_id and ok:
                m = db.query(models.ScheduledMeeting).filter(models.ScheduledMeeting.id == item.ref_id).first()
                if m and not m.alert_sent_at:
                    m.alert_sent_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error("[AGENDA] outbox error: %s", e)
    finally:
        db.close()


async def periodic_agenda_worker():
    logger.info("[AGENDA] Worker iniciado")
    cleanup_counter = 0
    while True:
        try:
            await process_outbox_once()
            due_ids: List[int] = []
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                due = (
                    db.query(models.ScheduledRecording)
                    .filter(
                        models.ScheduledRecording.status == "scheduled",
                        models.ScheduledRecording.scheduled_at <= now,
                    )
                    .limit(10)
                    .all()
                )
                due_ids = [r.id for r in due]
                for m in (
                    db.query(models.ScheduledMeeting)
                    .filter(
                        models.ScheduledMeeting.status == "scheduled",
                        models.ScheduledMeeting.starts_at <= now,
                    )
                    .all()
                ):
                    end = m.starts_at + timedelta(minutes=m.duration_minutes or 30)
                    m.status = "completed" if now >= end else "live"
                for m in (
                    db.query(models.ScheduledMeeting)
                    .filter(models.ScheduledMeeting.status == "live")
                    .all()
                ):
                    end = m.starts_at + timedelta(minutes=m.duration_minutes or 30)
                    if now >= end:
                        m.status = "completed"
                db.commit()
            finally:
                db.close()

            for rid in due_ids:
                await start_recording_job(rid)

            for device_id in list(recorder_manager.active_device_ids()):
                if recorder_manager.should_stop(device_id):
                    rec = recorder_manager._active.get(device_id)
                    if rec:
                        await finish_recording_job(rec.recording_id)

            cleanup_counter += 1
            if cleanup_counter >= 120:
                cleanup_counter = 0
                removed = await asyncio.to_thread(cleanup_old_recordings)
                if removed:
                    logger.info("[AGENDA] Retención: %s archivos eliminados", removed)
        except Exception as e:
            logger.error("[AGENDA] Worker error: %s", e)
        await asyncio.sleep(30)


def setup_agenda(app: FastAPI, manager, get_current_user, send_push_notification):
    """Registra rutas y cablea dependencias (llamar desde main.py)."""
    global _manager, _send_push
    _manager = manager
    _send_push = send_push_notification

    @router.get("/recordings", response_model=List[schemas.ScheduledRecordingOut])
    def list_recordings(
        status: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        q = (
            db.query(models.ScheduledRecording)
            .options(
                joinedload(models.ScheduledRecording.client),
                joinedload(models.ScheduledRecording.device),
                joinedload(models.ScheduledRecording.technician),
            )
            .order_by(models.ScheduledRecording.scheduled_at.desc())
        )
        if status:
            q = q.filter(models.ScheduledRecording.status == status)
        return [recording_out(r) for r in q.limit(200).all()]

    @router.get("/recordings/library", response_model=List[schemas.ScheduledRecordingOut])
    def recordings_library(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        rows = (
            db.query(models.ScheduledRecording)
            .options(
                joinedload(models.ScheduledRecording.client),
                joinedload(models.ScheduledRecording.device),
                joinedload(models.ScheduledRecording.technician),
            )
            .filter(models.ScheduledRecording.status.in_(["completed", "failed", "running"]))
            .order_by(models.ScheduledRecording.scheduled_at.desc())
            .limit(200)
            .all()
        )
        return [recording_out(r) for r in rows]

    @router.post("/recordings", response_model=schemas.ScheduledRecordingOut)
    def create_recording(
        payload: schemas.ScheduledRecordingCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == payload.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
        if device.client_id != payload.client_id:
            raise HTTPException(status_code=400, detail="El dispositivo no pertenece al cliente indicado")
        tech = db.query(models.User).filter(models.User.id == payload.technician_id).first()
        if not tech:
            raise HTTPException(status_code=404, detail="Técnico no encontrado")
        row = models.ScheduledRecording(
            client_id=payload.client_id,
            device_id=payload.device_id,
            technician_id=payload.technician_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes or 30,
            notes=payload.notes,
            status="scheduled",
        )
        db.add(row)
        db.flush()
        alert_at = payload.scheduled_at - timedelta(minutes=10)
        if alert_at < datetime.utcnow():
            alert_at = datetime.utcnow()
        enqueue_outbox(
            db, "push", f"En breve inicia grabación remota del device #{payload.device_id}",
            alert_at, target=str(tech.id), subject="Grabación programada",
            ref_type="recording", ref_id=row.id,
        )
        db.commit()
        row = (
            db.query(models.ScheduledRecording)
            .options(
                joinedload(models.ScheduledRecording.client),
                joinedload(models.ScheduledRecording.device),
                joinedload(models.ScheduledRecording.technician),
            )
            .filter(models.ScheduledRecording.id == row.id)
            .first()
        )
        return recording_out(row)

    @router.patch("/recordings/{recording_id}", response_model=schemas.ScheduledRecordingOut)
    def update_recording(
        recording_id: int,
        payload: schemas.ScheduledRecordingUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == recording_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Grabación no encontrada")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        db.commit()
        row = (
            db.query(models.ScheduledRecording)
            .options(
                joinedload(models.ScheduledRecording.client),
                joinedload(models.ScheduledRecording.device),
                joinedload(models.ScheduledRecording.technician),
            )
            .filter(models.ScheduledRecording.id == recording_id)
            .first()
        )
        return recording_out(row)

    @router.post("/recordings/{recording_id}/cancel")
    def cancel_recording(
        recording_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == recording_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Grabación no encontrada")
        if row.status == "running":
            raise HTTPException(status_code=400, detail="No se puede cancelar una grabación en curso")
        row.status = "cancelled"
        db.commit()
        return {"status": "success", "message": "Grabación cancelada"}

    @router.delete("/recordings/{recording_id}")
    def delete_recording(
        recording_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == recording_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Grabación no encontrada")
        if row.file_path:
            try:
                Path(row.file_path).unlink(missing_ok=True)
            except Exception:
                pass
        db.delete(row)
        db.commit()
        return {"status": "success"}

    @router.get("/recordings/{recording_id}/download")
    def download_recording(
        recording_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledRecording).filter(models.ScheduledRecording.id == recording_id).first()
        if not row or not row.file_path:
            raise HTTPException(status_code=404, detail="Archivo no disponible")
        path = Path(row.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
        media = "video/mp4" if path.suffix.lower() == ".mp4" else "application/octet-stream"
        return FileResponse(path, media_type=media, filename=path.name)

    @router.get("/meetings", response_model=List[schemas.ScheduledMeetingOut])
    def list_meetings(
        status: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        q = (
            db.query(models.ScheduledMeeting)
            .options(joinedload(models.ScheduledMeeting.client), joinedload(models.ScheduledMeeting.host))
            .order_by(models.ScheduledMeeting.starts_at.desc())
        )
        if status:
            q = q.filter(models.ScheduledMeeting.status == status)
        return [meeting_out(m) for m in q.limit(200).all()]

    @router.post("/meetings", response_model=schemas.ScheduledMeetingOut)
    def create_meeting(
        payload: schemas.ScheduledMeetingCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        client = db.query(models.Client).filter(models.Client.id == payload.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        room = sanitize_jitsi_room(f"Apollo-{client.codigo or client.id}-{int(payload.starts_at.timestamp())}")
        join_url = f"{JITSI_BASE_URL}/{room}"
        email = payload.client_email or client.email
        phone = payload.client_phone or client.telefono
        row = models.ScheduledMeeting(
            client_id=payload.client_id,
            host_user_id=current_user.id,
            title=payload.title,
            agenda=payload.agenda,
            starts_at=payload.starts_at,
            duration_minutes=payload.duration_minutes or 30,
            join_url=join_url,
            status="scheduled",
            notify_minutes_before=payload.notify_minutes_before or 15,
            client_email=email,
            client_phone=phone,
        )
        db.add(row)
        db.flush()
        notify_at = payload.starts_at - timedelta(minutes=row.notify_minutes_before)
        msg = build_meeting_message(row, client.razon_social)
        if email:
            enqueue_outbox(
                db, "email", msg, notify_at, target=email,
                subject=f"Videoconferencia Apollo: {payload.title}",
                ref_type="meeting", ref_id=row.id,
            )
        enqueue_outbox(
            db, "push", msg, notify_at, target=str(current_user.id),
            subject="Reunión próxima", ref_type="meeting", ref_id=row.id,
        )
        enqueue_outbox(
            db, "agent", msg, notify_at, target=str(payload.client_id),
            subject="Reunión Apollo Support", ref_type="meeting", ref_id=row.id,
        )
        db.commit()
        row = (
            db.query(models.ScheduledMeeting)
            .options(joinedload(models.ScheduledMeeting.client), joinedload(models.ScheduledMeeting.host))
            .filter(models.ScheduledMeeting.id == row.id)
            .first()
        )
        return meeting_out(row)

    @router.patch("/meetings/{meeting_id}", response_model=schemas.ScheduledMeetingOut)
    def update_meeting(
        meeting_id: int,
        payload: schemas.ScheduledMeetingUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledMeeting).filter(models.ScheduledMeeting.id == meeting_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Reunión no encontrada")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        db.commit()
        row = (
            db.query(models.ScheduledMeeting)
            .options(joinedload(models.ScheduledMeeting.client), joinedload(models.ScheduledMeeting.host))
            .filter(models.ScheduledMeeting.id == meeting_id)
            .first()
        )
        return meeting_out(row)

    @router.delete("/meetings/{meeting_id}")
    def delete_meeting(
        meeting_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = db.query(models.ScheduledMeeting).filter(models.ScheduledMeeting.id == meeting_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Reunión no encontrada")
        row.status = "cancelled"
        db.commit()
        return {"status": "success", "message": "Reunión cancelada"}

    @router.get("/meetings/{meeting_id}/share", response_model=schemas.MeetingShareOut)
    def share_meeting(
        meeting_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = (
            db.query(models.ScheduledMeeting)
            .options(joinedload(models.ScheduledMeeting.client))
            .filter(models.ScheduledMeeting.id == meeting_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Reunión no encontrada")
        name = row.client.razon_social if row.client else ""
        message = build_meeting_message(row, name)
        return schemas.MeetingShareOut(
            join_url=row.join_url,
            message=message,
            mailto=build_mailto(row.client_email, f"Videoconferencia: {row.title}", message),
            wa_url=build_wa_url(row.client_phone, message),
            email=row.client_email,
            phone=row.client_phone,
        )

    @router.post("/meetings/{meeting_id}/notify")
    async def notify_meeting(
        meeting_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        row = (
            db.query(models.ScheduledMeeting)
            .options(joinedload(models.ScheduledMeeting.client))
            .filter(models.ScheduledMeeting.id == meeting_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Reunión no encontrada")
        name = row.client.razon_social if row.client else ""
        message = build_meeting_message(row, name)
        email_ok = False
        if row.client_email:
            email_ok = await asyncio.to_thread(
                send_smtp_email, row.client_email, f"Videoconferencia: {row.title}", message
            )
        agent_ok = await notify_client_devices(row.client_id, message)
        return {
            "status": "success",
            "email_sent": email_ok,
            "agent_notified": agent_ok,
            "wa_url": build_wa_url(row.client_phone, message),
            "mailto": build_mailto(row.client_email, f"Videoconferencia: {row.title}", message),
            "message": message,
            "join_url": row.join_url,
        }

    app.include_router(router)
