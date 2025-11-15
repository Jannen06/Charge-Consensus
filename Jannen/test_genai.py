import asyncio
import json
from google import genai
from google.genai.types import GenerateContentConfig, Schema, Type

# --- Standalone GenAI Test Script ---

# IMPORTANT: Replace with your actual Google AI API key
genai_client = genai.Client(api_key="AIzaSyBU7Fe3GLcXsKkplon8PGbWAuS36WYp0jc")

async def get_intent_from_genai(user_text: str) -> dict:
    """
    This is the exact same function from your orchestrator, but with a corrected schema.
    """
    system_prompt = """You are a master EV Charging Concierge. Your sole job is to analyze a user's request and the current power grid status, then create a perfect charging plan. You must fill in all fields of the JSON output.

**Analysis Checklist:**

1.  **Extract Priority**:
    *   `high`: Is the user in a `panic`? Do they have a `meeting` or `appointment`? Are they using words like `ASAP` or `urgent`?
    *   `medium`: Does the user mention a specific future time like `by 6 PM` or `this evening`?
    *   `low`: Is the user flexible? Do they say `no rush`, `all day`, or `overnight`?

2.  **Extract Leave By Time**:
    *   Look for any time mentioned (e.g., "3 PM", "evening").
    *   Convert it to a 24-hour `HH:MM` format. "evening" is `18:00`.
    *   If no time is mentioned, you MUST use `null`.

3.  **Extract Minimum SoC**:
    *   Look for a target battery percentage (e.g., "at least 70%", "full charge").
    *   `full charge` means `100`.
    *   If no target SoC is mentioned, you MUST use `null`.

4.  **Determine Charging Plan & Points (Grid Logic)**:
    *   If grid is **STABLE**: Always `fast_charge`, `10` points.
    *   If grid is **STRESSED**:
        *   If priority is `high`, it MUST be `fast_charge`, `0` points.
        *   If priority is `medium` or `low`, it MUST be `eco_charge`, `100` points.

5.  **Estimate Pickup Time**:
    *   `fast_charge` takes about **45 minutes**.
    *   `eco_charge` takes about **3 hours**.
    *   Provide a user-friendly estimate like `"in about 45 mins"` or `"around 5:30 PM"`.

**CRITICAL OUTPUT FORMAT:**
You MUST return only a single, valid JSON object. All keys must be present. Use `null` if a value is not available.
"""
 
    try:
        # --- CORRECTED SCHEMA DEFINITION ---
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{system_prompt}\n\nAnalyze this request:\n{user_text}",
            config=GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=Schema(
                    type=Type.OBJECT,
                    properties={
                        'priority': Schema(type=Type.STRING),
                        # Correct way to define a nullable string
                        'leave_by': Schema(type=Type.STRING, nullable=True),
                        # Correct way to define a nullable integer
                        'min_soc': Schema(type=Type.INTEGER, nullable=True),
                        'charging_option': Schema(type=Type.STRING),
                        'points_awarded': Schema(type=Type.INTEGER),
                        'pickup_time': Schema(type=Type.STRING),
                    },
                    required=["priority", "leave_by", "min_soc", "charging_option", "points_awarded", "pickup_time"]
                )
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[GenAI Test] ✗ ERROR: {e}")
        return {"error": str(e)}

# ... (The rest of the test script, run_tests() and main(), are exactly the same) ...

async def run_tests():
    """
    Runs a series of tests against the GenAI function to verify its output.
    """
    print("--- Starting GenAI Direct Output Test ---")

    # --- Test Case 1: Sarah (High Priority, Grid Stressed) ---
    print("\n[Test Case 1: Sarah - High Priority, Stressed Grid]")
    prompt1 = "As of 2025-11-16 01:30:00, a user with 3% battery says: 'I'M IN A PANIC! I have a client meeting at 3 PM and I need at least 70%!'. The power grid is currently stressed."
    print(f"  PROMPT: {prompt1}")
    result1 = await get_intent_from_genai(prompt1)
    print(f"  GENAI OUTPUT: {json.dumps(result1, indent=2)}")
    
    # --- Validation ---
    if result1.get("priority") == "high" and result1.get("leave_by") == "15:00" and result1.get("charging_option") == "fast_charge":
        print("  ✓ RESULT: PASS")
    else:
        print("  ✗ RESULT: FAIL")


    # --- Test Case 2: Tom (Low Priority, Grid Stressed) ---
    print("\n[Test Case 2: Tom - Low Priority, Stressed Grid]")
    prompt2 = "As of 2025-11-16 01:30:00, a user with 50% battery says: 'Hey, I'm just plugging in. I'll be here all day, no rush at all.'. The power grid is currently stressed."
    print(f"  PROMPT: {prompt2}")
    result2 = await get_intent_from_genai(prompt2)
    print(f"  GENAI OUTPUT: {json.dumps(result2, indent=2)}")

    # --- Validation ---
    if result2.get("priority") == "low" and result2.get("charging_option") == "eco_charge" and result2.get("points_awarded") == 100:
        print("  ✓ RESULT: PASS")
    else:
        print("  ✗ RESULT: FAIL")


    # --- Test Case 3: Newbie (Medium Priority, Grid Stable) ---
    print("\n[Test Case 3: Newbie - Medium Priority, Stable Grid]")
    prompt3 = "As of 2025-11-16 01:30:00, a user with 40% battery says: 'Hi, it's my first time here! My car is at 40% and I need to leave by the evening.'. The power grid is currently stable."
    print(f"  PROMPT: {prompt3}")
    result3 = await get_intent_from_genai(prompt3)
    print(f"  GENAI OUTPUT: {json.dumps(result3, indent=2)}")

    # --- Validation ---
    if result3.get("priority") == "medium" and result3.get("leave_by") == "18:00" and result3.get("charging_option") == "fast_charge":
        print("  ✓ RESULT: PASS")
    else:
        print("  ✗ RESULT: FAIL")

    print("\n--- Test Complete ---")


if __name__ == "__main__":
    asyncio.run(run_tests())
