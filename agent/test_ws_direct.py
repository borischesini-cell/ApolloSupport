import asyncio
import websockets
import json
import sys

sys.path.append('p:/ApolloSupport/agent')
import centinela

async def test_ws():
    uri = "ws://localhost:8001/api/ws/centinela/670?device_name=SRV-TEST&license_key=APOLLO-TEST&alt_id=123&session_id=99"
    async with websockets.connect(uri) as websocket:
        print("Connected!")
        sys_info = await asyncio.get_event_loop().run_in_executor(None, centinela.get_system_info_extended)
        payload = {'type': 'telemetry', 'data': {'status': 'online', 'system_info': sys_info}}
        
        print("Sending telemetry...")
        await websocket.send(json.dumps(payload))
        print("Telemetry sent!")
        
        try:
            while True:
                msg = await websocket.recv()
                print("Received:", msg)
        except Exception as e:
            print(f"Closed: {e}")

asyncio.run(test_ws())
