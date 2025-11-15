
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from heapq import heappush, heappop
from typing import List, Dict, Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Top constants
DENSO_API_HOST = os.getenv("DENSO_API_HOST", "https://hackathon.dndappsdev.net")
DENSO_API_TOKEN = os.getenv("DENSO_API_TOKEN")

# Pydantic models
class NegotiateRequest(BaseModel):
    user_did: str
    text: str
    presentation: dict

class NegotiateResponse(BaseModel):
    status: str
    queued_id: Optional[str] = None
    priority: Optional[str] = None

class DashboardItem(BaseModel):
    user_did: str
    soc: int
    text: str
    intent: str
    priority: str
    recommendation: str
    timestamp: str

# In-memory priority queue
priority_queue = []
queue_counter = 0

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS middleware
origins = os.getenv("ORIGINS", "http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def verify_denso_presentation(presentation: dict) -> dict:
    if "vc" not in presentation and "credentials" not in presentation:
        return {"verified": False}

    # TODO: Replace with actual Denso token usage
    if DENSO_API_TOKEN:
        headers = {"Authorization": f"Bearer {DENSO_API_TOKEN}"}
        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{DENSO_API_HOST}/api/verify-presentation",
                        json=presentation,
                        headers=headers,
                        timeout=5.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("verified"):
                        if "soc" not in data or not (0 <= int(data["soc"]) <= 100):
                            raise ValueError("Invalid 'soc' value")
                        data["soc"] = int(data["soc"])
                        return data
            except (httpx.RequestError, ValueError) as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        return {"verified": False}
    else:
        # Simulated verification
        return {"verified": True, "soc": 40}

async def get_intent_from_genai(user_text: str, soc: int) -> dict:
    # TODO: Replace with a real GenAI call
    user_text_lower = user_text.lower()
    if soc < 25 or "panic" in user_text_lower:
        return {
            "priority": "high",
            "intent": "urgent_charge",
            "recommendation": "reserve nearest charger and prioritize output",
        }
    elif soc < 50:
        return {"priority": "medium", "intent": "charge_soon", "recommendation": ""}
    else:
        return {"priority": "low", "intent": "no_urgent_action", "recommendation": ""}

@app.post("/api/negotiate", response_model=NegotiateResponse)
async def negotiate(request: NegotiateRequest):
    if not request.user_did.startswith("did:"):
        raise HTTPException(status_code=400, detail="Invalid DID format")

    verification = await verify_denso_presentation(request.presentation)
    if not verification.get("verified"):
        raise HTTPException(status_code=400, detail="Presentation verification failed")

    logger.info(json.dumps({"event": "verification", "user_did": request.user_did, "status": "verified"}))

    soc = verification.get("soc")
    if soc is None or not (0 <= soc <= 100):
        raise HTTPException(status_code=400, detail="Invalid or missing 'soc' in verification response")

    intent_data = await get_intent_from_genai(request.text, soc)
    
    global queue_counter
    queued_id = f"{int(time.time())}-{queue_counter}"
    queue_counter += 1

    priority_map = {"high": 1, "medium": 2, "low": 3}
    priority_numeric = priority_map.get(intent_data["priority"], 3)

    dashboard_item = DashboardItem(
        user_did=request.user_did,
        soc=soc,
        text=request.text,
        intent=intent_data["intent"],
        priority=intent_data["priority"],
        recommendation=intent_data["recommendation"],
        timestamp=datetime.utcnow().isoformat(),
    )

    heappush(priority_queue, (priority_numeric, queued_id, dashboard_item.model_dump()))
    
    log_message = {
        "event": "queue_add",
        "user_did": request.user_did,
        "priority": intent_data["priority"],
        "queued_id": queued_id,
    }
    logger.info(json.dumps(log_message))

    return NegotiateResponse(
        status="queued",
        queued_id=queued_id,
        priority=intent_data["priority"],
    )

@app.get("/dashboard-data", response_model=List[DashboardItem])
async def dashboard_data():
    sorted_items = sorted(priority_queue)
    return [DashboardItem(**item[2]) for item in sorted_items]

@app.get("/")
async def read_root():
    if os.path.exists("dashboard.html"):
        return FileResponse("dashboard.html")
    else:
        return {"message": "Dashboard not found. Place dashboard.html in project root."}

if __name__ == "__main__":
    uvicorn.run("orchestrator_server:app", host="0.0.0.0", port=8000, log_level="info")
