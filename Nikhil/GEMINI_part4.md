You will output exactly one file.

===== tests__test_orchestrator_py.py =====

Generate a single pytest file (name the file marker `tests__test_orchestrator_py.py` — you'll save it as tests/test_orchestrator.py) that tests core orchestrator behavior. Use the following constraints.

Requirements:
- Use pytest and pytest-asyncio. Use respx to mock httpx async requests.
- Imports allowed: pytest, pytest_asyncio, httpx, respx, asyncio, json, os, sys, typing, importlib
- The test should:
  1. Import the orchestrator module programmatically (import orchestrator_server).
  2. Test verify_denso_presentation() when DENSO_API_TOKEN is not set:
     - Call orchestrator_server.verify_denso_presentation({"vc":{"type":"VehicleSoC","soc_percent":30}}) and assert returned dict has verified True and soc==30 or default simulation soc.
  3. Test POST /api/negotiate flow using httpx.AsyncClient on the running FastAPI app via orchestrator_server.app.
     - Use AsyncClient(app=orchestrator_server.app, base_url="http://test") to POST negotiate with a simulated presentation and assert status_code == 200 and response JSON includes queued_id and priority.
  4. Test that invalid DID is rejected (POST with user_did "badid" returns 400).
- Use pytest-asyncio fixtures where necessary.

Notes:
- The file marker name must be used exactly. After generation, save it to tests/test_orchestrator.py.
- Do NOT attempt to start an external server in tests — use FastAPI TestClient/AsyncClient.

No extra text outside the file marker. The content must be a complete pytest file.
