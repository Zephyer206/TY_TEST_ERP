"""Direct test of backend API response."""

import asyncio
import httpx

async def test():
    # First login to get token
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        # Login
        login_resp = await client.post('/api/v1/auth/login', json={
            'username': 'admin',
            'password': '123456'
        })
        token = login_resp.json()['access_token']
        print(f'Login successful, token: {token[:20]}...')

        # Test part-names API
        headers = {'Authorization': f'Bearer {token}'}
        resp = await client.get('/api/v1/part-names?limit=1', headers=headers)

        print(f'\nStatus: {resp.status_code}')
        print(f'Response: {resp.text}')

        data = resp.json()
        if data:
            first = data[0]
            print('\nFields in response:')
            for key in first.keys():
                print(f'  {key}: {first[key]}')

if __name__ == '__main__':
    asyncio.run(test())
