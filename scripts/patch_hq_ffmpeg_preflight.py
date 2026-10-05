"""Agrega pre-flight de ffmpeg + error visible en bitacora para hq_stream_loop.

Sitio A: tras el exists-check, verifica que ffmpeg pueda ejecutarse (arquitectura).
Sitio B: si _start_ffmpeg falla, loguea a bitacora remota y baja HQ_MODE_ACTIVE.
"""
import ast
import os
import shutil
import sys

p = r'C:/Desarrollo/P Python/ApolloSupport/agent/centinela.py'
bak = p + '.bak_C_ffmpegpreflight_20261005'

data = open(p, 'rb').read()
st = os.stat(p)
print('size=%d mtime=%d' % (st.st_size, int(st.st_mtime)))

ANCHOR_A = b'        return\r\n\r\n    # Habilitar timer de alta resoluci'
assert data.count(ANCHOR_A) == 1, 'anchor A count=%d' % data.count(ANCHOR_A)

OLD_B = (b'            logger.error("[HQ] No se pudo iniciar ffmpeg: %s", e)\r\n'
         b'            return\r\n')
assert data.count(OLD_B) == 1, 'old B count=%d' % data.count(OLD_B)

NEW_A = (
    b'        return\r\n'
    b'\r\n'
    b'    # Pre-flight: el ffmpeg bundleado puede ser de arquitectura incompatible (x64 en Windows 32-bit)\r\n'
    b'    try:\r\n'
    b"        _hq_ver = subprocess.run(\r\n"
    b"            [FFMPEG_PATH, '-version'],\r\n"
    b'            capture_output=True, timeout=8,\r\n'
    b"            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0\r\n"
    b'        )\r\n'
    b'        if _hq_ver.returncode != 0:\r\n'
    b"            raise RuntimeError('ffmpeg -version retorno %d' % _hq_ver.returncode)\r\n"
    b'    except Exception as _hq_e:\r\n'
    b'        logger.error("[HQ] ffmpeg no ejecutable (%s): %s", FFMPEG_PATH, _hq_e)\r\n'
    b'        try:\r\n'
    b'            await emit_bitacora_log("[HQ] ffmpeg no ejecutable en esta PC (%s): modo HQ deshabilitado" % _hq_e, "ERROR")\r\n'
    b'        except Exception:\r\n'
    b'            pass\r\n'
    b'        HQ_MODE_ACTIVE = False\r\n'
    b'        return\r\n'
    b'\r\n'
    b'    # Habilitar timer de alta resoluci'
)

NEW_B = (b'            logger.error("[HQ] No se pudo iniciar ffmpeg: %s", e)\r\n'
         b'            try:\r\n'
         b'                await emit_bitacora_log("[HQ] No se pudo iniciar ffmpeg: %s" % e, "ERROR")\r\n'
         b'            except Exception:\r\n'
         b'                pass\r\n'
         b'            HQ_MODE_ACTIVE = False\r\n'
         b'            return\r\n')

if not os.path.exists(bak):
    shutil.copy2(p, bak)
    print('backup:', bak)
else:
    print('backup ya existe:', bak)

out = data.replace(ANCHOR_A, NEW_A).replace(OLD_B, NEW_B)
assert out != data
assert out.count(b'_hq_ver') == 3, out.count(b'_hq_ver')
assert out.count(b'ffmpeg no ejecutable en esta PC') == 1
assert out.count(OLD_B) == 0

# AST verify (parse tolera el mojibake porque es UTF-8 valido)
ast.parse(out.decode('utf-8'))
print('AST OK')

open(p, 'wb').write(out)
print('patch OK, nuevo size=%d' % len(out))
