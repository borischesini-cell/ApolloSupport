import re
import os
import sys

with open('p:/ApolloSupport/agent/centinela.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Replace stderr=subprocess.DEVNULL with log file
log_file_patch = '''    log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'ffmpeg_hq.log')
    try:
        hq_log_file = open(log_path, 'w', encoding='utf-8')
    except:
        hq_log_file = subprocess.DEVNULL

    try:
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=hq_log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        HQ_FFMPEG_PROC = proc
    except Exception as e:
        logger.error(f"[HQ] No se pudo iniciar ffmpeg: {e}")
        return'''

code = re.sub(
    r'    try:\s*proc = subprocess\.Popen\([\s\S]*?HQ_FFMPEG_PROC = proc\s*except Exception as e:\s*logger\.error\("[^"]+", e\)\s*return',
    log_file_patch,
    code
)

# 2. Replace capture_and_feed
dxgi_patch = '''    async def capture_and_feed():
        """Captura pantalla via DXGI Desktop Duplication (GPU) con fallback a GDI."""
        import ctypes
        import struct
        import ctypes.wintypes as wt

        async def check_ffmpeg():
            while HQ_MODE_ACTIVE:
                if proc.poll() is not None:
                    logger.error(f"[HQ] FFMPEG se cerró inesperadamente con código: {proc.returncode}")
                    break
                await asyncio.sleep(1)
        asyncio.create_task(check_ffmpeg())

        dxgi_ok = False
        try:
            d3d11_dll = ctypes.windll.LoadLibrary("d3d11")
            D3D_DRIVER_TYPE_HARDWARE = 1
            D3D11_SDK_VERSION = 7
            DXGI_FORMAT_B8G8R8A8_UNORM = 87
            D3D11_USAGE_STAGING = 3
            D3D11_CPU_ACCESS_READ = 0x20000
            D3D11_BIND_NONE = 0

            device_ptr   = ctypes.c_void_p()
            context_ptr  = ctypes.c_void_p()
            fl_out       = ctypes.c_uint()
            hr = d3d11_dll.D3D11CreateDevice(
                None, D3D_DRIVER_TYPE_HARDWARE, None, 0,
                None, 0, D3D11_SDK_VERSION,
                ctypes.byref(device_ptr), ctypes.byref(fl_out), ctypes.byref(context_ptr)
            )
            if hr < 0: raise OSError(f"D3D11CreateDevice hr={hr:#010x}")

            IUnknown_QI = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_byte * 16), ctypes.POINTER(ctypes.c_void_p))
            def qi(obj, iid_str):
                iid_bytes = int(iid_str.replace('-','').replace('{','').replace('}',''), 16).to_bytes(16, 'big')
                b = iid_bytes
                guid = (ctypes.c_byte * 16)(b[3],b[2],b[1],b[0], b[5],b[4], b[7],b[6], b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15])
                out = ctypes.c_void_p()
                vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))
                fn = IUnknown_QI(vtable[0])
                hr = fn(obj, ctypes.byref(guid), ctypes.byref(out))
                if hr < 0: raise OSError(f"QueryInterface {iid_str} hr={hr:#010x}")
                return out

            IID_IDXGIDevice  = "{54ec77fa-1377-44e6-8c32-88fd5f44c84c}"
            IID_IDXGIAdapter = "{2411e7e1-12ac-4ccf-bd14-9798e8534dc0}"
            IID_IDXGIOutput1 = "{00cddea8-939b-4b83-a340-a685226666cc}"

            dxgi_device  = qi(device_ptr, IID_IDXGIDevice)
            GetAdapter_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            vtable = ctypes.cast(dxgi_device, ctypes.POINTER(ctypes.c_void_p))
            adapter_ptr = ctypes.c_void_p()
            hr = GetAdapter_t(vtable[4])(dxgi_device, ctypes.byref(adapter_ptr))
            if hr < 0: raise OSError(f"GetAdapter hr={hr:#010x}")

            EnumOutputs_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))
            vtable = ctypes.cast(adapter_ptr, ctypes.POINTER(ctypes.c_void_p))
            output_ptr = ctypes.c_void_p()
            hr = EnumOutputs_t(vtable[7])(adapter_ptr, 0, ctypes.byref(output_ptr))
            if hr < 0: raise OSError(f"EnumOutputs hr={hr:#010x}")

            output1_ptr = qi(output_ptr, IID_IDXGIOutput1)
            DupOutput_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            vtable = ctypes.cast(output1_ptr, ctypes.POINTER(ctypes.c_void_p))
            dupl_ptr = ctypes.c_void_p()
            hr = DupOutput_t(vtable[22])(output1_ptr, device_ptr, ctypes.byref(dupl_ptr))
            if hr < 0: raise OSError(f"DuplicateOutput hr={hr:#010x}")

            logger.info(f"[HQ] DXGI iniciado OK ({sw}x{sh})")
            dxgi_ok = True

            class DXGI_OUTDUPL_FRAME_INFO(ctypes.Structure):
                _fields_ = [('LastPresentTime', ctypes.c_int64), ('LastMouseUpdateTime', ctypes.c_int64), ('AccumulatedFrames', ctypes.c_uint), ('RectsCoalesced', ctypes.c_bool), ('ProtectedContentMaskedOut', ctypes.c_bool), ('PointerPosition', ctypes.c_byte * 24), ('TotalMetadataBufferSize', ctypes.c_uint), ('PointerShapeBufferSize', ctypes.c_uint)]
            AcquireNextFrame_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(DXGI_OUTDUPL_FRAME_INFO), ctypes.POINTER(ctypes.c_void_p))
            ReleaseFrame_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)

            vtable_dupl = ctypes.cast(dupl_ptr, ctypes.POINTER(ctypes.c_void_p))
            fn_acquire = AcquireNextFrame_t(vtable_dupl[8])
            fn_release = ReleaseFrame_t(vtable_dupl[10])

            class D3D11_TEXTURE2D_DESC(ctypes.Structure):
                _fields_ = [('Width', ctypes.c_uint), ('Height', ctypes.c_uint), ('MipLevels', ctypes.c_uint), ('ArraySize', ctypes.c_uint), ('Format', ctypes.c_uint), ('SampleCount', ctypes.c_uint), ('SampleQuality', ctypes.c_uint), ('Usage', ctypes.c_uint), ('BindFlags', ctypes.c_uint), ('CPUAccessFlags', ctypes.c_uint), ('MiscFlags', ctypes.c_uint)]
            staging_desc = D3D11_TEXTURE2D_DESC(sw, sh, 1, 1, DXGI_FORMAT_B8G8R8A8_UNORM, 1, 0, D3D11_USAGE_STAGING, D3D11_BIND_NONE, D3D11_CPU_ACCESS_READ, 0)
            CreateTexture2D_t = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(D3D11_TEXTURE2D_DESC), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            vtable_dev = ctypes.cast(device_ptr, ctypes.POINTER(ctypes.c_void_p))
            staging_tex = ctypes.c_void_p()
            hr = CreateTexture2D_t(vtable_dev[5])(device_ptr, ctypes.byref(staging_desc), None, ctypes.byref(staging_tex))
            if hr < 0: raise OSError(f"CreateTexture2D staging hr={hr:#010x}")

            IID_ID3D11Texture2D = "{6f15aaf2-d208-4e89-9ab4-489535d34f9c}"
            CopyResource_t = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
            class D3D11_MAPPED_SUBRESOURCE(ctypes.Structure):
                _fields_ = [('pData', ctypes.c_void_p), ('RowPitch', ctypes.c_uint), ('DepthPitch', ctypes.c_uint)]
            Map_t   = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(D3D11_MAPPED_SUBRESOURCE))
            Unmap_t = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint)
            vtable_ctx = ctypes.cast(context_ptr, ctypes.POINTER(ctypes.c_void_p))
            fn_copy    = CopyResource_t(vtable_ctx[25])
            fn_map     = Map_t(vtable_ctx[14])
            fn_unmap   = Unmap_t(vtable_ctx[15])
            D3D11_MAP_READ = 1; D3D11_MAP_FLAG_DO_NOT_WAIT = 0x100000

            frame_info = DXGI_OUTDUPL_FRAME_INFO()
            DXGI_ERROR_WAIT_TIMEOUT = -2005270490  # 0x887A0027

            while HQ_MODE_ACTIVE and proc.poll() is None:
                desktop_res = ctypes.c_void_p()
                hr = fn_acquire(dupl_ptr, 100, ctypes.byref(frame_info), ctypes.byref(desktop_res))
                if hr == DXGI_ERROR_WAIT_TIMEOUT:
                    await asyncio.sleep(0)
                    continue
                if hr < 0:
                    await asyncio.sleep(0.01)
                    continue
                try:
                    tex2d = qi(desktop_res, IID_ID3D11Texture2D)
                    fn_copy(context_ptr, staging_tex, tex2d)
                    mapped = D3D11_MAPPED_SUBRESOURCE()
                    hr2 = fn_map(context_ptr, staging_tex, 0, D3D11_MAP_READ, 0, ctypes.byref(mapped))
                    if hr2 == 0:
                        raw_bgra = (ctypes.c_char * (mapped.RowPitch * sh)).from_address(mapped.pData)
                        rows = []
                        for row in range(sh):
                            offset = row * mapped.RowPitch
                            row_bgra = raw_bgra[offset:offset + sw*4]
                            rows.append(bytes(row_bgra[i] for i in range(len(row_bgra)) if i % 4 != 3))
                        raw_bgr = b"".join(rows)
                        fn_unmap(context_ptr, staging_tex, 0)
                        try:
                            await loop.run_in_executor(None, proc.stdin.write, raw_bgr)
                        except Exception:
                            break
                finally:
                    fn_release(dupl_ptr)
                    desktop_res = None
        except Exception as dxgi_err:
            if dxgi_ok:
                logger.error(f"[HQ] DXGI error en loop: {dxgi_err}")
            else:
                logger.warning(f"[HQ] DXGI no disponible ({dxgi_err}) — usando GDI BitBlt")
            gdi32  = ctypes.windll.gdi32
            hdc_screen = gdi32.CreateDCA(b'DISPLAY', None, None, None)
            hdc_mem    = gdi32.CreateCompatibleDC(hdc_screen)
            hbm        = gdi32.CreateCompatibleBitmap(hdc_screen, sw, sh)
            gdi32.SelectObject(hdc_mem, hbm)
            bmi = struct.pack('<IIIHHIIiiii', 40, sw, -sh, 1, 24, 0, frame_size, 0, 0, 0, 0) + b'\\x00'*4
            try:
                while HQ_MODE_ACTIVE and proc.poll() is None:
                    gdi32.BitBlt(hdc_mem, 0, 0, sw, sh, hdc_screen, 0, 0, 0x00CC0020)
                    buf = (ctypes.c_char * frame_size)()
                    gdi32.GetDIBits(hdc_mem, hbm, 0, sh, buf, bmi, 0)
                    try:
                        await loop.run_in_executor(None, proc.stdin.write, bytes(buf))
                        await loop.run_in_executor(None, proc.stdin.flush)
                    except Exception:
                        break
                    await asyncio.sleep(1/30)
            finally:
                try: proc.stdin.close()
                except: pass
                gdi32.DeleteDC(hdc_mem); gdi32.DeleteDC(hdc_screen); gdi32.DeleteObject(hbm)
            return
        try: proc.stdin.close()
        except: pass'''

code = re.sub(
    r'    async def capture_and_feed\(\):[\s\S]*?gdi32\.DeleteObject\(hbm\)',
    dxgi_patch,
    code
)

with open('p:/ApolloSupport/agent/centinela.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Patch applied successfully')
