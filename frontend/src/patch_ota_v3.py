import os
import re

app_file = 'p:/ApolloSupport/frontend/src/App.tsx'

with open(app_file, 'r', encoding='utf-8') as f:
    app_content = f.read()

# 1. Update CPU line to include agent version
cpu_pattern = re.compile(r'(<>CPU:\s*\{telemetry\?\.cpu\s*\|\|\s*0\}%\s*\|\s*RAM:\s*\{telemetry\?\.ram\s*\|\|\s*0\}%)(</>)')
app_content = cpu_pattern.sub(r'\1 {telemetry?.agent_version && <span className="text-amber-500 font-extrabold ml-1">V{telemetry.agent_version}</span>}\2', app_content)

# 2. Add OTA progress block right before antivirus or right after last_windows_update
ota_block = """
                                            {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                              <span className="text-[9px] text-amber-400 font-semibold">
                                                🗓️ Update: {telemetry.system_info.last_windows_update}
                                              </span>
                                            )}
                                          </div>
                                        )}
                                        {/* OTA PROGRESS Y BOTON */}
                                        {isOnline && (
                                          <div className="mt-1 w-full pr-4">
                                            {telemetry?.ota_status && (
                                              <>
                                                <div className="flex justify-between items-center text-[9px] text-amber-500 font-bold mb-1 uppercase">
                                                  <span>Actualización OTA: {telemetry.ota_status}</span>
                                                  <span>{telemetry.ota_progress}%</span>
                                                </div>
                                                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                                  <div className="bg-amber-500 h-1.5 transition-all" style={{ width: `${telemetry.ota_progress}%` }}></div>
                                                </div>
                                              </>
                                            )}
                                            {telemetry?.agent_version && !telemetry?.ota_status && (
                                              <button
                                                onClick={async (e) => {
                                                  e.stopPropagation();
                                                  if (window.confirm(`¿Forzar actualización OTA en ${dev.device_name}?`)) {
                                                    try {
                                                      await forceCentinelaUpdate(dev.id);
                                                      alert('Comando OTA enviado. Verás el progreso en breve.');
                                                    } catch (err) {
                                                      alert('Error al forzar OTA');
                                                    }
                                                  }
                                                }}
                                                className="mt-1 flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-lg bg-amber-500/10 text-amber-500 hover:bg-amber-500 hover:text-white transition-colors"
                                                title="Forzar actualización OTA ahora"
                                              >
                                                <ArrowUpRight size={10} /> Forzar Actualización OTA
                                              </button>
                                            )}
                                          </div>
                                        )}
"""

update_pattern = re.compile(r"(\{\s*telemetry\.system_info\.last_windows_update && telemetry\.system_info\.last_windows_update !== 'No disponible' && \([\s\S]*?</span>\s*\)\s*\})(\s*</div>\s*\)\})")
if "Actualización OTA:" not in app_content:
    app_content = update_pattern.sub(ota_block, app_content)

with open(app_file, 'w', encoding='utf-8') as f:
    f.write(app_content)
print("UI Patched successfully with regex")
