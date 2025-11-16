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
    Issues a credential using the EXACT strict format from the API documentation.
    No extra fields are included to pass "Safe mode" validation.
    The SOC and Vehicle DID are added to a top-level 'custom_data' field.
    """
    print(f"  [Denso API] Issuing 'ChargingSessionEnvelope' VC for {vehicle_did} with {soc}%...")

    # ULTRA-STRICT: Only include fields from the working example.
    credential_subject = {
        "envelope_id": str(uuid.uuid4()),
        "envelope_version": "1.0.0",
        "schema_uri": "urn:cloudcharger:schemas:ocpi-session-envelope:1",
        "object_type": "ocpi_session",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(uuid.uuid4()),
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    url = f"{DENSO_API_HOST}/boy/api/issue-credential"
    params = {
        "credential_type": "ChargingSessionEnvelope"
    }
    headers = {
        "Content-Type": "application/json"
    }
    # Add a top-level custom_data field
    payload = {
        "credentialSubject": credential_subject,
        "custom_data": {
            "vehicle_did": vehicle_did,
            "soc_percent": soc
        }
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
    Sends an array of VCs directly to the request-presentation endpoint.
    """
    print(f"  [Denso API] Sending credential array to {user_did}...")

    url = f"{DENSO_API_HOST}/boy/api/request-presentation"
    headers = {
        "Content-Type": "application/json"
    }
    # The API expects an array of credentials directly as the payload
    payload = [vehicle_vc]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            # The response is likely the signed presentation
            signed_presentation = response.json()
            print("  [Denso API] ✓ Presentation Successfully Processed!")
            return signed_presentation

    except httpx.HTTPStatusError as e:
        print(f"  [Denso API] HTTP Error {e.response.status_code} - {e.response.text}")
        return await create_presentation_simulated(user_did, vehicle_vc)
    except Exception as e:
        print(f"  [Denso API] Error: {e}")
        return await create_presentation_simulated(user_did, vehicle_vc)

# --- Fallback Simulation and Orchestrator Functions (Unchanged) ---
# ... (The rest of your script remains the same) ...

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
            "id": vehicle_did
        },
        "custom_data": { # Add custom data here as well
            "soc_percent": soc
        },
        "proof": {"type": "Ed25519Signature2020", "proofValue": "zSimulated..."}
    }


async def create_presentation_simulated(user_did: str, vehicle_vc: dict) -> dict:
    """Fallback: Creates a simulated presentation by returning the VC array."""
    print("  [Denso Sim] Creating simulated presentation (VC array)...")
    await asyncio.sleep(0.3)
    return [vehicle_vc]


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
        "I'M IN A PANIC! My car is at 40% I have a client meeting at 3 PM and I need at least 70%!",
        sarah_presentation
    )

if __name__ == "__main__":
    asyncio.run(main())
