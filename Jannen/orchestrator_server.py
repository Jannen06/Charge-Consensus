from fastapi import FastAPI, Request, HTTPException
from starlette.responses import HTMLResponse # UPDATED: Import from starlette
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware # NEW: Import CORS
import uvicorn
import httpx
from pydantic import BaseModel
import time
import json 
import asyncio 

# --- Configuration ---

app = FastAPI()

# --- NEW: Add CORS Middleware ---
# This tells the browser it's safe for our dashboard (even on a different URL)
# to request data from this server. This prevents "CORS errors".
origins = [
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:8000", # In case you switch back
    "http://localhost:8000",
    "null", # Allows 'file://' origins for local testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
# --- End of NEW section ---


DENSO_API_HOST = "https://hackathon.dndappsdev.net"

# This is your "database" for the hackathon.
CHARGE_REQUEST_QUEUE = []

# --- API Models (for valid data) ---

class UserNegotiateRequest(BaseModel):
    user_did: str
    text: str
    presentation: dict

class InternalChargeRequest(BaseModel):
    user_did: str
    priority: str
    leave_by: str | None = None
    min_soc: int | None = None
    start_soc: int | None = None
    original_text: str
    received_at: float

# --- Add route to serve dashboard.html ---
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open("dashboard.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: dashboard.html not found.</h1>", status_code=404)

# --- Denso API Verification Helper ---

async def verify_denso_presentation(presentation: dict) -> dict:
    """
    Simulates calling the Denso Gateway to verify a Verifiable Presentation.
    """
    print(f"[Verify] Verifying presentation with Denso Gateway...")
    # --- REAL API CALL (when you have a token) ---
    # ... (real call logic) ...
    
    # --- SIMULATED SUCCESS ---
    soc = None
    try:
        for vc in presentation.get("verifiableCredential", []):
            subject = vc.get("credentialSubject", {})
            if subject.get("type") == "VehicleSoC":
                soc = subject.get("soc_percent")
                break
        
        if soc is None:
            print("[Verify] WARN: Could not find 'VehicleSoC' in presentation. Defaulting to None.")
    
    except Exception as e:
        print(f"[Verify] ERROR parsing presentation: {e}")
        raise HTTPException(status_code=400, detail="Could not parse presentation structure")

    print(f"[Verify] Presentation VERIFIED. Extracted SoC: {soc}%")
    return {"verified": True, "soc": soc}


# --- The "Mouth": GenAI NLP Endpoint (UPDATED) ---

@app.post("/api/negotiate")
async def handle_negotiation(request: UserNegotiateRequest):
    """
    This is the "Mouth."
    1. Verifies data with Denso API.
    2. Enriches GenAI prompt.
    3. Forwards to internal "Brain".
    """
    print(f"[Negotiate] Received: {request.text} from {request.user_did}")

    # 1. VERIFY the presentation
    try:
        verification = await verify_denso_presentation(request.presentation)
        start_soc = verification.get("soc")
    except Exception as e:
        print(f"[Negotiate] ERROR verifying presentation: {e}")
        raise HTTPException(status_code=401, detail=f"Presentation verification failed: {e}")

    # 2. Call GenAI with ENRICHED prompt
    try:
        enriched_prompt = f"User is at {start_soc}% SoC. User says: '{request.text}'"
        print(f"[Negotiate] Sending enriched prompt to GenAI: {enriched_prompt}")
        
        genai_json = await get_intent_from_genai(enriched_prompt)
        
        genai_json["user_did"] = request.user_did
        genai_json["original_text"] = request.text
        genai_json["received_at"] = time.time()
        genai_json["start_soc"] = start_soc
        
        print(f"[Negotiate] GenAI Response: {genai_json}")

    except Exception as e:
        print(f"[Negotiate] ERROR calling GenAI: {e}")
        raise HTTPException(status_code=500, detail="GenAI call failed")

    # 3. Forward this structured request to our "Brain"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8001/api/charge_request", # Using port 8001
                json=genai_json,
                timeout=10.0
            )
            response.raise_for_status()
    except httpx.RequestError as e:
        print(f"[Negotiate] ERROR forwarding to /charge_request: {e}")
        raise HTTPException(status_code=500, detail="Failed to forward request to brain")

    return {"status": "request_received_and_processing", "intent": genai_json}


