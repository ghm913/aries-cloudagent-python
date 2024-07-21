import json
import asyncio
from aiohttp import ClientSession

# Define the invitation details (replace with your actual invitation details)
{"@type": "https://didcomm.org/out-of-band/1.1/invitation", "@id": "856f780f-98de-4e0d-8ed9-1bfc49a9bdff", "label": "faber.agent", "handshake_protocols": ["https://didcomm.org/didexchange/1.1"], "services": [{"id": "#inline", "type": "did-communication", "recipientKeys": ["did:key:z6Mkg3sSCwXQZwpnDeHjfH9QUFiVWqKSvNcZMCMbaRmmr778#z6Mkg3sSCwXQZwpnDeHjfH9QUFiVWqKSvNcZMCMbaRmmr778"], "serviceEndpoint": "http://192.168.65.3:8020"}]}

async def connect_to_acapy(invitation):
    async with ClientSession() as session:
        acapy_url = 'http://localhost:8030/connections/receive-invitation'
        
        async with session.post(acapy_url, json=invitation) as response:
            if response.status == 200:
                result = await response.json()
                print("Connection established successfully:", json.dumps(result, indent=2))
            else:
                print(f"Failed to connect: {response.status}")
                print(await response.text())

asyncio.get_event_loop().run_until_complete(connect_to_acapy(invitation_details))
