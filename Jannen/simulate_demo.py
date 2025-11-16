import httpx
import asyncio
import sys
import argparse
import random # <--- THE MISSING IMPORT

ORCHESTRATOR_URL = "http://127.0.0.1:8001"

# --- Define Your User Scenarios ---
USERS = [
    {
        "did": "did:denso:user:sarah:456",
        "text": "I'M IN A PANIC! I'm at 3% and I have a client meeting at 3 PM. I need at least 70% charge!"
    },
    {
        "did": "did:denso:user:tom:123",
        "text": "Hey, I'm just plugging in. My SoC is at 50%. I'll be here all day, no rush at all."
    },
    {
        "did": "did:denso:user:maria:789",
        "text": "My car is at 15%. I just need a full charge by tomorrow morning, please."
    }
]

async def send_request(user: dict):
    """Sends a single user request to the orchestrator."""
    driver_name = user['did'].split(':')[-2]
    print(f"\n--- Simulating Request for: {driver_name.upper()} ---")
    
    payload = {"user_did": user['did'], "text": user['text']}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload)
            response.raise_for_status()
            print(f"✓ Request for {driver_name} accepted. Orchestrator is processing...")
    except Exception as e:
        print(f"✗ ERROR for {driver_name}: {e}")

async def main():
    """Main function to run the simulation based on command-line arguments."""
    parser = argparse.ArgumentParser(description="Charge Consensus Demo Simulator")
    parser.add_argument(
        '--mode', 
        type=str, 
        default='all', 
        choices=['all', 'dynamic'],
        help="Simulation mode: 'all' to run all predefined users, 'dynamic' to read from stdin."
    )
    args = parser.parse_args()

    if args.mode == 'all':
        print("--- Running 'ALL USERS' Simulation ---")
        tasks = [send_request(user) for user in USERS]
        await asyncio.gather(*tasks)
        print("\n--- All user simulations complete ---")
    
    elif args.mode == 'dynamic':
        print("\n--- Starting 'DYNAMIC' Mode ---")
        print("Waiting for live input. Type your request and press Enter.")
        dynamic_text = sys.stdin.readline().strip()
        
        if dynamic_text:
            dynamic_user = {
                "did": f"did:denso:user:live-demo:{random.randint(100,999)}",
                "text": dynamic_text
            }
            await send_request(dynamic_user)
        else:
            print("No input received. Exiting.")

    print("Check the dashboard at http://127.0.0.1:8001 to see the results.")

if __name__ == "__main__":
    asyncio.run(main())
