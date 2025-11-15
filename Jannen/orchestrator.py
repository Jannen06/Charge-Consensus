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
from datetime import datetime, timedelta

from google import genai
from google.genai.types import GenerateContentConfig, Schema, Type

# --- Main Application Setup ---
app = FastAPI(
    title="Charge Consensus AI Orchestrator",
    description="An intelligent EV charging orchestrator using GenAI, Verifiable Credentials, and dynamic learning.",
    version="2.0.0"
)

# --- Configuration & Global State ---
DENSO_API_HOST = "https://hackathon1.didgateway.eu"
# IMPORTANT: Replace with your actual Google AI API key
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

GRID_IS_STRESSED = False
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
    is_grid_stressed_at_request: bool = False # To store context for learning

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
    print(f"[VC Logic] Issuing a new VC for {user_did}...")
    credential_subject = { "id": user_did, "envelope_id": str(uuid.uuid4()), "envelope_version": "1.0.0", "schema_uri": "urn:cloudcharger:schemas:ocpi-session-envelope:1", "object_type": "ocpi_session", "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session_id": str(uuid.uuid4()), "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "claims": {"soc_percent": soc} }
    url, params, headers, payload = f"{DENSO_API_HOST}/boy/api/issue-credential", {"credential_type": "ChargingSessionEnvelope"}, {"Content-Type": "application/json"}, {"credentialSubject": credential_subject}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            new_vc = response.json()
            print(f"[VC Logic] ✓ New VC issued for {user_did}.")
            USER_VCS[user_did] = new_vc
            return new_vc
    except Exception as e:
        print(f"[VC Logic] ✗ ERROR issuing new VC: {e}")
        return None

async def update_vc(user_did: str, existing_vc: dict, soc: int) -> dict | None:
    print(f"[VC Logic] Re-issuing VC for {user_did} to update SoC...")
    return await issue_new_vc(user_did, soc)

# --- Core API Endpoints ---

@app.post("/api/grid/stress", summary="Manually set the grid status to STRESSED")
async def stress_grid():
    global GRID_IS_STRESSED
    GRID_IS_STRESSED = True
    return {"status": "Grid is now STRESSED"}

@app.post("/api/grid/stabilize", summary="Manually set the grid status to STABLE")
async def stabilize_grid():
    global GRID_IS_STRESSED
    GRID_IS_STRESSED = False
    return {"status": "Grid is now STABLE"}

@app.post("/api/negotiate", summary="Handles all incoming user charging requests")
async def handle_negotiation(request: UserNegotiateRequest):
    print(f"\n--- New Request Received ---")
    start_soc = 50
    if '%' in request.text:
        try:
            soc_str = request.text.split('%')[0].strip().split()[-1]
            start_soc = int(soc_str)
        except (ValueError, IndexError): pass
    print(f"[Context] User: {request.user_did}, Parsed SoC: {start_soc}%")
    user_vc = USER_VCS.get(request.user_did)
    if user_vc: await update_vc(request.user_did, user_vc, start_soc)
    else: await issue_new_vc(request.user_did, start_soc)
    global GRID_IS_STRESSED, CHARGE_REQUEST_QUEUE
    grid_status_text = 'stressed' if GRID_IS_STRESSED else 'stable'
    print(f"[Context] Grid Status: {grid_status_text.upper()}")
    recent_examples = [r.model_dump() for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did][-3:]
    if recent_examples: print(f"[GenAI] Providing {len(recent_examples)} recent requests as learning examples.")
    try:
        enriched_prompt = f"A user with {start_soc}% battery says: '{request.text}'."
        genai_json = await get_intent_from_genai(enriched_prompt, grid_status_text, recent_examples)
        genai_json.update({"user_did": request.user_did, "original_text": request.text, "received_at": time.time(), "start_soc": start_soc, "is_grid_stressed_at_request": GRID_IS_STRESSED})
        print(f"[GenAI] ✓ Decision received: {genai_json}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GenAI call failed: {e}")
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8001/api/charge_request", json=genai_json)
        print(f"[Orchestrator] ✓ Request sent to internal queue.")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Failed to forward request to internal queue.")
    return {"status": "request_received_and_processing", "intent": genai_json}

@app.post("/api/charge_request", summary="Adds a request to the internal charging queue")
async def add_charge_request(request: InternalChargeRequest):
    print(f"[Brain] Adding to queue: {request.user_did} (Priority: {request.priority})")
    global CHARGE_REQUEST_QUEUE
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    CHARGE_REQUEST_QUEUE.append(request)
    return {"status": "request_added_to_queue"}

@app.get("/api/status", summary="Provides the current status of the charging queue and grid")
async def get_status():
    global GRID_IS_STRESSED, CHARGE_REQUEST_QUEUE
    priority_map = {"high": 3, "medium": 2, "low": 1}
    sorted_queue = sorted(CHARGE_REQUEST_QUEUE, key=lambda r: priority_map.get(r.priority, 0), reverse=True)
    return {"charger_count": 4, "chargers_in_use": len(sorted_queue), "is_grid_stressed": GRID_IS_STRESSED, "priority_queue": [r.model_dump() for r in sorted_queue]}

# --- Gemini API Helper Function (with Dynamic Few-Shot Learning) ---

async def get_intent_from_genai(user_text: str, grid_status: str, recent_requests: list) -> dict:
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    dynamic_examples = ""
    if recent_requests:
        dynamic_examples += "\n**Learn from these RECENT examples that just happened:**\n"
        for req in recent_requests:
            example_grid_status = 'stressed' if req.get('is_grid_stressed_at_request') else 'stable'
            example_prompt = f"A user with {req['start_soc']}% battery says: '{req['original_text']}'. The power grid is currently {example_grid_status}."
            example_output = {k: req[k] for k in ["priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]}
            dynamic_examples += f"\n*   **Input**: \"{example_prompt}\"\n    *   **Output**: `{json.dumps(example_output)}`"
    
    system_prompt = f"""You are a master EV Charging Concierge. Your sole job is to analyze a user's request, the power grid status, and the current time ({current_time_str}) to create a perfect charging plan.

**Analysis Checklist:**
1.  **Extract Priority**: `high` (urgent), `medium` (deadline), `low` (flexible).
2.  **Extract Leave By Time**: Convert to `HH:MM`. Use `null` if not mentioned.
3.  **Extract Minimum SoC**: Extract target %. `full` is `100`. Use `null` if not mentioned.
4.  **Grid-Aware Gamification**: If grid is {grid_status.upper()}: `fast_charge` (10 pts). If STRESSED: `high` -> `fast_charge` (0 pts); `medium`/`low` -> `eco_charge` (100 pts).
5.  **Calculate Pickup Time**: The current time is **{current_time_str}**. `fast_charge` is 45 mins, `eco_charge` is 3 hours. Calculate the final `HH:MM` time.
{dynamic_examples}

**CRITICAL OUTPUT FORMAT:**
Return only a single, valid JSON object. All keys must be present. Use `null` if a value is not available.
"""
 
    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\n**New Request to Analyze:**\n{user_text} The power grid is currently {grid_status}.",
            config=GenerateContentConfig(
                temperature=0.0, response_mime_type="application/json",
                response_schema=Schema(
                    type=Type.OBJECT,
                    properties={
                        'priority': Schema(type=Type.STRING), 'leave_by': Schema(type=Type.STRING, nullable=True), 'min_soc': Schema(type=Type.INTEGER, nullable=True),
                        'charging_option': Schema(type=Type.STRING), 'points_awarded': Schema(type=Type.INTEGER), 'pickup_time': Schema(type=Type.STRING),
                    },
                    required=["priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]
                )
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI] ✗ ERROR during GenAI call: {e}. Using fallback.")
        pickup_fallback = (now + timedelta(minutes=45)).strftime("%H:%M")
        return {"priority": "medium", "leave_by": "18:00", "min_soc": 80, "charging_option": "fast_charge", "points_awarded": 10, "pickup_time": pickup_fallback}

# --- Main Execution Guard ---
if __name__ == "__main__":
    print("Starting Charge Consensus AI Orchestrator v2.0 on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
