import speech_recognition as sr
import httpx
import asyncio
import webbrowser
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001"
DEMO_SERVER_PORT = 8080 # Port for the local dashboard server

def run_web_server():
    """A simple function to serve the dashboard.html file."""
    server_address = ('', DEMO_SERVER_PORT)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"--- Dashboard server running at http://localhost:{DEMO_SERVER_PORT} ---")
    httpd.serve_forever()

async def send_dynamic_request(text: str):
    """Sends the transcribed text to the orchestrator."""
    if not text:
        print("Could not understand audio.")
        return

    print(f"\n[DEMO] Recognized Text: '{text}'")
    print("[DEMO] Sending to Charge Consensus Orchestrator...")
    
    dynamic_user = {
        "did": f"did:denso:user:live-demo:{random.randint(100,999)}",
        "text": text
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=dynamic_user)
            response.raise_for_status()
            print("[DEMO] ✓ Request sent successfully! Check the dashboard.")
    except Exception as e:
        print(f"[DEMO] ✗ ERROR: Could not send request to orchestrator: {e}")


def listen_and_transcribe():
    """Uses the microphone to listen for a command and transcribe it."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n--- Live Demo Mode ---")
        print("Calibrating microphone... please wait.")
        r.adjust_for_ambient_noise(source, duration=1)
        print("🎤 Say your charging request now!")
        
        try:
            audio = r.listen(source, timeout=10, phrase_time_limit=10)
            print("Processing audio...")
            # Use the Google Web Speech API for transcription (requires internet)
            text = r.recognize_google(audio)
            asyncio.run(send_dynamic_request(text))
        except sr.WaitTimeoutError:
            print("No speech detected within the time limit.")
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio.")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    # 1. Start the local web server in a separate thread
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    # 2. Open the dashboard in the default web browser
    webbrowser.open_new_tab(f"http://localhost:{DEMO_SERVER_PORT}/dashboard.html")
    
    # 3. Start listening for the voice command
    # This must run in the main thread
    listen_and_transcribe()
