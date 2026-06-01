import os

app_file = 'p:/ApolloSupport/frontend/src/App.tsx'
api_file = 'p:/ApolloSupport/frontend/src/api.ts'

with open(api_file, 'r', encoding='utf-8') as f:
    api_content = f.read()

if 'forceCentinelaUpdate' not in api_content:
    new_api = """
export const forceCentinelaUpdate = async (deviceId: string | number) => {
    const response = await fetch(`${API_URL}/centinelas/${deviceId}/force_update`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Error al forzar actualizacion');
    return response.json();
};
"""
    with open(api_file, 'a', encoding='utf-8') as f:
        f.write(new_api)

with open(app_file, 'r', encoding='utf-8') as f:
    app_content = f.read()

if 'forceCentinelaUpdate' not in app_content:
    app_content = app_content.replace('import { getActiveCentinelas,', 'import { forceCentinelaUpdate, getActiveCentinelas,', 1)

btn_code = """
                                      <div className="flex items-center gap-1.5 shrink-0">
                                        {isOnline && telemetry?.agent_version && (
                                          <button
                                            onClick={async (e) => {
                                              e.stopPropagation();
                                              if (window.confirm(`¿Forzar actualización OTA en ${dev.device_name}?`)) {
                                                try {
                                                  await forceCentinelaUpdate(dev.id);
                                                  alert('Comando OTA enviado correctamente. Verás el progreso en breve.');
                                                } catch (err) {
                                                  alert('Error al forzar OTA');
                                                }
                                              }
                                            }}
                                            className="p-1.5 rounded-xl bg-amber-500/10 text-amber-500 hover:bg-amber-500 hover:text-white transition-colors"
                                            title="Forzar actualización OTA ahora"
                                          >
                                            <ArrowUpRight size={14} />
                                          </button>
                                        )}
"""

if "Forzar actualización OTA ahora" not in app_content:
    app_content = app_content.replace('<div className="flex items-center gap-1.5 shrink-0">', btn_code)

prog_code = """
                                            {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                              <span className="text-[9px] text-amber-400 font-semibold">
                                                🗓️ Update: {telemetry.system_info.last_windows_update}
                                              </span>
                                            )}
                                          </div>
                                        )}
                                        {isOnline && telemetry?.ota_status && (
                                          <div className="mt-2 w-full pr-4">
                                            <div className="flex justify-between items-center text-[10px] text-amber-500 font-bold mb-1 uppercase">
                                              <span>Actualización OTA: {telemetry.ota_status}</span>
                                              <span>{telemetry.ota_progress}%</span>
                                            </div>
                                            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                              <div className="bg-amber-500 h-1.5 transition-all" style={{ width: `${telemetry.ota_progress}%` }}></div>
                                            </div>
                                          </div>
                                        )}
"""

if "Actualización OTA:" not in app_content:
    app_content = app_content.replace("""
                                            {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                              <span className="text-[9px] text-amber-400 font-semibold">
                                                🗓️ Update: {telemetry.system_info.last_windows_update}
                                              </span>
                                            )}
                                          </div>
                                        )}""", prog_code)

with open(app_file, 'w', encoding='utf-8') as f:
    f.write(app_content)
print("UI Patched successfully")
