
import pytest
import pytest_asyncio
import httpx
import respx
import asyncio
import json
import os
import sys
from typing import Dict, Any
import importlib

# Add the project root to the Python path to allow importing orchestrator_server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

orchestrator_server = importlib.import_module("orchestrator_server")

@pytest.mark.asyncio
async def test_verify_denso_presentation_no_token():
    """
    Tests the verify_denso_presentation function when DENSO_API_TOKEN is not set.
    """
    # Ensure the token is not set for this test
    original_token = os.environ.get("DENSO_API_TOKEN")
    if original_token:
        del os.environ["DENSO_API_TOKEN"]

    presentation = {"vc": {"type": "VehicleSoC", "soc_percent": 30}}
    result = await orchestrator_server.verify_denso_presentation(presentation)

    assert result["verified"] is True
    # The default simulation returns a soc of 40
    assert result["soc"] == 40

    # Restore the token if it was originally set
    if original_token:
        os.environ["DENSO_API_TOKEN"] = original_token

@pytest.mark.asyncio
async def test_negotiate_endpoint():
    """
    Tests the /api/negotiate endpoint with a valid request.
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=orchestrator_server.app), base_url="http://test") as client:
        payload = {
            "user_did": "did:denso:user:test",
            "text": "I need a charge",
            "presentation": {"vc": {"type": "VehicleSoC", "soc_percent": 50}}
        }
        response = await client.post("/api/negotiate", json=payload)

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["status"] == "queued"
    assert "queued_id" in response_json
    assert "priority" in response_json

@pytest.mark.asyncio
async def test_negotiate_invalid_did():
    """
    Tests that the /api/negotiate endpoint rejects an invalid DID.
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=orchestrator_server.app), base_url="http://test") as client:
        payload = {
            "user_did": "badid",
            "text": "I need a charge",
            "presentation": {"vc": {"type": "VehicleSoC", "soc_percent": 50}}
        }
        response = await client.post("/api/negotiate", json=payload)

    assert response.status_code == 400
