import asyncio
import websockets
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import auth
import models
from database import SessionLocal

async def test_viewer():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.activo == True).first()
        if not user:
            print("No active user found!")
            return
        
        token = auth.create_access_token(data={"sub": user.email, "rol": user.rol})
        print(f"Technician Token: {token}")
    finally:
        db.close()
        
    device_id = 765
    ws_url = f"wss://support.ultimate.net.ar/api/ws/viewer/{device_id}?token={token}"
    print(f"Connecting to viewer WebSocket at {ws_url}...")
    
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            print("CONNECTED to viewer WebSocket successfully!")
            
            # Send a ping to keep it alive
            async def send_pings():
                while True:
                    await asyncio.sleep(5)
                    try:
                        await ws.send("ping")
                        print("Sent ping to server")
                    except Exception:
                        break
            
            asyncio.create_task(send_pings())
            
            # Wait for frames
            for _ in range(50): # read up to 50 messages
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    try:
                        data = json.loads(msg)
                        m_type = data.get('type')
                        print(f"Received message type: {m_type}")
                        if m_type == 'frame':
                            # En el nuevo protocolo, data["frame"] contiene {"frame": encoded_b64, "delta": delta}
                            # o directamente data["image"]
                            frame = data.get('frame') or {}
                            if isinstance(frame, dict):
                                img_data = frame.get('frame', '')
                                delta = frame.get('delta')
                            else:
                                img_data = frame
                                delta = None
                            print(f"-> Frame: delta={delta}, length={len(img_data)}")
                        elif m_type == 'error':
                            print(f"-> ERROR from server: {data.get('message')}")
                    except json.JSONDecodeError:
                        print(f"Received raw text message: {msg[:100]}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for message from server...")
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == '__main__':
    asyncio.run(test_viewer())
