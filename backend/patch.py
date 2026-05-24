with open('p:\\ApolloSupport\\backend\\main.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('async def websocket_centinela(websocket: WebSocket, client_id: int, device_name: str = "Desconocido", license_key: str = Query(""), hq: str = Query(None), device_id: int = Query(None)):', 'async def websocket_centinela(websocket: WebSocket, client_id: int, device_name: str = "Desconocido", license_key: str = Query(""), hq: str = Query(None), device_id: int = Query(None), alt_id: str = Query(None)):')
c = c.replace('logger.info(f"[WS-HANDSHAKE] Intento de conexion AGENTE device_id={device_id} name={device_name}")', 'logger.info(f"[WS-HANDSHAKE] Intento de conexion AGENTE device_id={device_id} name={device_name} alt_id={alt_id}")')
c = c.replace('res = await asyncio.to_thread(handle_centinela_handshake, client_id, device_name, license_key, hq, device_id)', 'res = await asyncio.to_thread(handle_centinela_handshake, client_id, device_name, license_key, hq, device_id, alt_id)')
with open('p:\\ApolloSupport\\backend\\main.py', 'w', encoding='utf-8') as f:
    f.write(c)
