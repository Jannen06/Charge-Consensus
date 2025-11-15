import httpx
import asyncio
import time
import json
import uuid

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001"
DENSO_API_HOST = "https://hackathon1.didgateway.eu"

async def issue_valid_vc_for_choice(user_did: str) -> dict:
    """
    Issues a new, valid VC to send with the user's choice.
    This is necessary to pass the orchestrator's verification step.
    """
    print("  [Choice Sim] Issuing a fresh VC to accompany user's choice...")
    
    # We can use a simplified subject since it just needs to be valid
    credential_subject = {
        "id": user_did,
        "envelope_id": str(uuid.uuid4()),
        "envelope_version": "1.0.1", # Increment version for clarity
        "schema_uri": "urn:cloudcharger:schemas:user-choice:v1",
        "object_type": "user_choice",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(uuid.uuid4()),
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "end_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claims": {
            "accepted_offer": "eco_charge"
        }
    }

    url = f"{DENSO_API_HOST}/boy/api/issue-credential"
    params = {"credential_type": "UserChoice"}
    headers = {"Content-Type": "application/json"}
    payload = {"credentialSubject": credential_subject}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            print("  [Choice Sim] ✓ Fresh VC Issued.")
            return response.json()
    except Exception as e:
        print(f"  [Choice Sim] ✗ ERROR issuing fresh VC: {e}. Falling back to simulation.")
        # Fallback if the API fails during this step
        return {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "id": "urn:uuid:sim-choice-vc",
            "type": ["VerifiableCredential", "UserChoice"],
            "credentialSubject": {"id": user_did, "claims": {"accepted_offer": "eco_charge", "soc_percent": 85}}
        }

async def create_valid_presentation_for_choice(user_did: str, choice_vc: dict) -> list:
    """
    Creates a valid presentation for the user's choice VC.
    """
    print("  [Choice Sim] Creating a fresh Presentation...")
    
    url = f"{DENSO_API_HOST}/boy/api/request-presentation"
    headers = {"Content-Type": "application/json"}
    # The API expects a direct array of VCs
    payload = [choice_vc]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            print("  [Choice Sim] ✓ Fresh Presentation Created.")
            return response.json()
    except Exception as e:
        print(f"  [Choice Sim] ✗ ERROR creating fresh presentation: {e}. Falling back.")
        return payload # Send the array anyway

async def simulate_accepting_eco_charge(user_did: str, points: int):
    """
    Simulates a user accepting the 'eco_charge' offer by generating a
    new valid presentation and sending it to the orchestrator.
    """
    print(f"\n--- SIMULATING USER CHOICE ---")
    print(f"User {user_did} has accepted the 'eco_charge' offer for {points} points!")
    print("This confirms their choice and awards them points.")

    # 1. Issue a new, valid VC for this interaction
    choice_vc = await issue_valid_vc_for_choice(user_did)
    
    # 2. Create a new, valid presentation with this VC
    valid_presentation = await create_valid_presentation_for_choice(user_did, choice_vc)

    # 3. Send this valid presentation to the orchestrator
    payload = {
        "user_did": user_did,
        "text": "Yes, I'll take the eco charge for 100 points!",
        "presentation": valid_presentation # Send the REAL, new presentation
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/negotiate", json=payload)
            response.raise_for_status()
            print("\n[Choice Sim] ✓ Orchestrator successfully processed the user's choice.")
            print(f"[Choice Sim] Final Decision: {response.json().get('intent')}")
    except Exception as e:
        print(f"\n[Choice Sim] ✗ ERROR sending choice to orchestrator: {e}")

async def main():
    # This simulates Tom accepting the eco charge offer
    await simulate_accepting_eco_charge(
        user_did="did:denso:user:tom:12345",
        points=100
    )

if __name__ == "__main__":
    # Correct the filename in your terminal if you saved it as `choise`
    # The command should be: python3 simulate_user_choice.py
    print("Running User Choice Simulation...")
    asyncio.run(main())
