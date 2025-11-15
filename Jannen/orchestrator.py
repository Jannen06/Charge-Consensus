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

# --- Configuration & Global State ---
DENSO_API_HOST = "https://hackathon1.didgateway.eu"
# IMPORTANT: Replace with your actual Google AI API key
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

# This global variable will hold the current grid status
GRID_IS_STRESSED = False

# In-memory "databases" for the hackathon
CHARGE_REQUEST_QUEUE = []
USER_VCS = {} 

# --- CORS Middleware ---
# Allows the dashboard to communicate with this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Data Models (Pydantic) ---

class UserNegotiateRequest(BaseModel):
    user_did: str
    text: str
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
    pickup_time: str | None = None

# --- HTML Dashboard Endpoint ---

@app.get("/", response_class=HTMLResponse, summary="Serves the main HTML dashboard")
async def get_dashboard():
    """
    Reads and returns the `dashboard.html` file from the same directory.
    """
    try:
        with open("dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: dashboard.html not found.</h1>", status_code=404)

# --- Denso VC Helper Functions ---
# These functions are for internal use by the orchestrator to manage VCs

async def issue_new_vc(user_did: str, soc: int) -> dict | None:
    """
    Issues a brand new Verifiable Credential for a user via the Denso API.
    """
    print(f"[VC Logic] Issuing a new VC for {user_did} with SoC {soc}%...")
    
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
            USER_VCS[user_did] = new_vc
            return new_vc
    except Exception as e:
        print(f"[VC Logic] ✗ ERROR issuing new VC: {e}")
        return None

async def update_vc(user_did: str, existing_vc: dict, soc: int) -> dict | None:
    """
    Updates an existing Verifiable Credential.
    """
    print(f"[VC Logic] Attempting to update VC for {user_did}...")
    
    # In a real scenario, you would modify specific fields.
    # For the demo, we'll just re-issue a new one as the update logic is complex.
    print("[VC Logic] Update endpoint not available, issuing a new VC as a fallback.")
    return await issue_new_vc(user_did, soc)

# --- Core API Endpoints ---

@app.post("/api/grid/stress", summary="Manually set the grid status to STRESSED")
async def stress_grid():
    global GRID_IS_STRESSED
    GRID_IS_STRESSED = True
    print("\n[Grid Control] Grid status manually set to STRESSED.\n")
    return {"status": "Grid is now STRESSED"}

@app.post("/api/grid/stabilize", summary="Manually set the grid status to STABLE")
async def stabilize_grid():
    global GRID_IS_STRESSED
    GRID_IS_STRESSED = False
    print("\n[Grid Control] Grid status manually set to STABLE.\n")
    return {"status": "Grid is now STABLE"}

