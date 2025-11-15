from fastapi import FastAPI, Request, HTTPException
from starlette.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
from pydantic import BaseModel
import time
import json 
import asyncio 
import random
import uuid

from google import genai
from google.genai.types import GenerateContentConfig, Schema

# --- Main Application Setup ---
app = FastAPI(
    title="ChargeFlex AI Orchestrator",
    description="Manages EV charging requests using GenAI and Verifiable Credentials.",
    version="1.0.0"
)

# --- Configuration ---
DENSO_API_HOST = "https://hackathon1.didgateway.eu"
# Replace with your actual API key
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

# --- CORS Middleware ---
# Allows the dashboard (and other services) to communicate with the orchestrator
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for the hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory "Databases" ---
CHARGE_REQUEST_QUEUE = []
# This dictionary will store the latest VC for each user, acting as our "wallet"
USER_VCS = {} 

# --- API Data Models (Pydantic) ---

class UserNegotiateRequest(BaseModel):
    user_did: str
    text: str
    # The presentation is optional, as first-time users won't have one
    presentation: list | dict | None = None

class InternalChargeRequest(BaseModel):
    user_did: str
    priority: str
    leave_by: str | None = None
    min_soc: int | None = None
    start_soc: int | None = None
    original_text: str
    received_at: float
    charging_option: str | None = None
    points_awarded: int = 0

# --- HTML Dashboard Endpoint ---

@app.get("/", response_class=HTMLResponse, summary="Serves the main HTML dashboard")
async def get_dashboard():
    """
    Reads and returns the `dashboard.html` file, providing a real-time view of the charging queue.
    """
    try:
        with open("dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: dashboard.html not found.</h1><p>Please make sure the dashboard file is in the same directory as the orchestrator.</p>", status_code=404)

# --- Denso VC Helper Functions ---

async def issue_new_vc(user_did: str, soc: int) -> dict | None:
    """
    Issues a brand new Verifiable Credential for a first-time user via the Denso API.
    """
    print(f"[VC Logic] Issuing a new VC for first-time user {user_did} with SoC {soc}%...")
    
    credential_subject = {
        "id": user_did,
        "envelope_id": str(uuid.uuid4()),
        "envelope_version": "1.0.0",
        "schema_uri": "urn:cloudcharger:schemas:ocpi-session-envelope:1",
        "object_type": "ocpi_session",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(uuid.uuid4()),
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claims": {"soc_percent": soc}
    }
    
    url = f"{DENSO_API_HOST}/boy/api/issue-credential"
    params = {"credential_type": "ChargingSessionEnvelope"}
    headers = {"Content-Type": "application/json"}
    payload = {"credentialSubject": credential_subject}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            new_vc = response.json()
            print(f"[VC Logic] ✓ New VC issued successfully for {user_did}.")
            USER_VCS[user_did] = new_vc # Store the new VC
            return new_vc
    except Exception as e:
        print(f"[VC Logic] ✗ ERROR issuing new VC: {e}")
        return None

