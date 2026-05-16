import asyncio
import websockets
import json

async def test():
    url = "ws://localhost:8001/api/ws/centinela/575774?device_name=TestDevice&license_key="
    try:
        async with websockets.connect(url) as ws:
            print("Connected!")
            await ws.send(json.dumps({"type": "telemetry", "data": {"status": "online"}}))
            print("Telemetry sent!")
            resp = await ws.recv()
            print(f"Received: {resp}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
