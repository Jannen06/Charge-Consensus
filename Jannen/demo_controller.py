import httpx
import asyncio
import speech_recognition as sr
import random
import webbrowser
import threading
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001"
DEMO_SERVER_PORT = 8080

# --- User Scenarios ---
USERS = [
    {"did": "did:denso:user:sarah:456", "text": "I'M IN A PANIC! I'm at 3% and I have a client meeting at 3 PM. I need at least 70% charge!"},
    {"did": "did:denso:user:tom:123", "text": "Hey, I'm just plugging in. My SoC is at 50%. I'll be here all day, no rush at all."},
    {"did": "did:denso:user:maria:789", "text": "My car is at 15%. I just need a full charge by tomorrow morning, please."}
]

# --- Helper Functions ---
def run_web_server():
    """Serves the dashboard.html file on a local port."""
    server_address = ('', DEMO_SERVER_PORT)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

async def send_request(user_did: str, text: str): # <--- BUG FIX 1: Accept user_did and text separately
    """Sends a request to the orchestrator."""
    driver_name = user_did.split(':')[-2]
    print(f"\n>>> Sending request for: {driver_name.upper()}...")
    
    # --- BUG FIX 2: Construct the payload with the correct keys ---
    payload = {
        "user_did": user_did,
        "text": text
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload) # Send the correct payload
            response.raise_for_status()
            print(f"✓ Request for {driver_name} accepted.")
    except Exception as e:
        print(f"✗ ERROR for {driver_name}: {e}")

def listen_for_voice_command():
    """Listens for a voice command and returns the transcribed text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Calibrating microphone... Please wait a moment.")
        r.adjust_for_ambient_noise(source, duration=1)
        print("✅  Microphone ready. Please speak your charging request now.")
        try:
            audio = r.listen(source, timeout=10, phrase_time_limit=10)
            print(">>> Processing audio...")
            text = r.recognize_google(audio)
            print(f"✓ Recognized: '{text}'")
            return text
        except Exception as e:
            print(f"✗ Speech Recognition Error: {e}")
            return None

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
        print("1. Simulate ALL initial users (Sarah, Tom, Maria)")
        print("2. Activate LIVE VOICE demo")
        print("3. EXIT")
        choice = input("Enter your choice (1, 2, or 3): ")

        if choice == '1':
            print("\n--- Running 'ALL USERS' Simulation ---")
            # --- BUG FIX 3: Pass the arguments correctly ---
            tasks = [send_request(user['did'], user['text']) for user in USERS]
            await asyncio.gather(*tasks)
            print("\n✓ All initial users have been added to the queue.")

        elif choice == '2':
            text = listen_for_voice_command()
            if text:
                live_user_did = f"did:denso:user:live-demo:{random.randint(100, 999)}"
                await send_request(live_user_did, text)

        elif choice == '3':
            print("\nExiting demo controller. Thank you!")
            break
            
        else:
            print("\nInvalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    try:
        asyncio.run(main_controller())
    except KeyboardInterrupt:
        print("\nDemo controller shut down.")
