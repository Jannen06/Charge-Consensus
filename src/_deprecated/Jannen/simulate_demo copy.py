import httpx
import asyncio
import random

ORCHESTRATOR_URL = "http://127.0.0.1:8001"

# --- Define Your User Scenarios ---
USERS = [
    {
        "did": "did:denso:user:sarah:456",
        "text": "I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70% charge!"
    },
    {
        "did": "did:denso:user:tom:123",
        "text": "Hey, I'm just plugging in. My SoC is at 50%. I'll be here all day, no rush at all."
    },
    {
        "did": "did:denso:user:newbie:999",
        "text": "Hi, it's my first time here! My car is at 40% and I need to leave by the evening."
    },
    {
        "did": "did:denso:user:maria:789",
        "text": "My car is at 15%, just need a full charge by tomorrow morning."
    }
]

async def send_request(user: dict):
    """Sends a single user request to the orchestrator."""
    driver_name = user['did'].split(':')[-2]
    print(f"\n--- Simulating Request for: {driver_name.upper()} ---")
    
    payload = {
        "user_did": user['did'],
        "text": user['text'],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload)
            response.raise_for_status()
            print(f"✓ Request for {driver_name} accepted. Orchestrator is processing...")
    except Exception as e:
        print(f"✗ ERROR for {driver_name}: {e}")

async def main():
    """Runs the simulation by sending a request from a random user."""
    print("--- Starting Dynamic Customer Request Simulation ---")
    
    # Select a random user to simulate
    user_to_simulate = random.choice(USERS)
    
    await send_request(user_to_simulate)
    
    print("\n--- Simulation Complete ---")
    print("Check the dashboard at http://127.0.0.1:8001 to see the result.")


if __name__ == "__main__":
    asyncio.run(main())