async def update_vc(user_did: str, existing_vc: dict, soc: int) -> dict | None:
    """
    Updates an existing Verifiable Credential with a new SoC value.
    Note: The update endpoint may not be implemented; this is a conceptual function.
    """
    print(f"[VC Logic] Attempting to update VC for user {user_did}...")
    
    # Modify the credential subject with the new SoC
    existing_vc['credentialSubject']['claims']['soc_percent'] = soc
    existing_vc['credentialSubject']['last_updated'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    url = f"{DENSO_API_HOST}/boy/api/update-credential" # This is a hypothetical endpoint
    headers = {"Content-Type": "application/json"}
    payload = existing_vc

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            updated_vc = response.json()
            print(f"[VC Logic] ✓ VC updated for {user_did}.")
            USER_VCS[user_did] = updated_vc # Store the updated VC
            return updated_vc
    except Exception:
        print(f"[VC Logic] ✗ Update failed (endpoint might not exist). Issuing a new VC instead.")
        return await issue_new_vc(user_did, soc)

# --- Core API Endpoints ---

@app.post("/api/negotiate", summary="Handles all incoming user charging requests")
async def handle_negotiation(request: UserNegotiateRequest):
    """
    This is the main entry point ("The Mouth"). It orchestrates the entire process:
    1. Manages Verifiable Credentials (VCs) for the user.
    2. Gathers context (like grid status).
    3. Queries the GenAI model for a smart charging decision.
    4. Passes the final, structured request to the internal queue ("The Brain").
    """
    print(f"\n--- New Request Received ---")
    print(f"User: {request.user_did}")
    print(f"Text: '{request.text}'")

    # Simplified SoC extraction from text for the demo
    start_soc = 50 # Default SoC
    if '%' in request.text:
        try:
            # Look for a number before the '%' sign
            soc_str = request.text.split('%')[0].strip().split()[-1]
            start_soc = int(soc_str)
        except (ValueError, IndexError):
            print("[Warning] Could not parse SoC from text, using default 50%.")
    
    # --- VC Management Logic ---
    user_vc = USER_VCS.get(request.user_did)
    if user_vc:
        # If the user is known, update their VC with the new SoC
        await update_vc(request.user_did, user_vc, start_soc)
    else:
        # If this is a new user, issue them a brand new VC
        await issue_new_vc(request.user_did, start_soc)
    
    # --- Contextual Enrichment ---
    # Simulate real-time grid status for the GenAI prompt
    is_grid_stressed = random.choice([True, False])
    print(f"[Context] Grid Status: {'STRESSED' if is_grid_stressed else 'STABLE'}")

    # --- GenAI Decision Making ---
    try:
        enriched_prompt = (
            f"A user with {start_soc}% battery says: '{request.text}'. "
            f"The power grid is currently {'stressed' if is_grid_stressed else 'stable'}."
        )
        print(f"[GenAI] Sending enriched prompt...")
        
        genai_json = await get_intent_from_genai(enriched_prompt)
        
        # Combine all data into a single, structured internal request
        genai_json.update({
            "user_did": request.user_did,
            "original_text": request.text,
            "received_at": time.time(),
            "start_soc": start_soc
        })
        print(f"[GenAI] ✓ Decision received: {genai_json}")

    except Exception as e:
        print(f"[GenAI] ✗ ERROR calling GenAI: {e}")
        raise HTTPException(status_code=500, detail=f"GenAI call failed: {e}")

    # --- Forward to Brain ---
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8001/api/charge_request", json=genai_json)
        print(f"[Orchestrator] ✓ Request for {request.user_did} sent to the internal queue.")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Failed to forward request to the internal queue.")

    return {"status": "request_received_and_processing", "intent": genai_json}

@app.post("/api/charge_request", summary="Adds a request to the internal charging queue")
async def add_charge_request(request: InternalChargeRequest):
    """
    This is "The Brain." It receives a validated, structured request and adds it to the master queue.
    """
    print(f"[Brain] Adding to queue: {request.user_did} (Priority: {request.priority})")
    
    global CHARGE_REQUEST_QUEUE
    # Ensure each user only has one active request
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    CHARGE_REQUEST_QUEUE.append(request)
    
    return {"status": "request_added_to_queue", "user_did": request.user_did}

@app.get("/api/status", summary="Provides the current status of the charging queue")
async def get_status():
    """
    This is "The Dashboard." It returns a sorted list of all cars currently in the queue.
    """
    priority_map = {"high": 3, "medium": 2, "low": 1}
    sorted_queue = sorted(
        CHARGE_REQUEST_QUEUE,
        key=lambda r: priority_map.get(r.priority, 0),
        reverse=True
    )
    return {
        "charger_count": 4, # Hardcoded for demo
        "chargers_in_use": len(sorted_queue),
        "priority_queue": [r.model_dump() for r in sorted_queue]
    }

# --- Gemini API Helper Function ---

async def get_intent_from_genai(user_text: str) -> dict:
    """
    Uses the Gemini model to make intelligent charging decisions based on user needs and grid status.
    """
    system_prompt = """You are an EV Charging Decision Engine. Your task is to analyze user requests and real-time grid status to make the best charging recommendation.

RULES:
1.  **Priority Analysis**:
    -   Assign "high" priority for urgent needs (e.g., 'panic', 'meeting', 'ASAP', 'running late').
    -   Assign "medium" priority for standard requests with a future deadline (e.g., 'by 6 PM', 'this evening').
    -   Assign "low" priority for flexible, non-urgent requests (e.g., 'no rush', 'overnight').
2.  **Time and SoC Extraction**:
    -   Convert all times to a 24-hour HH:MM format.
    -   Extract the target State of Charge (SoC) if mentioned ('full' = 100).
3.  **Grid-Aware Gamification**:
    -   If the grid is STABLE, the default option is always "fast_charge". Award a standard 10 loyalty points.
    -   If the grid is STRESSED:
        -   For "high" priority users, you MUST recommend "fast_charge" to meet their urgent need. They earn 0 points.
        -   For "medium" or "low" priority users, you MUST recommend "eco_charge" to help balance the grid. This is also healthier for the car's battery. Reward them with 100 loyalty points.

OUTPUT FORMAT:
You must return a single, valid JSON object with the following keys. Do not include any other text, markdown, or explanations.
{
  "priority": "high" | "medium" | "low",
  "leave_by": "HH:MM" | null,
  "min_soc": integer | null,
  "charging_option": "fast_charge" | "eco_charge",
  "points_awarded": integer
}

EXAMPLES:
Input: "A user with 20% battery says: 'I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70%!'. The power grid is currently stressed."
Output: {"priority": "high", "leave_by": "15:00", "min_soc": 70, "charging_option": "fast_charge", "points_awarded": 0}

Input: "A user with 85% battery says: 'Hey, I'm just plugging in. I'll be here all day, no rush at all.'. The power grid is currently stressed."
Output: {"priority": "low", "leave_by": null, "min_soc": null, "charging_option": "eco_charge", "points_awarded": 100}

Input: "A user with 50% battery says: 'I need my car by 6pm'. The power grid is currently stable."
Output: {"priority": "medium", "leave_by": "18:00", "min_soc": null, "charging_option": "fast_charge", "points_awarded": 10}
"""
 
    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\nAnalyze this request:\n{user_text}",
            config=GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string"},
                        "leave_by": {"type": ["string", "null"]},
                        "min_soc": {"type": ["integer", "null"]},
                        "charging_option": {"type": "string"},
                        "points_awarded": {"type": "integer"}
                    },
                    "required": ["priority", "leave_by", "min_soc", "charging_option", "points_awarded"]
                }
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI] ✗ ERROR during GenAI call: {e}. Using fallback.")
        return {"priority": "medium", "leave_by": None, "min_soc": None, "charging_option": "fast_charge", "points_awarded": 10}

# --- Main Execution Guard ---
if __name__ == "__main__":
    print("Starting ChargeFlex AI Orchestrator on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