@app.post("/api/negotiate", summary="Handles all incoming user charging requests")
async def handle_negotiation(request: UserNegotiateRequest):
    """
    This is the main entry point ("The Mouth"). This corrected version ensures
    the start_soc is correctly parsed and passed to the GenAI model.
    """
    print(f"\n--- New Request Received ---")
    print(f"User: {request.user_did}")
    print(f"Text: '{request.text}'")

    # --- Corrected SoC Parsing ---
    start_soc = 50  # Default SoC
    # A more robust way to find the SoC percentage in the text
    text_parts = request.text.replace('%', ' ').split()
    for i, part in enumerate(text_parts):
        if part.isdigit() and i > 0:
            # Check if the previous word indicates it's a percentage
            if text_parts[i-1].lower() in ["at", "is", "is at"]:
                start_soc = int(part)
                break
    
    print(f"[Context] Parsed Starting SoC: {start_soc}%")

    # --- VC Management Logic ---
    # This part is working correctly.
    user_vc = USER_VCS.get(request.user_did)
    if user_vc:
        await update_vc(request.user_did, user_vc, start_soc)
    else:
        await issue_new_vc(request.user_did, start_soc)
    
    # --- Contextual Enrichment ---
    global GRID_IS_STRESSED
    grid_status_text = 'stressed' if GRID_IS_STRESSED else 'stable'
    print(f"[Context] Grid Status: {grid_status_text.upper()}")

    # --- GenAI Decision Making (Corrected) ---
    try:
        # Add a timestamp to the prompt to ensure it's always unique
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        enriched_prompt = (
            f"As of {current_time}, a user with {start_soc}% battery says: '{request.text}'. "
            f"The power grid is currently {grid_status_text}."
        )
        print(f"[GenAI] Sending unique, enriched prompt...")
        
        genai_json = await get_intent_from_genai(enriched_prompt)
        
        genai_json.update({
            "user_did": request.user_did,
            "original_text": request.text,
            "received_at": time.time(),
            "start_soc": start_soc # Ensure this is passed correctly
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
    """This is "The Brain." It adds a structured request to the master queue."""
    print(f"[Brain] Adding to queue: {request.user_did} (Priority: {request.priority})")
    
    global CHARGE_REQUEST_QUEUE
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    CHARGE_REQUEST_QUEUE.append(request)
    
    return {"status": "request_added_to_queue", "user_did": request.user_did}

@app.get("/api/status", summary="Provides the current status of the charging queue and grid")
async def get_status():
    """This is for "The Dashboard." It returns the queue and grid status."""
    global GRID_IS_STRESSED
    priority_map = {"high": 3, "medium": 2, "low": 1}
    sorted_queue = sorted(
        CHARGE_REQUEST_QUEUE,
        key=lambda r: priority_map.get(r.priority, 0),
        reverse=True
    )
    return {
        "charger_count": 4,
        "chargers_in_use": len(sorted_queue),
        "is_grid_stressed": GRID_IS_STRESSED,
        "priority_queue": [r.model_dump() for r in sorted_queue]
    }

# --- Gemini API Helper Function ---

async def get_intent_from_genai(user_text: str) -> dict:
    """
    Uses GenAI to determine charging strategy. This version has a highly-tuned
    prompt to ensure all fields are extracted correctly.
    """
    # This is the final, most important part of the project.
    # The system_prompt is the "brain" of the AI.
    system_prompt = """You are a master EV Charging Concierge. Your sole job is to analyze a user's request and the current power grid status, then create a perfect charging plan. You must fill in all fields of the JSON output.

**Analysis Checklist:**

1.  **Extract Priority**:
    *   `high`: Is the user in a `panic`? Do they have a `meeting` or `appointment`? Are they using words like `ASAP` or `urgent`?
    *   `medium`: Does the user mention a specific future time like `by 6 PM` or `this evening`?
    *   `low`: Is the user flexible? Do they say `no rush`, `all day`, or `overnight`?

2.  **Extract Leave By Time**:
    *   Look for any time mentioned (e.g., "3 PM", "evening").
    *   Convert it to a 24-hour `HH:MM` format. "evening" is `18:00`.
    *   If no time is mentioned, you MUST use `null`.

3.  **Extract Minimum SoC**:
    *   Look for a target battery percentage (e.g., "at least 70%", "full charge").
    *   `full charge` means `100`.
    *   If no target SoC is mentioned, you MUST use `null`.

4.  **Determine Charging Plan & Points (Grid Logic)**:
    *   If grid is **STABLE**: Always `fast_charge`, `10` points.
    *   If grid is **STRESSED**:
        *   If priority is `high`, it MUST be `fast_charge`, `0` points.
        *   If priority is `medium` or `low`, it MUST be `eco_charge`, `100` points.

5.  **Estimate Pickup Time**:
    *   `fast_charge` takes about **45 minutes**.
    *   `eco_charge` takes about **3 hours**.
    *   Provide a user-friendly estimate like `"in about 45 mins"` or `"around 5:30 PM"`.

**CRITICAL OUTPUT FORMAT:**
You MUST return only a single, valid JSON object. All keys must be present. Use `null` if a value is not available.

**Examples to Learn From:**

*   **Input**: "A user with 20% battery says: 'I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70%!'. The power grid is currently stressed."
    *   **Output**: `{"priority": "high", "leave_by": "15:00", "min_soc": 70, "charging_option": "fast_charge", "points_awarded": 0, "pickup_time": "in about 45 mins"}`

*   **Input**: "A user with 85% battery says: 'Hey, I'm just plugging in. I'll be here all day, no rush at all.'. The power grid is currently stressed."
    *   **Output**: `{"priority": "low", "leave_by": null, "min_soc": null, "charging_option": "eco_charge", "points_awarded": 100, "pickup_time": "in about 3 hours"}`

*   **Input**: "A user with 40% battery says: 'Hi, it's my first time here! My car is at 40% and I need to leave by the evening.'. The power grid is currently stable."
    *   **Output**: `{"priority": "medium", "leave_by": "18:00", "min_soc": null, "charging_option": "fast_charge", "points_awarded": 10, "pickup_time": "in about 45 mins"}`

*   **Input**: "A user with 70% battery says: 'Just need a top-up'. The power grid is currently stable."
    *   **Output**: `{"priority": "low", "leave_by": null, "min_soc": null, "charging_option": "fast_charge", "points_awarded": 10, "pickup_time": "in about 45 mins"}`
"""
 
    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\nAnalyze this request:\n{user_text}",
            config=GenerateContentConfig(
                temperature=0.0, # Zero temperature for maximum consistency
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string"},
                        "leave_by": {"type": ["string", "null"]},
                        "min_soc": {"type": ["integer", "null"]},
                        "charging_option": {"type": "string"},
                        "points_awarded": {"type": "integer"},
                        "pickup_time": {"type": "string"}
                    },
                    "required": ["priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]
                }
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI] ✗ ERROR during GenAI call: {e}. Using fallback.")
        return {
            "priority": "medium", 
            "leave_by": "18:00", # Fallback with data
            "min_soc": 80,
            "charging_option": "fast_charge", 
            "points_awarded": 10,
            "pickup_time": "in about 45 mins"
        }

# --- Main Execution Guard ---
if __name__ == "__main__":
    print("Starting ChargeFlex AI Orchestrator on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
