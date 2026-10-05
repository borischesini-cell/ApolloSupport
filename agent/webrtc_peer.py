"""Canal WebRTC del agente (fase 1).

P2P UDP con el navegador del técnico. Señalización por el WebSocket de Support.
Si aiortc no está instalado, el visor recibe webrtc_error y sigue con HD/WebP.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("centinela")

EmitFn = Callable[[dict], Awaitable[None]]

TARGET_FPS = 20
MAX_WIDTH = 1280

_AIORTC_ERR = ""
try:
    from aiortc import (
        RTCConfiguration,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
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


def _grab_screen():
    try:
        from dxgi_capture import grab_rgb
        img = grab_rgb(0)
        if img is not None:
            return img
    except Exception:
        pass
    try:
        from PIL import ImageGrab
        return ImageGrab.grab()
    except Exception:
        return None


class ScreenTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, fps: int = TARGET_FPS, max_width: int = MAX_WIDTH):
        super().__init__()
        self._fps = max(8, min(30, int(fps)))
        self._max_width = max_width
        self._last = None

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        img = await asyncio.get_event_loop().run_in_executor(None, _grab_screen)
        if img is None:
            img = self._last
        if img is None:
            from PIL import Image
            img = Image.new("RGB", (640, 360), (15, 23, 42))
        self._last = img
        w, h = img.size
        if self._max_width and w > self._max_width:
            nh = max(2, int(h * self._max_width / w) & ~1)
            nw = self._max_width & ~1
            img = img.resize((nw, nh))
        frame = VideoFrame.from_image(img)
        frame.pts = pts
        frame.time_base = time_base
        return frame


class WebRtcSession:
    def __init__(self, emit: EmitFn):
        self.emit = emit
        self.pc: Optional[Any] = None
        self._closed = False

    async def start_from_offer(self, sdp: str, ice_servers=None):
        if not AIORTC_OK:
            await self.emit({
                "type": "webrtc_error",
                "message": f"Agente sin WebRTC ({webrtc_unavailable_reason()})",
            })
            return
        await self.close()
        self._closed = False
        config = RTCConfiguration(iceServers=_ice_servers_from_payload(ice_servers))
        self.pc = RTCPeerConnection(configuration=config)
        self.pc.addTrack(ScreenTrack())

        @self.pc.on("connectionstatechange")
        async def _on_state():
            state = getattr(self.pc, "connectionState", "unknown") if self.pc else "closed"
            logger.info("[WEBRTC] connectionstate=%s", state)
            mapped = state
            if state == "connected":
                mapped = "open"
            elif state in ("failed", "disconnected"):
                mapped = "failed"
            try:
                await self.emit({"type": "webrtc_state", "state": mapped})
            except Exception:
                pass

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
        logger.info("[WEBRTC] answer enviado (%d chars)", len(self.pc.localDescription.sdp or ""))

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
        pc = self.pc
        self.pc = None
        if pc:
            try:
                await pc.close()
            except Exception:
                pass


_SESSION: Optional[WebRtcSession] = None


async def handle_webrtc_message(data: dict, emit: EmitFn):
    global _SESSION
    kind = data.get("type")
    if kind == "webrtc_offer":
        if not AIORTC_OK:
            await emit({
                "type": "webrtc_error",
                "message": "Este agente no tiene el módulo WebRTC. Actualizá Centinela 3.3.4+.",
            })
            return
        _SESSION = WebRtcSession(emit)
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
