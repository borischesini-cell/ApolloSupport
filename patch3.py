import re

with open('p:/ApolloSupport/agent/centinela.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace padding
old_gdi_lines = [
    "bmi = struct.pack('<IiiHHIIiiII', 40, target_w, -target_h, 1, 24, 0, frame_size_bgr24, 0, 0, 0, 0)",
    "last_frame_hash_quick = 0",
    "buf = (ctypes.c_char * frame_size_bgr24)()",
    "mv_buf = memoryview(buf)",
    "try:",
    "loop = asyncio.get_event_loop()",
    "while HQ_MODE_ACTIVE and proc.poll() is None:",
    "t0 = time.perf_counter()",
    "def _capture_and_write():",
    "gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, 0x00CC0020)",
    "gdi32.GetDIBits(hdc_mem, hbm, 0, target_h, buf, bmi, 0)",
    "proc.stdin.write(buf.raw)",
    "proc.stdin.flush()"
]

new_gdi = """            row_pitch = (target_w * 3 + 3) & ~3
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

# I will use regex to find the block
pattern = re.compile(r"bmi = struct\.pack\('<IiiHHIIiiII'.*?proc\.stdin\.flush\(\)", re.DOTALL)
if pattern.search(code):
    code = pattern.sub(new_gdi.strip(), code)
    with open('p:/ApolloSupport/agent/centinela.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Patched padding!")
else:
    print("Not found!")
