from dotenv import load_dotenv
load_dotenv()

import os
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
GEMINI_API_KEY_VALUE = os.environ.get('GEMINI_API_KEY')
genai_client = genai.Client(api_key=GEMINI_API_KEY_VALUE)
if not GEMINI_API_KEY_VALUE:
    print("[ERROR] GEMINI_API_KEY not loaded. Please check your .env file or environment variables.")
else:
    print("[INFO] GEMINI_API_KEY successfully loaded.")

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

# --- API Data Models ---
class UserNegotiateRequest(BaseModel):
    user_did: str
    text: str

class InternalChargeRequest(BaseModel):
    user_did: str; priority: str; leave_by: str | None = None; min_soc: int | None = None
    start_soc: int | None = None; original_text: str; received_at: float
    charging_option: str | None = None; points_awarded: int = 0
    pickup_time: str | None = None; is_grid_stressed_at_request: bool = False

# --- HTML Dashboard Endpoint ---
@app.get("/", response_class=HTMLResponse, summary="Serves the main HTML dashboard")
async def get_dashboard():
    try:
        with open("dashboard.html", "r") as f: return HTMLResponse(content=f.read())
    except FileNotFoundError: return HTMLResponse(content="<h1>Error: dashboard.html not found.</h1>", status_code=404)

# --- Denso VC Helper Functions (Simulated for speed) ---
async def issue_or_update_vc(user_did: str, soc: int):
    if user_did in USER_VCS: print(f"[VC Logic] Updating VC for {user_did}...")
    else: print(f"[VC Logic] Issuing new VC for {user_did}...")
    USER_VCS[user_did] = {"id": f"urn:uuid:{uuid.uuid4()}", "credentialSubject": {"id": user_did, "claims": {"soc_percent": soc}}}
    await asyncio.sleep(0.1)
    print(f"[VC Logic] ✓ VC processed for {user_did}.")

# --- Core API Endpoints ---
@app.post("/api/grid/stress", summary="Manually set the grid status to STRESSED")
async def stress_grid():
    global GRID_IS_STRESSED; GRID_IS_STRESSED = True
    return {"status": "Grid is now STRESSED"}

@app.post("/api/grid/stabilize", summary="Manually set the grid status to STABLE")
async def stabilize_grid():
    global GRID_IS_STRESSED; GRID_IS_STRESSED = False
    return {"status": "Grid is now STABLE"}

@app.post("/api/negotiate", summary="Handles all incoming user charging requests")
async def handle_negotiation(request: UserNegotiateRequest):
    print(f"\n--- New Request Received ---")
    print(f"User: {request.user_did}")
    print(f"Text: '{request.text}'")

    start_soc_guess = 50
    text_lower = request.text.lower()
    if "dead" in text_lower or "empty" in text_lower:
        start_soc_guess = 5
    elif '%' in request.text:
        try:
            soc_str = text_lower.split('%')[0].strip().split()[-1]
            start_soc_guess = int(soc_str)
        except (ValueError, IndexError): pass
    print(f"[Context] Initial SoC guess: {start_soc_guess}%")
    
    # --- BUG FIX 1: Call the VC functions ---
    user_vc = USER_VCS.get(request.user_did)
    if user_vc:
        await issue_or_update_vc(request.user_did, start_soc_guess)
    else:
        await issue_or_update_vc(request.user_did, start_soc_guess)

    try:
        global GRID_IS_STRESSED, CHARGE_REQUEST_QUEUE
        grid_status_text = 'stressed' if GRID_IS_STRESSED else 'stable'
        recent_examples = [r.model_dump() for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did][-2:]
        
        enriched_prompt = f"A user with approximately {start_soc_guess}% battery says: '{request.text}'."
        print(f"[GenAI] Sending enriched prompt...")
        genai_json = await get_intent_from_genai(enriched_prompt, grid_status_text, recent_examples)
        
        final_start_soc = genai_json.get("start_soc") if genai_json.get("start_soc") is not None else start_soc_guess
        
        # Sanity check/finetuning for min_soc: if not provided, default to 80
        if genai_json.get("min_soc") is None:
            genai_json["min_soc"] = 80

        genai_json.update({
            "user_did": request.user_did,
            "original_text": request.text,
            "received_at": time.time(),
            "start_soc": final_start_soc,
            "is_grid_stressed_at_request": GRID_IS_STRESSED
        })
        print(f"[GenAI] ✓ Final Validated Plan: {genai_json}")
    except Exception as e:
        print(f"[ERROR] GenAI call failed in handle_negotiation: {e}")
        raise HTTPException(status_code=500, detail=f"GenAI call failed: {e}")
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8080/api/charge_request", json=genai_json)
        print(f"[Orchestrator] ✓ Request sent to internal queue.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to forward request: {e}")
        
    return {"status": "request_received_and_processing", "intent": genai_json}

