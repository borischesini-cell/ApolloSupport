import asyncio
import websockets
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import auth
import models
from database import SessionLocal

async def test_hugo():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.activo == True).first()
        if not user:
            print("No active user found in local DB!")
            # Fallback: create a temporary token manually
            token = auth.create_access_token(data={"sub": "boris@test.com", "rol": "admin"})
            print(f"Using generated fallback token: {token}")
        else:
            token = auth.create_access_token(data={"sub": user.email, "rol": user.rol})
            print(f"Technician Token ({user.email}): {token}")
    finally:
        db.close()
        
    device_id = 773
    ws_url = f"ws://localhost:8001/api/ws/viewer/{device_id}?token={token}"
    print(f"Connecting to local viewer WebSocket at {ws_url}...")
    
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
            
            pinger = asyncio.create_task(send_pings())
            
            # Wait for frames
            frames_count = 0
            for i in range(10): # read up to 10 messages
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    try:
                        data = json.loads(msg)
                        m_type = data.get('type')
                        print(f"[{i}] Received message type: {m_type}")
                        if m_type == 'frame':
                            frames_count += 1
                            frame = data.get('frame') or {}
                            if isinstance(frame, dict):
                                img_data = frame.get('frame', '')
                                delta = frame.get('delta')
                            else:
                                img_data = frame
                                delta = None
                            print(f"  -> Frame: delta={delta}, length={len(img_data)}")
                        elif m_type == 'error':
                            print(f"  -> ERROR from server: {data.get('message')}")
                    except json.JSONDecodeError:
                        print(f"[{i}] Received raw text message: {msg[:100]}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for message from server...")
                    break
            
            pinger.cancel()
            print(f"\nTest finished. Received {frames_count} frames.")
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == '__main__':
    asyncio.run(test_hugo())
