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

from google import genai
from google.genai.types import GenerateContentConfig
from google import genai
from google.genai.types import GenerateContentConfig, Schema
import json

app = FastAPI()

# Initialize the client at the top of your file (with other initializations)
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

# Add CORS middleware to allow your dashboard to connect
origins = [
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "null", # For file:// origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    # --- SIMULATED SUCCESS ---
    soc = None
    try:
        # This simulates parsing the VC *after* it's been verified
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
        
        # Add all metadata for the internal request
        genai_json["user_did"] = request.user_did
        genai_json["original_text"] = request.text
        genai_json["received_at"] = time.time()
        genai_json["start_soc"] = start_soc
        
        print(f"[Negotiate] GenAI Response: {genai_json}")

    except Exception as e:
        print(f"[Negotiate] ERROR calling GenAI: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"GenAI call failed: {e}")

    # 3. Forward this structured request to our "Brain"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8001/api/charge_request",
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
    # Remove any old request from this user
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != request.user_did]
    # Add the new request
    CHARGE_REQUEST_QUEUE.append(request)
    
    return {"status": "request_added_to_queue", "user_did": request.user_did}

# --- The "Gamification": Nudge Endpoint ---

@app.post("/api/nudge/{user_did}")
async def nudge_user(user_did: str):
    """
    This is the "Gamification" feature.
    An admin clicks a button on the dashboard to "nudge" a user.
    """
    print(f"[Nudge] Admin sent a nudge to {user_did}")
    
    # For the demo, we just log it and remove them from the queue
    global CHARGE_REQUEST_QUEUE
    CHARGE_REQUEST_QUEUE = [r for r in CHARGE_REQUEST_QUEUE if r.user_did != user_did]
    
    print(f"[Nudge] {user_did} has been removed from the queue.")
    return {"status": "nudge_sent", "user_did": user_did, "points_awarded": 50}

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
    
    queue_as_dicts = [r.model_dump() for r in sorted_queue]
    
    return {
        "charger_count": 4,
        "chargers_in_use": len(queue_as_dicts),
        "priority_queue": queue_as_dicts
    }

# --- Gemini API Helper Function ---
async def get_intent_from_genai(user_text: str) -> dict:
    """
    Uses Google GenAI SDK with structured JSON output for reliable parsing.
    """
    system_prompt = """You are an EV charging priority classifier. Extract structured data from user requests.

PRIORITY CLASSIFICATION:
HIGH - Urgent situations requiring immediate attention:
  • Keywords: panic, urgent, emergency, ASAP, hurry, rush, crucial, critical
  • Events: meeting, appointment, client, interview, flight, deadline
  • Time pressure: "need to leave soon", "running late", "in 30 minutes"
  • Emphasis: ALL CAPS, multiple exclamation marks!!!

MEDIUM - Standard requests with time constraints:
  • Specific future times: "by 5 PM", "need it this evening", "before dinner"
  • Moderate urgency: "would like to", "hoping to get", "need it by"
  • Planning ahead: "have plans later", "going out tonight"

LOW - Flexible, non-urgent charging:
  • Keywords: no rush, no hurry, whenever, flexible, leisurely
  • Extended time: "all day", "all night", "here until tomorrow", "overnight"
  • Casual tone: "just topping up", "might as well", "while I'm here"

TIME EXTRACTION (24-hour format):
  • "3 PM" / "3:00 PM" → "15:00"
  • "noon" / "12 PM" → "12:00"
  • "evening" → "18:00"
  • "morning" → "08:00"
  • "midnight" → "00:00"
  • No time mentioned → null

STATE OF CHARGE (SOC) EXTRACTION:
  • "70%" / "70 percent" / "at least 70" → 70
  • "full charge" / "100%" / "fully charged" → 100
  • "80" / "eighty percent" → 80
  • "half" / "50%" → 50
  • No target mentioned → null

CONTEXT AWARENESS:
  • If current SoC is very low (<25%) and user says "full charge", treat as HIGH priority
  • If current SoC is high (>75%) and no urgency mentioned, default to LOW
  • Time + low battery = HIGH priority automatically

EXAMPLES:
Input: "User is at 85% SoC. User says: 'Just plugging in, here all day, no rush'"
Output: {"priority": "low", "leave_by": null, "min_soc": null}

Input: "User is at 20% SoC. User says: 'URGENT! Client meeting at 3 PM and I need at least 70%!'"
Output: {"priority": "high", "leave_by": "15:00", "min_soc": 70}

Input: "User is at 45% SoC. User says: 'Need it by evening, around 80% would be good'"
Output: {"priority": "medium", "leave_by": "18:00", "min_soc": 80}

Input: "User is at 15% SoC. User says: 'Need a full charge for my road trip'"
Output: {"priority": "high", "leave_by": null, "min_soc": 100}"""
 
    try:
        # Use structured output with JSON schema for reliable parsing
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\nNow analyze:\n{user_text}",
            config=GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"]
                        },
                        "leave_by": {
                            "type": ["string", "null"],
                            "description": "Time in 24-hour format (HH:MM) or null"
                        },
                        "min_soc": {
                            "type": ["integer", "null"],
                            "description": "Minimum state of charge percentage or null"
                        }
                    },
                    "required": ["priority"]
                }
            ),
        )
        
        text = response.text.strip()
        print(f"[GenAI] Raw response: {text}")
        
        # Parse the JSON response
        parsed = json.loads(text)
        
        # Validate and clean the response
        priority = parsed.get("priority", "medium").lower()
        if priority not in ["low", "medium", "high"]:
            priority = "medium"
        
        return {
            "priority": priority,
            "leave_by": parsed.get("leave_by"),
            "min_soc": parsed.get("min_soc")
        }
        
    except Exception as e:
        print(f"[GenAI] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Smart fallback based on keywords
        text_lower = user_text.lower()
        if any(word in text_lower for word in ["panic", "urgent", "emergency", "asap", "meeting"]):
            return {"priority": "high", "leave_by": None, "min_soc": None}
        elif any(word in text_lower for word in ["no rush", "all day", "tomorrow"]):
            return {"priority": "low", "leave_by": None, "min_soc": None}
        return {"priority": "medium", "leave_by": None, "min_soc": None}
    


    
if __name__ == "__main__":
    print("Starting ChargeFlex AI Orchestrator on http://0.0.0.0:8001")
    print("View dashboard at http://127.0.0.1:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
