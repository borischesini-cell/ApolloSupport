import os

file_path = r'p:\ApolloSupport\frontend\src\App.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

funcs_code = """
  const handleBackup = async () => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${API_URL}/backup`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        const err = await response.json();
        alert(err.detail || "Error al descargar backup");
        return;
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ApolloBackup_${new Date().toISOString().slice(0, 10)}.apbk`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      alert("Error descargando backup: " + e);
    }
  };

  const handleRestore = async (e: any) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!window.confirm("ATENCIÓN: Esto sobrescribirá todos los datos actuales. ¿Estás seguro?")) return;

    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_URL}/restore`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      const data = await response.json();
      if (response.ok) {
        alert(data.message || "Restauración exitosa");
        window.location.reload();
      } else {
        alert(data.detail || "Error en la restauración");
      }
    } catch (e) {
      alert("Error subiendo backup: " + e);
    }
  };

  const generateLicense"""

ui_target = "{/* Seccin PWA e Installability */}"
if "Sección PWA e Installability" in content:
    ui_target = "{/* Sección PWA e Installability */}"

ui_code = """
                    {/* Backup Section */}
                    <div className="pt-6 border-t border-slate-200 dark:border-white/5 space-y-4">
                      <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">Respaldo y Seguridad de Datos</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-blue-500 uppercase tracking-widest block mb-1">Exportar Backup</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Genera una copia encriptada de la base de datos de Apollo.</p>
                          </div>
                          <button onClick={handleBackup} className="bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center">
                            Descargar Base de Datos
                          </button>
                        </div>
                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-red-500 uppercase tracking-widest block mb-1">Restaurar Datos</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Restaura la BD desde un archivo .apbk encriptado. Peligroso.</p>
                          </div>
                          <label className="bg-red-600 hover:bg-red-700 text-white font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center cursor-pointer">
                            Subir Backup (.apbk)
                            <input type="file" accept=".apbk" className="hidden" onChange={handleRestore} />
                          </label>
                        </div>
                      </div>
                    </div>

                    """

if "const generateLicense = async" in content and "handleBackup" not in content:
    content = content.replace("const generateLicense", funcs_code)
    
if ui_target in content and "Exportar Backup" not in content:
    content = content.replace(ui_target, ui_code + ui_target)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Frontend patched")
