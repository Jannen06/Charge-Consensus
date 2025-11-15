import httpx
import sys
import asyncio
import time
import json
import uuid

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001"
DENSO_API_HOST = "https://hackathon1.didgateway.eu"

# --- Denso API Functions ---

async def issue_vehicle_soc_vc(vehicle_did: str, soc: int) -> dict:
    """
    Issues a ChargingSessionEnvelope credential using the exact strict format required by the API.
    """
    print(f"  [Denso API] Issuing 'ChargingSessionEnvelope' VC for {vehicle_did} with {soc}%...")

    # Build the credentialSubject with the required fields
    credential_subject = {
        "id": vehicle_did,  # Use the 'id' field for the vehicle's DID
        "envelope_id": str(uuid.uuid4()),
        "envelope_version": "1.0.0",
        "schema_uri": "urn:cloudcharger:schemas:ocpi-session-envelope:1",
        "object_type": "ocpi_session",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(uuid.uuid4()),
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # Add custom data inside a 'claims' object to pass validation
        "claims": {
            "soc_percent": soc
        }
    }

    url = f"{DENSO_API_HOST}/boy/api/issue-credential"
    params = {
        "credential_type": "ChargingSessionEnvelope"
    }
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "credentialSubject": credential_subject
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            issued_vc = response.json()
            print("  [Denso API] ✓ VC Successfully Issued!")
            return issued_vc

    except httpx.HTTPStatusError as e:
        print(f"  [Denso API] HTTP Error {e.response.status_code} - {e.response.text}")
        return await issue_vehicle_soc_vc_simulated(vehicle_did, soc)
    except Exception as e:
        print(f"  [Denso API] Error: {e}")
        return await issue_vehicle_soc_vc_simulated(vehicle_did, soc)

async def create_presentation(user_did: str, vehicle_vc: dict) -> dict:
    """
    Builds and sends a complete Verifiable Presentation to the request-presentation endpoint.
    """
    print(f"  [Denso API] Creating and sending Presentation for {user_did}...")

    # Build the full Verifiable Presentation object
    presentation_payload = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiablePresentation"],
        "holder": user_did,
        "verifiableCredential": [vehicle_vc]  # Embed the credential here
    }

    url = f"{DENSO_API_HOST}/boy/api/request-presentation"
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # The request body should be the full presentation object
            response = await client.post(url, json=presentation_payload, headers=headers)
            response.raise_for_status()
            signed_presentation = response.json()
            print("  [Denso API] ✓ Presentation Successfully Processed!")
            return signed_presentation

    except httpx.HTTPStatusError as e:
        print(f"  [Denso API] HTTP Error {e.response.status_code} - {e.response.text}")
        print("  [Denso API] Falling back to simulated presentation...")
        return await create_presentation_simulated(user_did, vehicle_vc)
    except Exception as e:
        print(f"  [Denso API] Error: {e}")
        return await create_presentation_simulated(user_did, vehicle_vc)

# --- Fallback Simulation and Orchestrator Functions ---

async def issue_vehicle_soc_vc_simulated(vehicle_did: str, soc: int) -> dict:
    """Fallback: Creates a simulated VC that matches the expected structure."""
    print("  [Denso Sim] Creating simulated VC...")
    await asyncio.sleep(0.3)
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": f"urn:uuid:sim-vc-{int(time.time())}",
        "type": ["VerifiableCredential", "ChargingSessionEnvelope"],
        "issuer": vehicle_did,
        "issuanceDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "credentialSubject": {
            "id": vehicle_did,
            "claims": {
                "soc_percent": soc
            }
        },
        "proof": {"type": "Ed25519Signature2020", "proofValue": "zSimulated..."}
    }

async def create_presentation_simulated(user_did: str, vehicle_vc: dict) -> dict:
    """Fallback: Creates a simulated presentation."""
    print("  [Denso Sim] Creating simulated presentation...")
    await asyncio.sleep(0.3)
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": f"urn:uuid:sim-pres-{int(time.time())}",
        "type": ["VerifiablePresentation"],
        "holder": user_did,
        "verifiableCredential": [vehicle_vc]
    }

async def send_charge_request(did: str, text: str, presentation: dict):
    """Sends the charge request to your orchestrator."""
    url = f"{ORCHESTRATOR_URL}/api/negotiate"
    payload = {
        "user_did": did,
        "text": text,
        "presentation": presentation
    }
    
    driver_name = did.split(':')[-2] if ':' in did else did
    print(f"\n--- Simulating Driver: {driver_name} ---")
    print(f"Sending text: '{text}'")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            print(f"[Driver Sim] Orchestrator Response: {response.json()}")
    except Exception as e:
        print(f"[Driver Sim] ERROR: Could not connect or send request: {e}")
    
    print("-------------------------------------------\n")

# --- Main Execution ---

async def main():
    print("=" * 60)
    print("DENSO DID GATEWAY INTEGRATION TEST")
    print(f"Gateway: {DENSO_API_HOST}")
    print(f"Orchestrator: {ORCHESTRATOR_URL}")
    print("=" * 60)
    
    # --- Driver 1: Tom (Low priority) ---
    print("\n--- DEMO START: TOM (LOW PRIORITY) ---")
    tom_vc = await issue_vehicle_soc_vc("did:denso:vehicle:tom:123", 85)
    tom_presentation = await create_presentation("did:denso:user:tom:12345", tom_vc)
    await send_charge_request(
        "did:denso:user:tom:12345",
        "Hey, I'm just plugging in. I'll be here all day, no rush at all.",
        tom_presentation
    )
    
    await asyncio.sleep(2)
    
    # --- Driver 2: Sarah (High priority) ---
    print("\n--- DEMO START: SARAH (HIGH PRIORITY) ---")
    sarah_vc = await issue_vehicle_soc_vc("did:denso:vehicle:sarah:456", 20)
    sarah_presentation = await create_presentation("did:denso:user:sarah:67890", sarah_vc)
    await send_charge_request(
        "did:denso:user:sarah:67890",
        "I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70%!",
        sarah_presentation
    )

if __name__ == "__main__":
    asyncio.run(main())
