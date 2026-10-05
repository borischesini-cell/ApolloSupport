"""Desktop Duplication (DXGI) via ctypes. Sin dependencias extra.

Mas rapido que GDI/BitBlt: el GPU copia el framebuffer y el CPU solo lee
una textura staging. Si DXGI no esta disponible (Session 0, RDP viejo,
escritorio bloqueado), devolver None y que el caller use GDI.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger("centinela")

DXGI_ERROR_ACCESS_LOST = 0x887A0026
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_ERROR_ACCESS_DENIED = 0x887A002B
DXGI_ERROR_UNSUPPORTED = 0x887A0004

DXGI_FORMAT_B8G8R8A8_UNORM = 87
D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_SDK_VERSION = 7
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_READ = 0x20000
D3D11_MAP_READ = 1
COINIT_MULTITHREADED = 0x0

# ID3D11Device
_IDevice_CreateTexture2D = 5
# ID3D11DeviceContext (hereda ID3D11DeviceChild)
_ICtx_Map = 14
_ICtx_Unmap = 15
_ICtx_CopyResource = 47
# ID3D11Texture2D
_ITex_GetDesc = 10
# IDXGIObject
_IDXGI_GetParent = 6
# IDXGIAdapter
_IAdapter_EnumOutputs = 7
# IDXGIOutput1
_IOutput1_DuplicateOutput = 22
# IDXGIOutputDuplication
_IDup_GetDesc = 7
_IDup_AcquireNextFrame = 8
_IDup_ReleaseFrame = 14


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    raw = text.strip("{}")
    a, b, c, d, e = raw.split("-")
    data4 = bytes.fromhex(d + e)
    return _GUID(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*data4))


IID_IDXGIDevice = _guid("54ec77fa-1377-44e6-8c32-88fd5f44c84c")
IID_IDXGIAdapter = _guid("2411e7e1-12ac-4ccf-bd14-9798e8534dc0")
IID_IDXGIOutput1 = _guid("00cddea8-939b-4b83-a340-a685226666cc")
IID_ID3D11Texture2D = _guid("6f15aaf2-d208-4e89-9ab4-489535d34f9c")


class _DXGI_SAMPLE_DESC(ctypes.Structure):
    _fields_ = [("Count", ctypes.c_uint), ("Quality", ctypes.c_uint)]


class _D3D11_TEXTURE2D_DESC(ctypes.Structure):
    _fields_ = [
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("MipLevels", ctypes.c_uint),
        ("ArraySize", ctypes.c_uint),
        ("Format", ctypes.c_uint),
        ("SampleDesc", _DXGI_SAMPLE_DESC),
        ("Usage", ctypes.c_uint),
        ("BindFlags", ctypes.c_uint),
        ("CPUAccessFlags", ctypes.c_uint),
        ("MiscFlags", ctypes.c_uint),
    ]


class _D3D11_MAPPED(ctypes.Structure):
    _fields_ = [
        ("pData", ctypes.c_void_p),
        ("RowPitch", ctypes.c_uint),
        ("DepthPitch", ctypes.c_uint),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _DXGI_OUTDUPL_POINTER_POSITION(ctypes.Structure):
    _fields_ = [("Position", _POINT), ("Visible", ctypes.c_int)]


class _DXGI_OUTDUPL_FRAME_INFO(ctypes.Structure):
    _fields_ = [
        ("LastPresentTime", ctypes.c_int64),
        ("LastMouseUpdateTime", ctypes.c_int64),
        ("AccumulatedFrames", ctypes.c_uint),
        ("RectsCoalesced", ctypes.c_int),
        ("ProtectedContentMaskedOut", ctypes.c_int),
        ("PointerPosition", _DXGI_OUTDUPL_POINTER_POSITION),
        ("TotalMetadataBufferSize", ctypes.c_uint),
        ("PointerShapeBufferSize", ctypes.c_uint),
    ]


def _u32(hr: int) -> int:
    return hr & 0xFFFFFFFF


def _ok(hr: int) -> bool:
    return hr == 0


def _vtbl(punk: ctypes.c_void_p):
    return ctypes.cast(punk, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]


def _fn(punk, index, restype, *argtypes):
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(_vtbl(punk)[index])


def _release(punk) -> None:
    if not punk:
        return
    try:
        _fn(punk, 2, ctypes.c_ulong)(punk)
    except Exception:
        pass


def _query(punk, iid: _GUID):
    out = ctypes.c_void_p()
    hr = _fn(punk, 0, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
        punk, ctypes.byref(iid), ctypes.byref(out)
    )
    if not _ok(hr) or not out.value:
        return None
    return out


class DxgiCapturer:
    """Captura el monitor primario con Desktop Duplication."""

    def __init__(self):
        self._device = None
        self._ctx = None
        self._dup = None
        self._staging = None
        self._width = 0
        self._height = 0
        self._last_bgra = None
        self._ready = False
        self._coinit = False
        self._output_index = 0

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def size(self):
        return (self._width, self._height) if self._ready else (0, 0)

    def start(self, output_index: int = 0) -> bool:
        self.release()
        self._output_index = max(0, int(output_index))
        try:
            ctypes.windll.ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
            self._coinit = True
        except Exception:
            self._coinit = False

        d3d11 = ctypes.windll.d3d11
        d3d11.D3D11CreateDevice.restype = ctypes.c_long
        device = ctypes.c_void_p()
        ctx = ctypes.c_void_p()
        level = ctypes.c_int()
        hr = d3d11.D3D11CreateDevice(
            None,
            D3D_DRIVER_TYPE_HARDWARE,
            None,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            None,
            0,
            D3D11_SDK_VERSION,
            ctypes.byref(device),
            ctypes.byref(level),
            ctypes.byref(ctx),
        )
        if not _ok(hr) or not device.value or not ctx.value:
            logger.warning("[DXGI] D3D11CreateDevice fallo hr=0x%08X", _u32(hr))
            self.release()
            return False
        self._device = device
        self._ctx = ctx

        dxgi_dev = _query(device, IID_IDXGIDevice)
        if not dxgi_dev:
            logger.warning("[DXGI] QueryInterface IDXGIDevice fallo")
            self.release()
            return False

        adapter = ctypes.c_void_p()
        hr = _fn(dxgi_dev, _IDXGI_GetParent, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
            dxgi_dev, ctypes.byref(IID_IDXGIAdapter), ctypes.byref(adapter)
        )
        _release(dxgi_dev)
        if not _ok(hr) or not adapter.value:
            logger.warning("[DXGI] GetParent adapter fallo hr=0x%08X", _u32(hr))
            self.release()
            return False

        output = ctypes.c_void_p()
        hr = _fn(adapter, _IAdapter_EnumOutputs, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(
            adapter, self._output_index, ctypes.byref(output)
        )
        if not _ok(hr) or not output.value:
            # Monitor pedido no existe: caer al primario
            hr = _fn(adapter, _IAdapter_EnumOutputs, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(
                adapter, 0, ctypes.byref(output)
            )
        _release(adapter)
        if not _ok(hr) or not output.value:
            logger.warning("[DXGI] EnumOutputs fallo hr=0x%08X", _u32(hr))
            self.release()
            return False

        output1 = _query(output, IID_IDXGIOutput1)
        _release(output)
        if not output1:
            logger.warning("[DXGI] IDXGIOutput1 no disponible")
            self.release()
            return False

        dup = ctypes.c_void_p()
        hr = _fn(output1, _IOutput1_DuplicateOutput, ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            output1, device, ctypes.byref(dup)
        )
        _release(output1)
        if not _ok(hr) or not dup.value:
            logger.warning("[DXGI] DuplicateOutput fallo hr=0x%08X", _u32(hr))
            self.release()
            return False
        self._dup = dup

        # Primer frame para saber el tamanho y crear staging
        if self._acquire_into_staging(timeout_ms=200) is None and self._staging is None:
            logger.warning("[DXGI] No se pudo obtener el primer frame")
            self.release()
            return False

        self._ready = True
        logger.info("[DXGI] Desktop Duplication OK %dx%d (output %d)", self._width, self._height, self._output_index)
        return True

    def _ensure_staging(self, gpu_tex) -> bool:
        desc = _D3D11_TEXTURE2D_DESC()
        _fn(gpu_tex, _ITex_GetDesc, None, ctypes.POINTER(_D3D11_TEXTURE2D_DESC))(
            gpu_tex, ctypes.byref(desc)
        )
        w, h = int(desc.Width), int(desc.Height)
        if w <= 0 or h <= 0:
            return False
        if self._staging and w == self._width and h == self._height:
            return True

        if self._staging:
            _release(self._staging)
            self._staging = None

        desc.MipLevels = 1
        desc.ArraySize = 1
        desc.SampleDesc.Count = 1
        desc.SampleDesc.Quality = 0
        desc.Usage = D3D11_USAGE_STAGING
        desc.BindFlags = 0
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
        desc.MiscFlags = 0
        staging = ctypes.c_void_p()
        hr = _fn(
            self._device,
            _IDevice_CreateTexture2D,
            ctypes.c_long,
            ctypes.POINTER(_D3D11_TEXTURE2D_DESC),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )(self._device, ctypes.byref(desc), None, ctypes.byref(staging))
        if not _ok(hr) or not staging.value:
            logger.warning("[DXGI] CreateTexture2D staging fallo hr=0x%08X", _u32(hr))
            return False
        self._staging = staging
        self._width = w
        self._height = h
        return True

    def _acquire_into_staging(self, timeout_ms: int = 16):
        if not self._dup:
            return None
        info = _DXGI_OUTDUPL_FRAME_INFO()
        resource = ctypes.c_void_p()
        hr = _fn(
            self._dup,
            _IDup_AcquireNextFrame,
            ctypes.c_long,
            ctypes.c_uint,
            ctypes.POINTER(_DXGI_OUTDUPL_FRAME_INFO),
            ctypes.POINTER(ctypes.c_void_p),
        )(self._dup, timeout_ms, ctypes.byref(info), ctypes.byref(resource))
        code = _u32(hr)
        if code == DXGI_ERROR_WAIT_TIMEOUT:
            return "timeout"
        if code in (DXGI_ERROR_ACCESS_LOST, DXGI_ERROR_ACCESS_DENIED, DXGI_ERROR_UNSUPPORTED):
            return "lost"
        if not _ok(hr) or not resource.value:
            return None

        gpu_tex = _query(resource, IID_ID3D11Texture2D)
        _release(resource)
        if not gpu_tex:
            self._release_frame()
            return None
        try:
            if not self._ensure_staging(gpu_tex):
                return None
            _fn(self._ctx, _ICtx_CopyResource, None, ctypes.c_void_p, ctypes.c_void_p)(
                self._ctx, self._staging, gpu_tex
            )
            mapped = _D3D11_MAPPED()
            hr = _fn(
                self._ctx,
                _ICtx_Map,
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.POINTER(_D3D11_MAPPED),
            )(self._ctx, self._staging, 0, D3D11_MAP_READ, 0, ctypes.byref(mapped))
            if not _ok(hr) or not mapped.pData:
                return None
            try:
                pitch = int(mapped.RowPitch)
                row_bytes = self._width * 4
                src = ctypes.string_at(mapped.pData, pitch * self._height)
                if pitch == row_bytes:
                    self._last_bgra = src
                else:
                    packed = bytearray(row_bytes * self._height)
                    for y in range(self._height):
                        s = y * pitch
                        d = y * row_bytes
                        packed[d : d + row_bytes] = src[s : s + row_bytes]
                    self._last_bgra = bytes(packed)
            finally:
                _fn(self._ctx, _ICtx_Unmap, None, ctypes.c_void_p, ctypes.c_uint)(
                    self._ctx, self._staging, 0
                )
            return "ok"
        finally:
            _release(gpu_tex)
            self._release_frame()

    def _release_frame(self) -> None:
        if not self._dup:
            return
        try:
            _fn(self._dup, _IDup_ReleaseFrame, ctypes.c_long)(self._dup)
        except Exception:
            pass

    def grab_bgra(self, timeout_ms: int = 16):
        """Devuelve (w, h, bgra_bytes) o None. Reusa el ultimo frame si no hay uno nuevo."""
        if not self._ready and not self.start(self._output_index):
            return None
        status = self._acquire_into_staging(timeout_ms=timeout_ms)
        if status == "lost":
            logger.info("[DXGI] Access lost — reiniciando duplicacion")
            if not self.start(self._output_index):
                return None
            status = self._acquire_into_staging(timeout_ms=80)
        if self._last_bgra is None:
            return None
        return self._width, self._height, self._last_bgra

    def grab_rgb(self):
        """PIL Image RGB o None."""
        frame = self.grab_bgra()
        if frame is None:
            return None
        w, h, bgra = frame
        try:
            from PIL import Image
            return Image.frombuffer("RGBX", (w, h), bgra, "raw", "BGRX", 0, 1).convert("RGB")
        except Exception as exc:
            logger.debug("[DXGI] PIL convert: %s", exc)
            return None

    def grab_bgr24(self, target_w: int, target_h: int):
        """Bytes BGR empaquetados al tamanho pedido, o None."""
        img = self.grab_rgb()
        if img is None:
            return None
        if img.size != (target_w, target_h):
            from PIL import Image
            img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
        return img.tobytes("raw", "BGR")

    def release(self) -> None:
        self._ready = False
        for attr in ("_dup", "_staging", "_ctx", "_device"):
            punk = getattr(self, attr, None)
            if punk:
                _release(punk)
                setattr(self, attr, None)
        self._width = 0
        self._height = 0
        if self._coinit:
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass
            self._coinit = False


_GLOBAL = None


def get_capturer(output_index: int = 0) -> DxgiCapturer | None:
    global _GLOBAL
    if _GLOBAL is None:
        cap = DxgiCapturer()
        if not cap.start(output_index):
            return None
        _GLOBAL = cap
    return _GLOBAL


def reset_capturer() -> None:
    global _GLOBAL
    if _GLOBAL is not None:
        try:
            _GLOBAL.release()
        except Exception:
            pass
        _GLOBAL = None


def grab_rgb(output_index: int = 0):
    cap = get_capturer(output_index)
    if cap is None:
        return None
    return cap.grab_rgb()