# --- The "Brain": Internal Scheduler Endpoint ---

@app.post("/api/charge_request")
async def add_charge_request(request: InternalChargeRequest):
    """
    This is the "Brain."
    It adds the verified, structured request to the master queue.
    """
    print(f"[Brain] Adding to queue: {request.user_did} (Priority: {request.priority})")
    
    global CHARGE_REQUEST_QUEUE
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    CHARGE_REQUEST_QUEUE.append(request)
    
    return {"status": "request_added_to_queue", "user_did": request.user_did}


# --- The "Dashboard": Status Endpoint ---

@app.get("/api/status")
async def get_status():
    """
    This is the "Dashboard."
    It sorts the queue by priority and returns it.
    """
    priority_map = {"high": 3, "medium": 2, "low": 1}
    
    sorted_queue = sorted(
        CHARGE_REQUEST_QUEUE,
        key=lambda r: priority_map.get(r.priority, 0),
        reverse=True
    )
    
    queue_as_dicts = [r.model_dump() for r in sorted_queue] # Use .model_dump()
    
    return {
        "charger_count": 4,
        "chargers_in_use": len(queue_as_dicts),
        "priority_queue": queue_as_dicts
    }


# --- Gemini API Helper Function ---

async def get_intent_from_genai(user_text: str) -> dict:
    """
    Calls the Gemini API to classify the user's intent.
    """
    apiKey = "" # Canvas provides this
    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={apiKey}"

    system_prompt = """
    You are an EV charging assistant. Your ONLY job is to convert a user's text into a valid JSON object.
    You MUST output ONLY the JSON, with no other text.
    
    The JSON must have 3 keys:
    1. "priority": (string) Must be one of: "low", "medium", or "high".
    2. "leave_by": (string or null) The time the user needs to leave in "HH:MM" 24-hour format, or null if not specified.
    3. "min_soc": (integer or null) The minimum State of Charge (e.g., 70), or null if not specified.

    High priority examples: "in a hurry", "urgent", "client meeting", "need to leave soon", "panic".
    Medium priority examples: "need it by this evening", "sometime after 5".
    Low priority examples: "no rush", "here all day", "just a top-up", "leaving tomorrow".
    
    The user's text may include their current SoC. Use this to inform the "min_soc" if they are vague.
    For example: "User is at 20% SoC. User says: 'I need at least 70%'" -> "min_soc": 70
    For example: "User is at 20% SoC. User says: 'I need a full charge'" -> "min_soc": 100
    """
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "priority": {"type": "STRING"},
                    "leave_by": {"type": "STRING", "nullable": true},
                    "min_soc": {"type": "NUMBER", "nullable": true}
                },
                "required": ["priority", "leave_by", "min_soc"]
            }
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(3): # Retry up to 3 times
            try:
                response = await client.post(apiUrl, json=payload, headers={"Content-Type": "application/json"})
                
                if response.status_code == 429 or response.status_code >= 500:
                    wait_time = 2 ** i
                    print(f"[GenAI] Rate limited. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                result = response.json()
                json_text = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(json_text)

            except httpx.ReadTimeout:
                print(f"[GenAI] Read timeout. Retrying...")
                await asyncio.sleep(2 ** i)
            except Exception as e:
                print(f"[GenAI] ERROR: {e}")
                raise e
        
        raise HTTPException(status_code=500, detail="GenAI service is unavailable or timing out.")


# --- Run the Server ---
if __name__ == "__main__":
    print("Starting ChargeFlex AI Orchestrator on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001) # Use port 8001