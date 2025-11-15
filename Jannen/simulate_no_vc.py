import httpx
import asyncio

ORCHESTRATOR_URL = "http://127.0.0.1:8001"

async def simulate_first_time_user(user_did: str, text: str):
    """
    Simulates a user connecting for the first time, without a VC or presentation.
    """
    print(f"\n--- SIMULATING FIRST-TIME USER: {user_did.split(':')[-2]} ---")
    print(f"Sending text: '{text}'")
    print("NOTE: No presentation is being sent.")

    # The request body for a first-time user has no 'presentation'
    payload = {
        "user_did": user_did,
        "text": text,
        # "presentation": None # This field is omitted
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload)
            response.raise_for_status()
            print("\n[First-Time Sim] ✓ Orchestrator received request and issued a new VC.")
            print(f"[First-Time Sim] Orchestrator Response: {response.json()}")
    except Exception as e:
        print(f"\n[First-Time Sim] ✗ ERROR: {e}")

async def main():
    await simulate_first_time_user(
        user_did="did:denso:user:newbie:999",
        text="Hi, it's my first time here! My car is at 40% and I need to leave by the evening."
    )

if __name__ == "__main__":
    asyncio.run(main())
