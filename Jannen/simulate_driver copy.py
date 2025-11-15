import httpx
import sys
import asyncio
import time
import json

# --- Configuration ---
ORCHESTRATOR_URL = "http://127.0.0.1:8001" # Using port 8001
DENSO_API_HOST = "https://hackathon.dndappsdev.net"

# --- Denso API Simulation Functions ---

async def issue_vehicle_soc_vc(vehicle_did: str, soc: int) -> dict:
    """
    Simulates a Vehicle calling /api/issue-credential.
    This "preserves" the vehicle's SoC as a trusted VC.
    """
    print(f"  [Denso Sim] Issuing 'VehicleSoC' VC for {vehicle_did} with {soc}%...")
    
    # This is the "claims" block from Page 7
    credential_subject = {
        "type": "VehicleSoC", # Our custom type
        "soc_percent": soc,
        "issued_at": time.time()
    }
    
    # --- REAL API CALL (when you have a token) ---
    # url = f"{DENSO_API_HOST}/api/issue-credential?credential_type=VehicleSoC"
    # headers = {"Authorization": "Bearer YOUR_MENTOR_TOKEN"}
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(url, json={"credentialSubject": credential_subject}, headers=headers)
    #     response.raise_for_status()
    #     new_vc = response.json()
    #     print("  [Denso Sim] VC Created:", json.dumps(new_vc, indent=2))
    #     return new_vc
    
    # --- SIMULATED SUCCESS ---
    # We'll just create a fake VC that *looks* like the one on Page 6
    await asyncio.sleep(0.5) # Simulate network delay
    fake_vc = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": "urn:uuid:fake-vc-12345",
        "type": ["VerifiableCredential", "VehicleSoC"],
        "issuer": "did:denso:vehicle:vw:45678", # Fake issuer
        "issuanceDate": "2025-11-15T12:00:00Z",
        "credentialSubject": credential_subject,
        "proof": { "type": "Ed25519Signature2020", "proofValue": "zFakeProofValue..." }
    }
    print("  [Denso Sim] Fake VC Created.")
    return fake_vc


async def create_presentation(user_did: str, vehicle_vc: dict) -> dict:
    """
    Simulates a Driver calling /api/request-presentation.
    This "bundles" the driver's ID and the car's VC to "share" them.
    """
    print(f"  [Denso Sim] Bundling VCs for {user_did} into a Presentation...")
    
    # --- REAL API CALL (when you have a token) ---
    # url = f"{DENSO_API_HOST}/api/request-presentation"
    # headers = {"Authorization": "Bearer YOUR_MENTOR_TOKEN"}
    # payload = {
    #     "holder": user_did,
    #     "verifiableCredential": [vehicle_vc] 
    #     # You would also add the driver's "Employee" VC here
    # }
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(url, json=payload, headers=headers)
    #     response.raise_for_status()
    #     new_presentation = response.json()
    #     print("  [Denso Sim] Presentation Created:", json.dumps(new_presentation, indent=2))
    #     return new_presentation
        
    # --- SIMULATED SUCCESS ---
    await asyncio.sleep(0.5) # Simulate network delay
    fake_presentation = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "id": "urn:uuid:fake-presentation-98765",
        "type": ["VerifiablePresentation"],
        "holder": user_did,
        "verifiableCredential": [vehicle_vc] # Embed the VC
    }
    print("  [Denso Sim] Fake Presentation Created.")
    return fake_presentation


# --- Orchestrator API Call Function ---

async def send_charge_request(did: str, text: str, presentation: dict):
    """
    This script simulates a driver talking to YOUR orchestrator.
    It calls the "/api/negotiate" endpoint with the presentation.
    """
    url = f"{ORCHESTRATOR_URL}/api/negotiate"
    payload = {
        "user_did": did,
        "text": text,
        "presentation": presentation # Send the whole presentation
    }
    
    print(f"\n--- Simulating Driver: {did.split(':')[2]} ---")
    print(f"Sending text: '{text}'")
    
    # Debug line to show what's being sent
    print(f"\n[Debug] Sending payload to {url}")
    # print(json.dumps(payload, indent=2)) # You can un-comment this if you need to see the full JSON
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            print("[Driver Sim] Orchestrator Response:", response.json())
            
    except httpx.HTTPStatusError as e:
        print(f"\n!!! HTTPStatusError: {e.response.status_code} {e.response.reason_phrase}")
        print("Server Response:", e.response.text)
        
    except httpx.RequestError as e:
        print(f"\n!!! ERROR: Could not connect to orchestrator.")
        print(f"Did you start the server? `python {sys.argv[0]}`")
        print(f"Details: {e}")
    
    print("-------------------------------------------\n")

async def main():
    # --- This is your new demo script! ---
    
    # --- Driver 1: Tom (Low priority) ---
    print("--- DEMO START: TOM (LOW PRIORITY) ---")
    
    tom_vehicle_vc = await issue_vehicle_soc_vc(
        vehicle_did="did:denso:vehicle:tom:123", 
        soc=85
    )
    
    tom_presentation = await create_presentation(
        user_did="did:denso:user:tom:12345",
        vehicle_vc=tom_vehicle_vc
    )
    
    await send_charge_request(
        did="did:denso:user:tom:12345",
        text="Hey, I'm just plugging in. I'll be here all day, no rush at all.",
        presentation=tom_presentation
    )
    
    await asyncio.sleep(2) # Pause for demo
    
    # --- Driver 2: Sarah (High priority) ---
    print("--- DEMO START: SARAH (HIGH PRIORITY) ---")
    
    sarah_vehicle_vc = await issue_vehicle_soc_vc(
        vehicle_did="did:denso:vehicle:sarah:456", 
        soc=20 # She has low battery!
    )
    
    sarah_presentation = await create_presentation(
        user_did="did:denso:user:sarah:67890",
        vehicle_vc=sarah_vehicle_vc
    )
    
    await send_charge_request(
        did="did:denso:user:sarah:67890",
        text="I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70%!",
        presentation=sarah_presentation
    )

if __name__ == "__main__":
    asyncio.run(main())