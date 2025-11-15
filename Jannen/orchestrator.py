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
from google.genai.types import GenerateContentConfig, Schema, Type

from datetime import datetime, timedelta

# --- Main Application Setup ---
app = FastAPI(
    title="Charge Consensus AI Orchestrator",
    description="An intelligent EV charging orchestrator using GenAI and Verifiable Credentials.",
    version="1.1.0"
)

# --- Configuration & Global State ---
DENSO_API_HOST = "https://hackathon1.didgateway.eu"
# IMPORTANT: Replace with your actual Google AI API key
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

# This global variable will hold the current grid status, controllable via API
GRID_IS_STRESSED = False

# In-memory "databases" for the hackathon
CHARGE_REQUEST_QUEUE = []
USER_VCS = {} 

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    try:
        with open("dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: dashboard.html not found.</h1>", status_code=404)

# --- Denso VC Helper Functions ---

async def issue_new_vc(user_did: str, soc: int) -> dict | None:
    print(f"[VC Logic] Issuing a new VC for {user_did} with SoC {soc}%...")
    credential_subject = { "id": user_did, "envelope_id": str(uuid.uuid4()), "envelope_version": "1.0.0", "schema_uri": "urn:cloudcharger:schemas:ocpi-session-envelope:1", "object_type": "ocpi_session", "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session_id": str(uuid.uuid4()), "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "claims": {"soc_percent": soc} }
    url, params, headers, payload = f"{DENSO_API_HOST}/boy/api/issue-credential", {"credential_type": "ChargingSessionEnvelope"}, {"Content-Type": "application/json"}, {"credentialSubject": credential_subject}
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
    print(f"[VC Logic] Update logic: Re-issuing VC for user {user_did}...")
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
    print(f"\n--- New Request Received ---")
    print(f"User: {request.user_did}")
    print(f"Text: '{request.text}'")
    start_soc = 50
    if '%' in request.text:
        try:
            soc_str = request.text.split('%')[0].strip().split()[-1]
            start_soc = int(soc_str)
        except (ValueError, IndexError):
            print("[Warning] Could not parse SoC from text.")
    print(f"[Context] Parsed Starting SoC: {start_soc}%")
    user_vc = USER_VCS.get(request.user_did)
    if user_vc: await update_vc(request.user_did, user_vc, start_soc)
    else: await issue_new_vc(request.user_did, start_soc)
    global GRID_IS_STRESSED
    grid_status_text = 'stressed' if GRID_IS_STRESSED else 'stable'
    print(f"[Context] Grid Status: {grid_status_text.upper()}")
    try:
        enriched_prompt = f"As of {time.strftime('%Y-%m-%d %H:%M:%S')}, a user with {start_soc}% battery says: '{request.text}'. The power grid is currently {grid_status_text}."
        print(f"[GenAI] Sending unique, enriched prompt...")
        genai_json = await get_intent_from_genai(enriched_prompt)
        genai_json.update({"user_did": request.user_did, "original_text": request.text, "received_at": time.time(), "start_soc": start_soc})
        print(f"[GenAI] ✓ Decision received: {genai_json}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GenAI call failed: {e}")
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8001/api/charge_request", json=genai_json)
        print(f"[Orchestrator] ✓ Request for {request.user_did} sent to the internal queue.")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Failed to forward request to the internal queue.")
    return {"status": "request_received_and_processing", "intent": genai_json}

@app.post("/api/charge_request", summary="Adds a request to the internal charging queue")
async def add_charge_request(request: InternalChargeRequest):
    print(f"[Brain] Adding to queue: {request.user_did} (Priority: {request.priority})")
    global CHARGE_REQUEST_QUEUE
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    CHARGE_REQUEST_QUEUE.append(request)
    return {"status": "request_added_to_queue", "user_did": request.user_did}

@app.get("/api/status", summary="Provides the current status of the charging queue and grid")
async def get_status():
    global GRID_IS_STRESSED
    priority_map = {"high": 3, "medium": 2, "low": 1}
    sorted_queue = sorted(CHARGE_REQUEST_QUEUE, key=lambda r: priority_map.get(r.priority, 0), reverse=True)
    return {"charger_count": 4, "chargers_in_use": len(sorted_queue), "is_grid_stressed": GRID_IS_STRESSED, "priority_queue": [r.model_dump() for r in sorted_queue]}

# --- Gemini API Helper Function (Final, Tested Version) ---
async def get_intent_from_genai(user_text: str) -> dict:
    """
    Uses GenAI to make intelligent charging decisions, including a calculated pickup time.
    """
    # Get the current time to pass to the AI
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")

    system_prompt = f"""You are a master EV Charging Concierge. Your sole job is to analyze a user's request, including their starting battery SoC (State of Charge), the power grid status, and the current time ({current_time_str}) to create an optimal, grid-friendly charging plan. Always prioritize grid stability while meeting user needs as closely as possible. Output must be deterministic and logical.

**Key Assumptions**:
- Starting SoC is provided in the request (e.g., 40%). If not parsable, default to 50%.
- Charging rates: fast_charge adds ~1% SoC per minute (max 45 min session). eco_charge adds ~0.3% SoC per minute (max 3 hours session).
- If min_soc not reached in time, cap at what's possible and award 0 points.
- Handle time formats flexibly: 24-hour (15:00), 12-hour (3pm/3 pm), relative (in 2 hours = add to current time), or vague (soon = high priority, +30 min).
- If leave_by conflicts with pickup (e.g., too soon), force fast_charge and adjust.
- Default min_soc: 80% if not specified. Default leave_by: current time +3 hours if flexible/low priority.
- Grid status overrides: If stressed, encourage eco for medium/low; allow fast for high but with 0 points.

**Analysis Steps (Follow Strictly)**:
1. **Extract Priority**: Based on urgency words (e.g., 'urgent/emergency' = high; 'by [time]' = medium; 'whenever/no rush' = low). Default: medium.
2. **Extract Leave By Time**: Parse to HH:MM (24-hour). Convert relatives/AM/PM. If none, infer from priority (high: +45 min; medium: +2 hours; low: +3 hours). Use null only if truly impossible to infer.
3. **Extract Minimum SoC**: Parse target % (e.g., '70%' = 70, 'full' = 100). If range, take minimum. Default: 80 if none.
4. **Determine Charging Option and Points (Grid-Aware Gamification)**:
   - If grid STABLE: Always fast_charge, award 10 points base + 20 if flexible (low priority).
   - If grid STRESSED: high priority = fast_charge (0 points); medium = eco_charge (50 points); low = eco_charge (100 points + 50 bonus if delaying >1 hour).
   - Adjust if min_soc/start_soc delta requires more time: e.g., if >50% needed, prefer eco for grid health unless high priority.
   - For conflicts (e.g., time/SoC impossible), set points to 0.
5. **Calculate Pickup Time**:
   - Compute required time: (min_soc - start_soc) / rate (fast=1%/min, eco=0.3%/min). Cap at max session.
   - Add to current time: Format as HH:MM (24-hour). If over 24:00, wrap to next day but note.
   - Ensure pickup <= leave_by: If not, switch to fast_charge, reduce min_soc if needed, and set points to 0.
   - If no charging needed (start_soc >= min_soc), set pickup to current time +5 min, option='none', points=0.

**CRITICAL OUTPUT FORMAT**:
Return ONLY a single, valid JSON object. All required keys must be present. Use null sparingly—prefer defaults/inferences. Add an optional 'reasoning' string for brief explanation (e.g., "Switched to fast due to time conflict").
"""
 
    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\nAnalyze this request:\n{user_text}",
            config=GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=Schema(
                    type=Type.OBJECT,
                    properties={
                        'priority': Schema(type=Type.STRING),
                        'leave_by': Schema(type=Type.STRING, nullable=True),
                        'min_soc': Schema(type=Type.INTEGER, nullable=True),
                        'charging_option': Schema(type=Type.STRING),
                        'points_awarded': Schema(type=Type.INTEGER),
                        'pickup_time': Schema(type=Type.STRING),
                    },
                    required=["priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]
                )
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI] ✗ ERROR during GenAI call: {e}. Using fallback.")
        # Calculate a simple fallback time
        pickup_fallback = (now + timedelta(minutes=45)).strftime("%H:%M")
        return {
            "priority": "medium", 
            "leave_by": "18:00", 
            "min_soc": 80,
            "charging_option": "fast_charge", 
            "points_awarded": 10,
            "pickup_time": pickup_fallback
        }




# --- Main Execution Guard ---
if __name__ == "__main__":
    print("Starting Charge Consensus AI Orchestrator on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)

