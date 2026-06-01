import re

with open('p:/ApolloSupport/agent/centinela.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Change ffmpeg pix_fmt
code = code.replace("'-pix_fmt', 'bgr24',", "'-pix_fmt', 'bgra',")

# 2. Change GetDIBits logic to use 32-bit (bgra) which completely avoids stride alignment issues
old_gdi = """            row_pitch = (target_w * 3 + 3) & ~3
            actual_frame_size = row_pitch * target_h
            bmi = struct.pack('<IiiHHIIiiII', 40, target_w, -target_h, 1, 24, 0, actual_frame_size, 0, 0, 0, 0)

            last_frame_hash_quick = 0
            buf = (ctypes.c_char * actual_frame_size)()
            
            try:
                loop = asyncio.get_event_loop()
                while HQ_MODE_ACTIVE and proc.poll() is None:
                    t0 = time.perf_counter()
                    
                    def _capture_and_write():
                        gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, 0x00CC0020)
                        gdi32.GetDIBits(hdc_mem, hbm, 0, target_h, buf, bmi, 0)
                        
                        if row_pitch == target_w * 3:
                            proc.stdin.write(buf.raw)
                        else:
                            raw = buf.raw
                            bgr = b"".join(raw[i*row_pitch : i*row_pitch + target_w*3] for i in range(target_h))
                            proc.stdin.write(bgr)
                        proc.stdin.flush()"""

new_gdi = """            # Se usa 32-bit (BGRA) para evitar los problemas de "padding" / "stride" de GDI
            # ya que cualquier width * 4 siempre es multiplo de 4 (alineacion de DWORD natural).
            actual_frame_size = target_w * target_h * 4
            bmi = struct.pack('<IiiHHIIiiII', 40, target_w, -target_h, 1, 32, 0, actual_frame_size, 0, 0, 0, 0)

            last_frame_hash_quick = 0
            buf = (ctypes.c_char * actual_frame_size)()
            
            try:
                loop = asyncio.get_event_loop()
                while HQ_MODE_ACTIVE and proc.poll() is None:
                    t0 = time.perf_counter()
                    
                    def _capture_and_write():
                        gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, 0x00CC0020)
                        gdi32.GetDIBits(hdc_mem, hbm, 0, target_h, buf, bmi, 0)
                        proc.stdin.write(buf.raw)
                        proc.stdin.flush()"""

if old_gdi in code:
    code = code.replace(old_gdi, new_gdi)
    print("Replaced successfully")
else:
    print("Could not find old GDI block!")

with open('p:/ApolloSupport/agent/centinela.py', 'w', encoding='utf-8') as f:
    f.write(code)
