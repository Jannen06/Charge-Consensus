
import asyncio
import httpx
import argparse
import os
import json
import time
import logging
from typing import Dict, Any

# Top constants
DENSO_API_HOST = os.getenv("DENSO_API_HOST", "https://hackathon.dndappsdev.net")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
DENSO_API_TOKEN = os.getenv("DENSO_API_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def issue_vehicle_soc_vc(soc_percent: int) -> Dict[str, Any]:
    if DENSO_API_TOKEN:
        headers = {"Authorization": f"Bearer {DENSO_API_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DENSO_API_HOST}/api/issue-credential",
                    json={"credentialSubject": {"type": "VehicleSoC", "soc_percent": soc_percent}},
                    headers=headers,
                    timeout=5.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error issuing credential: {e}")
            # Fallback to mock
            pass
    
    return {
        "vc_id": f"mock-vc-{int(time.time())}",
        "credentialSubject": {"type": "VehicleSoC", "soc_percent": soc_percent},
    }

async def create_presentation(user_did: str, vehicle_vc: Dict[str, Any]) -> Dict[str, Any]:
    if DENSO_API_TOKEN:
        headers = {"Authorization": f"Bearer {DENSO_API_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DENSO_API_HOST}/api/request-presentation",
                    json={"did": user_did, "verifiable_credential": vehicle_vc},
                    headers=headers,
                    timeout=5.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error creating presentation: {e}")
            # Fallback to mock
            pass

    return {
        "presentation_id": f"mock-pres-{int(time.time())}",
        "vc": vehicle_vc,
    }

async def send_charge_request(user_did: str, text: str, presentation: Dict[str, Any]) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/api/negotiate",
                json={"user_did": user_did, "text": text, "presentation": presentation},
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.error(f"Orchestrator rejected the request: {e.response.text}")
        else:
            logger.error(f"Error sending charge request: {e}")
    except httpx.RequestError as e:
        logger.error(f"Error sending charge request: {e}")
    return {}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soc", type=int, default=40, help="State of Charge in percent")
    parser.add_argument("--user-did", type=str, default="did:denso:user:sarah", help="User's DID")
    parser.add_argument("--text", type=str, default="I need to leave by 15:00", help="User's charging request text")
    args = parser.parse_args()

    print("Step 1: Simulating Vehicle creating a new SoC credential...")
    vehicle_vc = await issue_vehicle_soc_vc(args.soc)
    if not vehicle_vc:
        return

    print("Step 2: Simulating Driver bundling VCs into a Presentation...")
    presentation = await create_presentation(args.user_did, vehicle_vc)
    if not presentation:
        return

    print("Step 3: Sending trusted data + user text to our AI Orchestrator...")
    response = await send_charge_request(args.user_did, args.text, presentation)
    if response:
        print(json.dumps(response, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
