import asyncio
import websockets
import json
from jose import jwt
from datetime import datetime, timedelta
import time

SECRET_KEY = "apollo_super_secreto_para_master_is_2026_x"
ALGORITHM = "HS256"

def create_token():
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode = {"sub": "boris_test_bench@test.com", "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def test_viewer_hq():
    token = create_token()
    # Connect to the /hq endpoint
    uri = f"ws://localhost:8001/api/ws/viewer/767/hq?token={token}"
    print(f"Connecting to HQ endpoint at {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected as HQ viewer!")
            
            async def send_pings():
                while True:
                    await asyncio.sleep(10)
                    try:
                        await websocket.send("ping")
                        print("Sent ping to backend")
                    except Exception as e:
                        print("Ping error:", e)
                        break
            
            asyncio.create_task(send_pings())
            
            chunks_received = 0
            total_bytes = 0
            last_time = time.time()
            
            while True:
                try:
                    msg = await websocket.recv()
                    
                    if isinstance(msg, bytes):
                        chunks_received += 1
                        total_bytes += len(msg)
                        
                        current_time = time.time()
                        elapsed = current_time - last_time
                        
                        if elapsed >= 1.0:
                            chunks_per_sec = chunks_received / elapsed
                            kbps = (total_bytes * 8) / (1024 * elapsed)
                            print(f"HQ STREAM: {chunks_per_sec:.2f} chunks/sec | {kbps:.2f} kbps | Last chunk size: {len(msg)} bytes")
                            
                            chunks_received = 0
                            total_bytes = 0
                            last_time = current_time
                    else:
                        print(f"Received text message: {msg}")
                except Exception as e:
                    print("Connection closed or error:", e)
                    break
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_viewer_hq())
