import httpx
import asyncio

async def test_gemini():
    apiKey = "AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc"
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={apiKey}"
    
    payload = {
        "contents": [{
            "parts": [{"text": "Respond with JSON: {'message': 'API works!'}"}]
        }]
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ API Key works!")
                text = result['candidates'][0]['content']['parts'][0]['text']
                print(f"Response: {text}")
            else:
                print(f"✗ Error: {response.text}")
                
    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(test_gemini())