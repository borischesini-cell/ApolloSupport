"""Canal WebRTC del agente (fase 1).

P2P UDP con el navegador del técnico. Señalización por el WebSocket de Support.
Si aiortc no está instalado, el visor recibe webrtc_error y sigue con HD/WebP.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from fractions import Fraction
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("centinela")

EmitFn = Callable[[dict], Awaitable[None]]
LogFn = Callable[[str], Awaitable[None]]

TARGET_FPS = 20
MAX_WIDTH = 1280
DISCONNECT_GRACE_S = 10.0
STATS_EVERY_FRAMES = 300

_AIORTC_ERR = ""
try:
    from aiortc import (
        RTCConfiguration,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from aiortc.mediastreams import VIDEO_CLOCK_RATE, MediaStreamError
    from av.video.frame import VideoFrame
    AIORTC_OK = True
except Exception as exc:
    AIORTC_OK = False
    _AIORTC_ERR = str(exc)
    RTCPeerConnection = None  # type: ignore
    VideoStreamTrack = object  # type: ignore
    VideoFrame = None  # type: ignore


def webrtc_available() -> bool:
    return bool(AIORTC_OK)


def webrtc_unavailable_reason() -> str:
    if AIORTC_OK:
        return ""
    return _AIORTC_ERR or "aiortc no está instalado en este agente"


def _ice_servers_from_payload(raw) -> list:
    servers = []
    if not raw:
        return [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun.cloudflare.com:3478"]),
        ]
    for item in raw:
        if not isinstance(item, dict):
            continue
        urls = item.get("urls") or item.get("url")
        if not urls:
            continue
        if isinstance(urls, str):
            urls = [urls]
        kwargs = {"urls": list(urls)}
        if item.get("username"):
            kwargs["username"] = item["username"]
        if item.get("credential"):
            kwargs["credential"] = item["credential"]
        try:
            servers.append(RTCIceServer(**kwargs))
        except Exception:
            continue
    return servers or [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]


_SCALE_CACHE = {"src": None, "w": 0, "img": None}


def _grab_scaled(max_width: int):
    """Captura y escala en un paso. Devuelve PIL RGB (ancho/alto pares) o None.

    DXGI: escala directo desde el buffer BGRX (sin el .convert("RGB") a resolucion
    completa) y con BILINEAR+reducing_gap, mucho mas barato que el BICUBIC por defecto.
    """
    from PIL import Image
    img = None
    try:
        from dxgi_capture import get_capturer
        cap = get_capturer(0)
        frame = cap.grab_bgra() if cap is not None else None
        if frame is not None:
            w, h, bgra = frame
            # DXGI reusa el mismo objeto bytes si no hubo frame nuevo: no reescalar.
            if bgra is _SCALE_CACHE["src"] and max_width == _SCALE_CACHE["w"] and _SCALE_CACHE["img"] is not None:
                return _SCALE_CACHE["img"]
            img = Image.frombuffer("RGBX", (w, h), bgra, "raw", "BGRX", 0, 1)
            _SCALE_CACHE["src"] = bgra
    except Exception:
        img = None
    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
        except Exception:
            return None
    w, h = img.size
    if max_width and w > max_width:
        nw = max_width & ~1
        nh = max(2, int(h * nw / w) & ~1)
        img = img.resize((nw, nh), Image.Resampling.BILINEAR, reducing_gap=2.0)
    elif (w & 1) or (h & 1):
        img = img.crop((0, 0, w & ~1, h & ~1))
    img = img if img.mode == "RGB" else img.convert("RGB")
    _SCALE_CACHE["w"] = max_width
    _SCALE_CACHE["img"] = img
    return img


class ScreenTrack(VideoStreamTrack):
    """Track de pantalla. Un hilo productor captura a `fps`; recv() solo toma el
    ultimo frame listo, asi la captura/escalado no se serializa con el encode VP8."""
    kind = "video"

    def __init__(self, fps: int = TARGET_FPS, max_width: int = MAX_WIDTH, log_fn: Optional[LogFn] = None):
        super().__init__()
        self._fps = max(8, min(30, int(fps)))
        self._max_width = max_width
        self._last = None
        self._log_fn = log_fn
        self._frames = 0
        self._t0: Optional[float] = None
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._cap_frames = 0
        self._pace_start: Optional[float] = None
        self._pace_n = 0
        self._thread = threading.Thread(target=self._producer, name="webrtc-capture", daemon=True)
        self._thread.start()

    def _producer(self):
        period = 1.0 / self._fps
        nxt = time.monotonic()
        while not self._stop_evt.is_set():
            try:
                img = _grab_scaled(self._max_width)
            except Exception:
                img = None
            if img is not None:
                with self._lock:
                    self._last = img
                    self._cap_frames += 1
            nxt += period
            delay = nxt - time.monotonic()
            if delay > 0:
                self._stop_evt.wait(delay)
            else:
                nxt = time.monotonic()  # no acumular deuda si la captura es mas lenta

    def stop(self):
        self._stop_evt.set()
        super().stop()

    async def next_timestamp(self):
        """Pacing a self._fps (el de aiortc esta fijo en 30)."""
        if self.readyState != "live":
            raise MediaStreamError
        ptime = 1.0 / self._fps
        if self._pace_start is None:
            self._pace_start = time.time()
            self._pace_n = 0
        else:
            self._pace_n += 1
            wait = self._pace_start + self._pace_n * ptime - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
        return int(self._pace_n * ptime * VIDEO_CLOCK_RATE), Fraction(1, VIDEO_CLOCK_RATE)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        with self._lock:
            img = self._last
        if img is None:
            from PIL import Image
            img = Image.new("RGB", (640, 360), (15, 23, 42))
        frame = VideoFrame.from_image(img)
        frame.pts = pts
        frame.time_base = time_base
        self._frames += 1
        if self._frames == 1:
            self._t0 = time.monotonic()
        elif self._frames % STATS_EVERY_FRAMES == 0 and self._t0 and self._log_fn:
            dt = time.monotonic() - self._t0
            avg = (self._frames - 1) / dt if dt > 0 else 0.0
            try:
                await self._log_fn(
                    "[WEBRTC] track: %d frames en %.1fs (%.1f fps promedio, %d capturas)"
                    % (self._frames, dt, avg, self._cap_frames)
                )
            except Exception:
                pass
        return frame


class WebRtcSession:
    def __init__(self, emit: EmitFn, log_fn: Optional[LogFn] = None):
        self.emit = emit
        self.log_fn = log_fn
        self.pc: Optional[Any] = None
        self._closed = False
        self._fail_timer: Optional[asyncio.Task] = None

    async def _report(self, mapped: Optional[str], detail: str = ""):
        msg = "[WEBRTC]"
        if mapped:
            msg += " state→%s" % mapped
        if detail:
            msg += " %s" % detail
        logger.info("%s", msg)
        if self.log_fn:
            try:
                await self.log_fn(msg)
            except Exception:
                pass
        if mapped:
            try:
                await self.emit({"type": "webrtc_state", "state": mapped})
            except Exception:
                pass

    def _cancel_fail_timer(self):
        t = self._fail_timer
        self._fail_timer = None
        if t:
            try:
                t.cancel()
            except Exception:
                pass

    async def _delayed_fail(self, state_seen: str):
        try:
            await asyncio.sleep(DISCONNECT_GRACE_S)
        except asyncio.CancelledError:
            return
        if self._closed or not self.pc:
            return
        now = getattr(self.pc, "connectionState", "unknown")
        if now in ("connected", "completed"):
            return
        await self._report("failed", "connectionstate=%s hace %.0fs, ahora=%s" % (state_seen, DISCONNECT_GRACE_S, now))

    async def start_from_offer(self, sdp: str, ice_servers=None):
        if not AIORTC_OK:
            await self.emit({
                "type": "webrtc_error",
                "message": f"Agente sin WebRTC ({webrtc_unavailable_reason()})",
            })
            return
        await self.close()
        self._closed = False
        await self._report(None, "offer recibido, creando peer")
        config = RTCConfiguration(iceServers=_ice_servers_from_payload(ice_servers))
        self.pc = RTCPeerConnection(configuration=config)
        self.pc.addTrack(ScreenTrack(log_fn=self.log_fn))

        @self.pc.on("connectionstatechange")
        async def _on_state():
            state = getattr(self.pc, "connectionState", "unknown") if self.pc else "closed"
            if state in ("connected", "completed"):
                self._cancel_fail_timer()
                await self._report("open", "connectionstate=%s" % state)
            elif state == "disconnected":
                # Transitorio frecuente en P2P UDP: dar gracia antes de declarar fallo.
                self._cancel_fail_timer()
                self._fail_timer = asyncio.create_task(self._delayed_fail(state))
                await self._report(None, "connectionstate=disconnected (gracia %.0fs)" % DISCONNECT_GRACE_S)
            elif state == "failed":
                self._cancel_fail_timer()
                await self._report("failed", "connectionstate=failed")
            elif state == "closed":
                self._cancel_fail_timer()

        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        await self._wait_ice()
        if self._closed or not self.pc or not self.pc.localDescription:
            return
        await self.emit({
            "type": "webrtc_answer",
            "sdp": self.pc.localDescription.sdp,
        })
        await self._report(None, "answer enviado (%d chars)" % len(self.pc.localDescription.sdp or ""))

    async def add_ice(self, candidate: str, sdp_mid=None, sdp_mline_index=None):
        if not self.pc or not candidate:
            return
        try:
            from aiortc.sdp import candidate_from_sdp
            raw = candidate[10:] if candidate.startswith("candidate:") else candidate
            ice = candidate_from_sdp(raw)
            ice.sdpMid = sdp_mid
            ice.sdpMLineIndex = sdp_mline_index
            await self.pc.addIceCandidate(ice)
        except Exception as e:
            logger.debug("[WEBRTC] ICE remoto ignorado: %s", e)

    async def _wait_ice(self, timeout: float = 8.0):
        if not self.pc:
            return
        if self.pc.iceGatheringState == "complete":
            return
        done = asyncio.Event()

        @self.pc.on("icegatheringstatechange")
        def _on_gather():
            if self.pc and self.pc.iceGatheringState == "complete":
                done.set()

        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("[WEBRTC] ICE gathering timeout — se envía SDP parcial")

    async def close(self):
        self._closed = True
        self._cancel_fail_timer()
        pc = self.pc
        self.pc = None
        if pc:
            try:
                await pc.close()
            except Exception:
                pass


_SESSION: Optional[WebRtcSession] = None


async def handle_webrtc_message(data: dict, emit: EmitFn, log_fn: Optional[LogFn] = None):
    global _SESSION
    kind = data.get("type")
    if kind == "webrtc_offer":
        if not AIORTC_OK:
            await emit({
                "type": "webrtc_error",
                "message": "Este agente no tiene el módulo WebRTC. Actualizá Centinela 3.3.4+.",
            })
            return
        _SESSION = WebRtcSession(emit, log_fn)
        await _SESSION.start_from_offer(data.get("sdp") or "", data.get("ice_servers"))
    elif kind == "webrtc_ice":
        if _SESSION:
            await _SESSION.add_ice(
                data.get("candidate") or "",
                data.get("sdpMid"),
                data.get("sdpMLineIndex"),
            )
    elif kind == "webrtc_hangup":
        if _SESSION:
            await _SESSION.close()
            _SESSION = None
        await emit({"type": "webrtc_state", "state": "closed"})
