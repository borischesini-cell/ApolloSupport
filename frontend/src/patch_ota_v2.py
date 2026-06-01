import os

app_file = 'p:/ApolloSupport/frontend/src/App.tsx'

with open(app_file, 'r', encoding='utf-8') as f:
    app_content = f.read()

if 'forceCentinelaUpdate' not in app_content:
    app_content = app_content.replace('import { getActiveCentinelas,', 'import { forceCentinelaUpdate, getActiveCentinelas,', 1)

prog_code = """                                          <>CPU: {telemetry?.cpu || 0}% | RAM: {telemetry?.ram || 0}% {telemetry?.agent_version && <span className="text-amber-500 font-extrabold ml-1">V{telemetry.agent_version}</span>}</>
                                          ) : 'Desconectado'}
                                        </div>
                                        {/* Info extendida del sistema */}
                                        {isOnline && telemetry?.system_info && (
                                          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                            {telemetry.system_info.logged_user && (
                                              <span className="text-[9px] text-cyan-400 font-bold">
                                                👤 {telemetry.system_info.user_full || telemetry.system_info.logged_user}
                                              </span>
                                            )}
                                            {telemetry.system_info.windows_name && (
                                              <span className="text-[9px] text-slate-400 font-semibold">
                                                💻 {telemetry.system_info.windows_name}
                                              </span>
                                            )}
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

target = """                                          <>CPU: {telemetry?.cpu || 0}% | RAM: {telemetry?.ram || 0}%</>
                                        ) : 'Desconectado'}
                                      </div>
                                      {/* Info extendida del sistema — viene de system_info en telemetría */}
                                      {isOnline && telemetry?.system_info && (
                                        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                          {telemetry.system_info.logged_user && (
                                            <span className="text-[9px] text-cyan-400 font-bold">
                                              👤 {telemetry.system_info.user_full || telemetry.system_info.logged_user}
                                            </span>
                                          )}
                                          {telemetry.system_info.windows_name && (
                                            <span className="text-[9px] text-slate-400 font-semibold">
                                              💻 {telemetry.system_info.windows_name}
                                            </span>
                                          )}
                                          {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                            <span className="text-[9px] text-amber-400 font-semibold">
                                              🗓️ Update: {telemetry.system_info.last_windows_update}
                                            </span>
                                          )}
                                        </div>
                                      )}"""

if "Actualización OTA:" not in app_content:
    if target in app_content:
        app_content = app_content.replace(target, prog_code)
    else:
        print("COULD NOT FIND TARGET")

with open(app_file, 'w', encoding='utf-8') as f:
    f.write(app_content)
print("UI Patched successfully")
