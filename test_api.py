import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        r = await client.get('http://localhost:8000/api/buildings')
        print(f'Status: {r.status_code}')
        print(f'Content: {r.text}')

asyncio.run(test())
