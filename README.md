# Charge Consensus - An AI-Powered EV Charging Orchestrator

**Project for Junction 2025 - Denso "ChargeID: Trusted EV Services" Challenge**

**Punchline:** Smart charging for a stressed grid.

<p align="center">
  <img src="https://i.imgur.com/your-dashboard-image.png" width="700" alt="Charge Consensus Dashboard">
</p>

*(Recommendation: Replace the Imgur link above with a real screenshot of your dashboard.)*

## 1. The Problem

EV charging today is fundamentally "dumb." It's a first-come, first-served system that leads to three major problems:
1.  **Grid Strain:** Unmanaged charging during peak hours overloads the power grid, causing instability and high costs for operators.
2.  **Unfair Queues:** A driver with a nearly full battery can block someone with a genuine emergency, creating a poor user experience.
3.  **No Incentive to Help:** Drivers who have flexible schedules have no reason to charge during off-peak hours, even though it would benefit the entire system.

## 2. Our Solution: Charge Consensus

**Charge Consensus** is an intelligent orchestration platform that uses GenAI to create a fair, efficient, and grid-aware charging ecosystem.

Our system reimagines EV charging by transforming it from a simple utility into a dynamic, negotiated service. It addresses the core challenge by creating business value through gamified incentives and demand management, all while respecting user privacy and security through the principles of Decentralized Identity (DID).

### How It Works

<p align="center">
  <img src="https://i.imgur.com/your-diagram-image.png" width="600" alt="Architecture Diagram">
</p>

*(Recommendation: Replace the Imgur link above with a real screenshot of the architecture diagram.)*

1.  **Natural Language Request:** A driver states their need in plain English (e.g., "I'm in a panic!" or "I'll be here all day").
2.  **DID-Based Verification (Simulated):** The driver's identity and vehicle data are verified using a Verifiable Credential (VC). This ensures a secure, trusted interaction without sharing unnecessary personal data.
3.  **AI Orchestration:** Our GenAI-powered orchestrator analyzes the user's request, their vehicle's state of charge (SoC), and the **real-time status of the power grid**.
4.  **Intelligent Charging Plan:** The AI generates a tailored charging plan:
    *   **If the grid is STRESSED**, it offers flexible users an "Eco Charge" plan and rewards them with **loyalty points**. Urgent users are still given a "Fast Charge," but with no points.
    *   **If the grid is STABLE**, all users are offered a "Fast Charge."
5.  **Dynamic Learning:** The AI uses a "short-term memory" of recent requests to make its decisions progressively more consistent and context-aware.

## 3. Technologies Used

*   **Backend:** Python, FastAPI
*   **AI Engine:** Google GenAI (Gemini)
*   **Frontend:** HTML, CSS, JavaScript (served via Python's standard library)
*   **Decentralized Identity:** Denso DID Agent (Simulated for the demo)
*   **Core Libraries:** `httpx`, `asyncio`, `uvicorn`, `pydantic`, `python-dotenv`

## 4. How to Run the Demo

Follow these steps to run the full demonstration.

### Prerequisites

-   Python 3.9+
-   A Google AI API key for the Gemini model.

### Step 1: Clone the Repository

```
git clone https://github.com/your-username/charge-consensus.git
cd charge-consensus
```


### Step 2: Install Dependencies

Navigate to the `src` directory and install the required Python libraries from the `requirements.txt` file.

```
cd src
pip install -r requirements.txt
```

### Step 3: Set Your API Key

Inside the `src` directory, create a file named `.env`. Add your Google AI API key to this file:

**File: `src/.env`**

`GEMINI_API_KEY="YOUR_API_KEY_HERE"`



### Step 4: Run the Application

You will need to run two terminal sessions, both from within the `src` directory.

**Terminal 1: Start the Orchestrator**
This is the main "brain" of the application.


```
# Make sure you are inside the 'src' directory
python3 orchestrator.py
```

You should see output confirming that the Uvicorn server has started on `http://0.0.0.0:8001`.

**Terminal 2: Start the Demo Controller**
This script provides a menu to control the demonstration.

```
# Make sure you are inside the 'src' directory
python3 demo_controller.py

```


### Step 5: Experience the Demo

1.  The `demo_controller.py` script will automatically open the **Charge Consensus Dashboard** in your web browser.
2.  Your terminal will display a menu:
    ```
    --- Demo Options ---
    1. Simulate ALL initial users (Runs simulate_demo.py)
    2. Activate LIVE TEXT demo
    3. EXIT
    Enter your choice (1, 2, or 3):
    ```
3.  **Choose option 1** to populate the dashboard with the three predefined users. Explain how the AI has assigned different plans based on their needs.
4.  Use the **"Set Grid to STRESSED" / "Set Grid to STABLE"** buttons on the dashboard to change the grid conditions and show how the AI's recommendations would change for new users.
5.  **Choose option 2** for the live demo. The terminal will prompt you to enter a custom request. Type a new scenario, for example:
    > My car is almost dead, I have a flight to catch and I need 80% charge!
6.  Press Enter and watch as a new "live-demo" driver instantly appears on the dashboard with a `HIGH` priority and `FAST CHARGE` plan. This demonstrates the system's ability to handle any dynamic, natural language request.

## 6. Project Structure

/
|-- presentation/ # Your pitch deck PDF
|-- src/
| |-- _deprecated/ # Old, unused files
| |-- .env # For API keys (Secured way)
| |-- .python-version # Python version file
| |-- dashboard.html # The live dashboard UI
| |-- demo_controller.py # The main script to run the demo
| |-- orchestrator.py # The core FastAPI application and AI logic
| |-- requirements.txt # Project dependencies
| |-- simulate_demo.py # A helper script for the demo controller
|-- README.md # This file



## 7. Team

This project is created at Junction 2025 by:
*   Jannen
*   Al Shafi
*   Nikhil
