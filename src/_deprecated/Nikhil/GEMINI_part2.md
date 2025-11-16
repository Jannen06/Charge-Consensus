You will output exactly one file.

===== simulate_driver.py =====

Create an asynchronous Python script `simulate_driver.py` meeting the following requirements.

Requirements:
- Use these imports only: asyncio, httpx, argparse, os, json, time, logging, typing.
- Top constants:
  - DENSO_API_HOST = os.getenv("DENSO_API_HOST", "https://hackathon.dndappsdev.net")
  - ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
  - DENSO_API_TOKEN = os.getenv("DENSO_API_TOKEN")  # must not be hard-coded
- Implement:
  - async def issue_vehicle_soc_vc(soc_percent: int) -> dict:
    - If DENSO_API_TOKEN set: perform httpx.post to f"{DENSO_API_HOST}/api/issue-credential" with JSON body {"credentialSubject": {"type":"VehicleSoC","soc_percent": soc_percent}} and Authorization header. Use 5s timeout. If real API missing, gracefully fallback.
    - If token not set: return simulated {"vc_id":"mock-vc-<timestamp>","credentialSubject":{"type":"VehicleSoC","soc_percent":soc_percent}}
  - async def create_presentation(user_did: str, vehicle_vc: dict) -> dict:
    - If DENSO_API_TOKEN set: POST to f"{DENSO_API_HOST}/api/request-presentation" with JSON including user_did and the VC
    - Else: return simulated {"presentation_id":"mock-pres-<timestamp>","vc":vehicle_vc}
  - async def send_charge_request(user_did: str, text: str, presentation: dict) -> dict:
    - POST to ORCHESTRATOR_URL + "/api/negotiate" with JSON {user_did, text, presentation}. Use 5s timeout. Print response JSON or error.
- CLI:
  - Accept args: --soc (int), --user-did (str), --text (str)
  - Default: soc=40, user_did="did:denso:user:sarah", text="I need to leave by 15:00"
- Main demo flow prints EXACTLY (these 3 lines when run):
  Step 1: Simulating Vehicle creating a new SoC credential...
  Step 2: Simulating Driver bundling VCs into a Presentation...
  Step 3: Sending trusted data + user text to our AI Orchestrator...
- Provide proper logging for success/error but DO NOT print tokens or raw presentation cryptographic proofs.
- If orchestrator returns 400 or unverified, print an informative error message.

No extra text outside the file marker. The content must be a complete, runnable Python file.
