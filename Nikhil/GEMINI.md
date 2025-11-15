You will output exactly one file. Title it with the file marker:

===== orchestrator_server.py =====

Create a **single-file FastAPI application** named `orchestrator_server.py` that implements the ChargeFlex AI "Brain" with the following strict requirements.

Requirements:
- Use Python 3.10+ idioms (async/await).
- Use only these imports: fastapi, uvicorn, pydantic, httpx, typing, heapq, time, os, logging, fastapi.responses.FileResponse, fastapi.middleware.cors.CORSMiddleware, datetime, json.
- Top constants:
  - DENSO_API_HOST = os.getenv("DENSO_API_HOST", "https://hackathon.dndappsdev.net")
  - DENSO_API_TOKEN = os.getenv("DENSO_API_TOKEN")  # must not be hard-coded
- Pydantic models:
  - NegotiateRequest: user_did: str, text: str, presentation: dict
  - NegotiateResponse: status: str, queued_id: str | None, priority: str | None
  - DashboardItem: user_did, soc (int), text, intent, priority, recommendation, timestamp
- Implement async def verify_denso_presentation(presentation: dict) -> dict:
  - Validate presentation shape (must contain "vc" or "credentials" keys or return {"verified": False})
  - If DENSO_API_TOKEN is set: simulate an httpx.post to f"{DENSO_API_HOST}/api/verify-presentation" with Authorization Bearer header and exponential backoff (3 retries). Parse JSON; if response.get("verified") truthy, return it.
  - If DENSO_API_TOKEN not set: return simulated {"verified": True, "soc": 40}
  - Always ensure soc is int 0..100. Raise ValueError for invalid soc.
- Implement async def get_intent_from_genai(user_text: str, soc: int) -> dict:
  - Do not call external GenAI. Implement deterministic rule-based logic:
    - If soc < 25 or "panic" in lower(user_text) => priority "high", intent "urgent_charge", recommendation "reserve nearest charger and prioritize output"
    - Else if soc < 50 => priority "medium", intent "charge_soon"
    - Else => priority "low", intent "no_urgent_action"
  - Return dict: {"intent": ..., "priority": ..., "recommendation": ...}
- Implement an in-memory priority queue using heapq. Priority order: high=1, medium=2, low=3. Each queued item stores a unique queued_id (timestamp + counter), DashboardItem payload, and numeric priority.
- Endpoints:
  - POST /api/negotiate
    - Accepts NegotiateRequest
    - Calls verify_denso_presentation() first; if not verified, return 400 with JSON reason.
    - Extract soc from verify result and validate.
    - Call get_intent_from_genai(user_text, soc)
    - Create DashboardItem, push to priority queue, log: "[Verify] Presentation for {user_did} verified." and "[Brain] Adding to queue: {user_did} (Priority: {priority})"
    - Return NegotiateResponse with queued_id and priority.
  - GET /dashboard-data
    - Returns JSON list of DashboardItem objects sorted by numeric priority then timestamp.
  - GET /
    - Serves dashboard.html from the same directory (use FileResponse). If missing, return a simple HTML with "Dashboard not found. Place dashboard.html in project root."
- Logging:
  - Use Python logging; format messages in JSON-like structure and do NOT log DENSO_API_TOKEN or full presentation contents.
- Security & validation:
  - Validate DID format starts with "did:"; otherwise raise HTTPException(400).
  - Validate soc range 0..100.
  - All external httpx calls must have a 5 second timeout.
  - Use CORS middleware allowing only origin "http://localhost:8000" by default (read origin from env ORIGINS if provided).
- Run guard:
  - if __name__ == "__main__": run uvicorn programmatically on host "0.0.0.0", port 8000, log_level="info".
- Add clear TODO comments where Denso token usage and GenAI replacement should be implemented in future.

No extra text outside the file marker. The content must be a complete, runnable Python file.
