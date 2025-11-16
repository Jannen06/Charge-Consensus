import httpx
import asyncio

ORCHESTRATOR_URL = "http://127.0.0.1:8080"

USERS = [
    {"user_did": "did:denso:user:sarah:456", "text": "I'M IN A PANIC! I'm at 3% and I have a client meeting at 3 PM. I need at least 70% charge!"},
    {"user_did": "did:denso:user:tom:123", "text": "Hey, I'm just plugging in. My SoC is at 50%. I'll be here all day, no rush at all."},
    {"user_did": "did:denso:user:maria:789", "text": "My car is at 15%. I just need a full charge by tomorrow morning, please."}
]

async def send_request(user: dict):
    driver_name = user['user_did'].split(':')[-2]
    print(f">>> Simulating request for: {driver_name.upper()}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=user)
            response.raise_for_status()
    except Exception as e:
        print(f"✗ ERROR for {driver_name}: {e}")

async def main():
    print("--- Running 'ALL USERS' Simulation ---")
    tasks = [send_request(user) for user in USERS]
    await asyncio.gather(*tasks)
    print("--- All initial users have been sent to the orchestrator. ---")

if __name__ == "__main__":
    asyncio.run(main())
