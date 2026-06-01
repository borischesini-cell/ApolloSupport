import asyncio
import websockets
import json
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "apollo_super_secreto_para_master_is_2026_x"
ALGORITHM = "HS256"

def create_token():
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode = {"sub": "boris_test_bench@test.com", "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def test_viewer():
    token = create_token()
    uri = f"ws://localhost:8001/api/ws/viewer/767?token={token}"
    print(f"Connecting to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        print("Connected as viewer!")
        
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
        
        import time
        frames_received = 0
        total_frames = 0
        last_time = time.time()
        
        while True:
            try:
                msg = await websocket.recv()
                try:
                    data = json.loads(msg)
                    mtype = data.get("type")
                    if mtype == "frame":
                        frames_received += 1
                        total_frames += 1
                        
                        current_time = time.time()
                        elapsed = current_time - last_time
                        
                        if elapsed >= 1.0:
                            fps = frames_received / elapsed
                            frame_len = len(data.get("frame", ""))
                            delta = data.get("delta")
                            print(f"FPS: {fps:.2f} | Total frames: {total_frames} | Last Frame Length: {frame_len} | Delta: {delta}")
                            
                            frames_received = 0
                            last_time = current_time
                            
                    else:
                        print("Received message:", data)
                except json.JSONDecodeError:
                    print("Received raw msg:", msg)
            except Exception as e:
                print("Connection closed or error:", e)
                break

if __name__ == "__main__":
    asyncio.run(test_viewer())
