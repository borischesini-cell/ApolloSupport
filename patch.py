import re

with open("agent/centinela.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Enable dirty rects
content = content.replace("USE_DIRTY_RECT     = False", "USE_DIRTY_RECT     = True")

# 2. Remove pyautogui pause
content = content.replace("pyautogui.FAILSAFE = False", "pyautogui.FAILSAFE = False\n                pyautogui.PAUSE = 0")

# 3. Add keepalive to video loop
content = content.replace("if current_hash != last_sent_frame_hash:", "if current_hash != last_sent_frame_hash or still_frames > 60:")

# 4. Remove _fast_changed call and loop continue
target = """                    current_raw = screenshot.tobytes()
                    # Comparación RÁPIDA por muestra — evita MD5 sobre 6MB por frame
                    changed, last_pixel_hash = _fast_changed(current_raw, last_pixel_hash)

                    if not changed and not FORCE_NEXT_FRAME:
                        # Calcular sleep dinámico para mantener ~25 FPS
                        elapsed = time.perf_counter() - _t0
                        time.sleep(max(0.002, _FRAME_BUDGET - elapsed))
                        continue
                    FORCE_NEXT_FRAME = False"""

replacement = """                    diff_bbox = None
                    if prev_screenshot_dr is not None:
                        from PIL import ImageChops as _IChops
                        diff_bbox = _IChops.difference(screenshot, prev_screenshot_dr).getbbox()
                        
                        if diff_bbox is None and not FORCE_NEXT_FRAME:
                            elapsed = time.perf_counter() - _t0
                            time.sleep(max(0.002, _FRAME_BUDGET - elapsed))
                            continue
                            
                    FORCE_NEXT_FRAME = False"""

content = content.replace(target, replacement)

# 5. Fix _IChops logic below since diff_bbox is already calculated
target2 = """                    if USE_DIRTY_RECT and prev_screenshot_dr is not None:
                        from PIL import ImageChops as _IChops
                        diff_bbox = _IChops.difference(screenshot, prev_screenshot_dr).getbbox()
                        if diff_bbox:
                            x1, y1, x2, y2 = diff_bbox"""

replacement2 = """                    if USE_DIRTY_RECT and diff_bbox:
                        x1, y1, x2, y2 = diff_bbox"""

content = content.replace(target2, replacement2)

with open("agent/centinela.py", "w", encoding="utf-8") as f:
    f.write(content)
