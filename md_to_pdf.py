from fpdf import FPDF
import os

def convert_md_to_pdf(md_path, pdf_path):
    if not os.path.exists(md_path):
        print(f"Error: {md_path} no existe.")
        return

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Usar fuente estándar
    pdf.set_font("helvetica", size=11)
    
    # Reemplazar caracteres no-latin1 para evitar errores en helvetica estándar
    content = content.replace("©", "(c)").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    
    # Renderizar línea por línea con margen fijo
    for line in content.split('\n'):
        # Detectar headers para cambiar fuente
        if line.startswith('# '):
            pdf.set_font("helvetica", "B", 16)
            pdf.multi_cell(0, 10, line[2:], border=0, align='L', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif line.startswith('## '):
            pdf.set_font("helvetica", "B", 14)
            pdf.multi_cell(0, 10, line[3:], border=0, align='L', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        else:
            pdf.set_font("helvetica", size=11)
            pdf.multi_cell(0, 6, line, border=0, align='L', new_x="LMARGIN", new_y="NEXT")

    pdf.output(pdf_path)
    print(f"[+] PDF generado: {pdf_path}")

if __name__ == "__main__":
    md_file = r"C:\Users\Boris-2010\.gemini\antigravity\brain\48e2cfef-76ca-4578-b1a1-5c385ae94661\manual_usuario.md"
    pdf_file = r"C:\Users\Boris-2010\.gemini\antigravity\brain\48e2cfef-76ca-4578-b1a1-5c385ae94661\manual_usuario.pdf"
    convert_md_to_pdf(md_file, pdf_file)
