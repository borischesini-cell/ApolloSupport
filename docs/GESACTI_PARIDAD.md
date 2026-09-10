ApolloSupport ↔ GesActi (Util_Activacion) — paridad funcional
Fecha: 2026-08-20

Panel de referencia: Panel2016.prg ("CLIENTES CON VERSIÓN 2016") + CliGesCom (Activa.prg)


YA EN SUPPORT (Base Clientes / Activaciones ERP)
================================================
[x] Todo / Nada / Invierte (marcar clientes)
[x] Monitoreo masivo (cartel / corte / forzar fecha a marcados)
[x] Filtro por tipo de cartel + ver tipo en columna
[x] Quitar carteles / Poner cartel a marcados
[x] Catálogo misi_messages (alta/edición)
[x] Extracto de cuenta (ERP vía CCLIFAC)
[x] Saldo + Últ. pago (CULPA)
[x] Licencias por cliente (misi_licenses)
[x] Monitoreo por serial (m_down, m_newdate, m_tipmsg, m_showmode, m_text, auto-ext)
[x] Vista previa de cartel
[x] Activar / desactivar licencia (l_desact)
[x] Terminales / nodos activados (misi_terminals) + desactivar nodo
[x] Alta cliente GesActi (código 4 + producto E/S/R/P) → CLIGESCO.DBF en M:\programa
[x] Generar serial GesActi (módulos + CRC + MySQL)
[x] Reportes por serial (misi_report) + Nodos (misi_nodorepo) + System (misi_sysrepo)
[x] Sincronizar clientes desde CLIGESCO.DBF
[x] Lic Facturadas (LisArtC + Articulo vía ERPBridge; botón "Lic Fac" en Base Clientes)
[x] Activaciones pendientes OnLine (misi_request → Activar/Denegar/Pendiente/Msg/Fecha)
[x] Extensiones OnLine (misi_extension → Generar; actualiza misi_licenses web)


PENDIENTE / PARCIAL (GesActi tiene y Support aún no)
====================================================
[ ] Seriales 2008 (ClieSeri / ActiData) — modelo legacy
[ ] Activaciones Manual / Telefónica (fuera de misi_request web)
[ ] Extensiones Manual / Telefónica / misi_patch
[ ] Funciones por serial (misi_LicenFun / misi_funciones)
[ ] Establecer usuario/password web (ClieSeri)
[ ] Expiraciones de nodos (vista ActiData)
[ ] Código de contingencia (Ctrl+F12)
[ ] Sync MySQL bidireccional FTP / hosting antiguo (incluye 192.168.10.24 local)
[ ] IA / Connect (módulos aparte en GesActi)


NOTAS
=====
- En GesActi el Monitoreo MASIVO solo aplica cartel (suspender/forzar están comentados).
  En Support el Monitoreo masivo también permite corte y forzar fecha (más completo).
- "Nodos" en Reportes = misi_nodorepo (heartbeats).
- Activaciones/Extensiones OL escriben solo MySQL web (apolloge_masterisi), no el servidor local 192.168.10.24.
- Lic Facturadas usa IVA 21% para neto (aproximación de GetDgi de GesActi).