@app.post("/api/charge_request", summary="Adds a request to the internal charging queue")
async def add_charge_request(request: InternalChargeRequest):
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

# --- Gemini API Helper Function ---
async def get_intent_from_genai(user_text: str, grid_status: str, recent_requests: list) -> dict:
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")

    # --- Final, Bulletproof Prompt Design ---
    # Instead of complex examples, we integrate the "learning" as a simple memory.
    memory_context = ""
    if recent_requests:
        memory_context += "\n**Short-Term Memory (What just happened):**\n"
        for req in recent_requests:
            memory_context += f"- A user with '{req['priority']}' priority got '{req['charging_option']}' and {req['points_awarded']} points.\n"
    
    system_prompt = f"""You are a hyper-efficient EV Charging Bot. Your only goal is to parse user text and output a perfect JSON charging plan.

**Current Time**: {current_time_str}
**Grid Status**: {grid_status.upper()}

{memory_context}

**Core Rules:**
1.  **Parse SoCs**: Find `start_soc` ('at 5%', 'dead'=5) and `min_soc` ('need 80%'). If not found, use `null`.
2.  **Parse Leave By**: Find `leave_by` time (e.g., 'flight to catch' = +2 hours from current time). If none, use `null`.
3.  **Determine Priority**: `high` (urgent), `medium` (deadline), `low` (flexible).
4.  **Choose Plan (Grid Logic)**:
    *   If grid is **STABLE**: Always `fast_charge` (10 pts).
    *   If grid is **STRESSED**: `high` priority -> `fast_charge` (0 pts); `medium`/`low` -> `eco_charge` (100 pts).
5.  **Calculate Pickup Time**: Start from **{current_time_str}**. `fast_charge` adds 45 mins. `eco_charge` adds 3 hours. Calculate the final `HH:MM` time.
6.  **Reasoning**: Briefly explain your decision.

**Output Format**: For the request below, return a single, valid JSON object. All keys are required.
"""
    
    final_prompt = f"{system_prompt}\n**New Request**: {user_text}"

    try:
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=final_prompt,
            config=GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=Schema(
                    type=Type.OBJECT,
                    properties={
                        'start_soc': Schema(type=Type.INTEGER, nullable=True),
                        'priority': Schema(type=Type.STRING),
                        'leave_by': Schema(type=Type.STRING, nullable=True),
                        'min_soc': Schema(type=Type.INTEGER, nullable=True),
                        'charging_option': Schema(type=Type.STRING),
                        'points_awarded': Schema(type=Type.INTEGER),
                        'pickup_time': Schema(type=Type.STRING),
                        'reasoning': Schema(type=Type.STRING, nullable=True),
                    },
                    required=["start_soc", "priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]
                )
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI] ✗ ERROR during GenAI call: {e}. Using fallback.")
        pickup_fallback = (now + timedelta(minutes=45)).strftime("%H:%M")
        return {"priority": "medium", "leave_by": "18:00", "min_soc": 80, "charging_option": "fast_charge", "points_awarded": 10, "pickup_time": pickup_fallback, "reasoning": "Fallback due to error."}


# --- Main Execution Guard ---
if __name__ == "__main__":
    print("Starting Charge Consensus AI Orchestrator v2.1 on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))
