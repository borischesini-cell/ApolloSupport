import re

with open("agent/centinela.py", "r", encoding="utf-8") as f:
    content = f.read()

# Buscamos la asignacion a current_raw = screenshot.tobytes()
idx1 = content.find("current_raw = screenshot.tobytes()")
if idx1 == -1:
    print("No encontré current_raw")
else:
    # Buscamos FORCE_NEXT_FRAME = False despues de eso
    idx2 = content.find("FORCE_NEXT_FRAME = False", idx1)
    if idx2 == -1:
        print("No encontre FORCE_NEXT_FRAME = False")
    else:
        # Extraemos todo ese bloque y lo reemplazamos
        target = content[idx1:idx2 + len("FORCE_NEXT_FRAME = False")]
        
        replacement = """diff_bbox = None
                    if prev_screenshot_dr is not None:
                        from PIL import ImageChops as _IChops
                        diff_bbox = _IChops.difference(screenshot, prev_screenshot_dr).getbbox()
                        
                        if diff_bbox is None and not FORCE_NEXT_FRAME:
                            elapsed = time.perf_counter() - _t0
                            time.sleep(max(0.002, _FRAME_BUDGET - elapsed))
                            continue
                            
                    FORCE_NEXT_FRAME = False"""
                    
        content = content[:idx1] + replacement + content[idx2 + len("FORCE_NEXT_FRAME = False"):]
        
        with open("agent/centinela.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("Archivo parcheado con éxito")
