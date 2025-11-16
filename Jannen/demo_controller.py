import httpx
import asyncio
import random
import webbrowser
import threading
import time
import subprocess
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001"
DEMO_SERVER_PORT = 8080

# --- Helper Functions ---
def run_web_server():
    """Serves the dashboard.html file on a local port."""
    server_address = ('', DEMO_SERVER_PORT)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

async def send_live_request(text: str):
    """Sends a single, dynamic request from the live demo."""
    if not text:
        print("No text input provided.")
        return
        
    print(f"\n>>> Sending LIVE request for: LIVE-DEMO...")
    payload = {
        "user_did": f"did:denso:user:live-demo:{random.randint(100, 999)}",
        "text": text
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload)
            response.raise_for_status()
            print("✓ Live request accepted.")
    except Exception as e:
        print(f"✗ ERROR sending live request: {e}")

# --- Main Controller Logic ---
async def main_controller():
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    print("--- Charge Consensus Demo Controller ---")
    print(f"--- Dashboard server starting at http://localhost:{DEMO_SERVER_PORT}/dashboard.html ---")
    time.sleep(1)
    webbrowser.open_new_tab(f"http://localhost:{DEMO_SERVER_PORT}/dashboard.html")

    while True:
        print("\n--- Demo Options ---")
        print("1. Simulate ALL initial users (Runs simulate_demo.py)")
        print("2. Activate LIVE TEXT demo")
        print("3. EXIT")
        choice = input("Enter your choice (1, 2, or 3): ")

        if choice == '1':
            print("\n--- Calling simulate_demo.py ---")
            subprocess.run(["python3", "simulate_demo.py"])
            print("\n✓ 'simulate_demo.py' finished.")

        elif choice == '2':
            # --- The Reliable Text Input ---
            print("\n--- Live Text Demo ---")
            text_input = input(">>> Enter your live charging request: ")
            if text_input:
                await send_live_request(text_input)

        elif choice == '3':
            print("\nExiting demo controller. Thank you for using Charge Consensus!")
            break
            
        else:
            print("\nInvalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    try:
        asyncio.run(main_controller())
    except KeyboardInterrupt:
        print("\nDemo controller shut down.")
