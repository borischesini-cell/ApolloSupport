import re
import codecs

with codecs.open('p:/ApolloSupport/agent/centinela.py', 'r', 'utf-8') as f:
    code = f.read()

# 1. Fix GDI padding
padding_fix = """            row_pitch = (target_w * 3 + 3) & ~3
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

old_gdi = """            bmi = struct.pack('<IiiHHIIiiII', 40, target_w, -target_h, 1, 24, 0, frame_size_bgr24, 0, 0, 0, 0)

            last_frame_hash_quick = 0
            buf = (ctypes.c_char * frame_size_bgr24)()
            mv_buf = memoryview(buf)
            
            try:
                loop = asyncio.get_event_loop()
                while HQ_MODE_ACTIVE and proc.poll() is None:
                    t0 = time.perf_counter()
                    
                    def _capture_and_write():
                        gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, 0x00CC0020)
                        gdi32.GetDIBits(hdc_mem, hbm, 0, target_h, buf, bmi, 0)
                        proc.stdin.write(buf.raw)
                        proc.stdin.flush()"""

code = code.replace(old_gdi, padding_fix)

# 2. Modernize UI
ui_modern = """    root.title("ApolloSoporte")
    root.geometry("360x420")
    root.resizable(False, False)
    root.configure(bg="#0f172a")

    # Guardar referencia global del ROOT y Callback de la notificacion
    global ROOT_WINDOW, SHOW_FLOATING_PANEL_CALLBACK
    ROOT_WINDOW = root

    # Cargar icono de la ventana de forma segura
    try:
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'apollo_logo.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'apollo_logo.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error cargando icono: {e}")

    # Header frame
    header_frame = tk.Frame(root, bg="#1e293b", pady=15)
    header_frame.pack(fill=tk.X)

    lbl_title = tk.Label(header_frame, text="ApolloGesCom", font=("Segoe UI", 18, "bold"), bg="#1e293b", fg="#f59e0b")
    lbl_title.pack()

    lbl_subtitle = tk.Label(header_frame, text="Módulo de Asistencia Activa", font=("Segoe UI", 10), bg="#1e293b", fg="#94a3b8")
    lbl_subtitle.pack()

    # Body frame
    body_frame = tk.Frame(root, bg="#0f172a", pady=20)
    body_frame.pack(fill=tk.BOTH, expand=True)

    lbl_info = tk.Label(body_frame, text="Dicte este ID al técnico:", font=("Segoe UI", 11), bg="#0f172a", fg="#cbd5e1")
    lbl_info.pack(pady=(10, 5))

    # ID Formateado XXL
    id_card = tk.Frame(body_frame, bg="#1e293b", padx=20, pady=15, relief="flat", bd=0)
    id_card.pack(pady=10)
    
    lbl_id = tk.Label(id_card, text=f"{str(CLIENT_ID)[:3]} {str(CLIENT_ID)[3:]}", font=("Consolas", 32, "bold"), bg="#1e293b", fg="#38bdf8")
    lbl_id.pack()

    # PIN de Soporte
    lbl_pin_info = tk.Label(body_frame, text=f"PIN: {REMOTE_PASSWORD}", font=("Segoe UI", 14, "bold"), bg="#0f172a", fg="#10b981")
    lbl_pin_info.pack(pady=15)

    # Footer
    footer_frame = tk.Frame(root, bg="#0f172a")
    footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15)

    lbl_status = tk.Label(footer_frame, text="Estado: Iniciando motor...", font=("Segoe UI", 9, "bold"), bg="#0f172a", fg="#fbbf24")
    lbl_status.pack()

    lbl_build = tk.Label(footer_frame, text=f"v{CLIENT_VERSION} | build {BUILD_DATE}", font=("Segoe UI", 8), bg="#0f172a", fg="#475569")
    lbl_build.pack(pady=(5, 0))

    # Arrancar el Socket sin frizar la pantallita
    t = threading.Thread(target=run_background_worker, args=(lbl_status,), daemon=True)
    t.start()"""

import sys
start_idx = code.find('root.title("ApolloSoporte")')
end_idx = code.find('t.start()', start_idx) + len('t.start()')

if start_idx != -1 and end_idx != -1:
    code = code[:start_idx] + ui_modern + code[end_idx:]
else:
    print("UI block not found!")
    sys.exit(1)

with codecs.open('p:/ApolloSupport/agent/centinela.py', 'w', 'utf-8') as f:
    f.write(code)

print("Patch applied successfully.")
