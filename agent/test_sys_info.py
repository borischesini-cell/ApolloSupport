import sys
import asyncio
import json

sys.path.append('p:/ApolloSupport/agent')
import centinela

async def test():
    sys_info = await asyncio.get_event_loop().run_in_executor(None, centinela.get_system_info_extended)
    payload = {'type': 'telemetry', 'data': {'system_info': sys_info}}
    try:
        print('Result:', json.dumps(payload))
    except Exception as e:
        print("JSON dumps failed:", e)

asyncio.run(test())
