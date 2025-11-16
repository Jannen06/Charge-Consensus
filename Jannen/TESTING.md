# Local Testing Instructions

Follow these steps to test the Charge Consensus AI Orchestrator locally:

## Prerequisites

1.  **Python Environment:** Ensure you have Python 3.10+ installed.
2.  **Dependencies:** Make sure all required Python packages are installed. This now includes `python-dotenv` for loading environment variables. Please re-run the installation command:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Google Gemini API Key:** You will need a Google Gemini API key.

## Setup

1.  **Create a `.env` file:** Create a file named `.env` in the root directory of the project.
    ```
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```
    Replace `"YOUR_GEMINI_API_KEY"` with your actual Google Gemini API key.

## Running the Application

1.  **Start the Orchestrator:**
    Open a terminal and run the `orchestrator.py` script. This will start the FastAPI server and serve the dashboard.
    ```bash
    python orchestrator.py
    ```
    You should see output indicating the server is running, typically on `http://0.0.0.0:8080` (or `8001` if `PORT` env var is not set).

2.  **Access the Dashboard:**
    Open your web browser and navigate to `http://127.0.0.1:8080` (or `http://127.0.0.1:8001` if the default port is used). You should see the Charge Consensus Dashboard.

3.  **Simulate Initial User Requests (Optional but Recommended):**
    Open a *second* terminal and run the `simulate_demo.py` script. This will send initial user requests (e.g., for Tom, Sarah) to the orchestrator.
    ```bash
    python simulate_demo.py
    ```
    Observe the dashboard to see these requests appear. Verify that `min_soc` is displayed as `80%` (if not explicitly provided in the simulation) and user names like "Tom", "Sarah" are correct.

4.  **Interact with the Demo Controller (Live Requests):**
    Open a *third* terminal and run the `demo_controller.py` script. This script allows you to send live, interactive user requests.
    ```bash
    python demo_controller.py
    ```
    *   When prompted, select option `2` ("Activate LIVE TEXT demo").
    *   Enter a charging request (e.g., "I need to charge my car to 90% by 5 PM").
    *   Repeat this a few times.
    *   Observe the dashboard. Verify that new requests appear with sequential names like "Live-demo1", "Live-demo2", etc., and that `min_soc` defaults to `80%` if not specified in your text.

## Stopping the Application

To stop the orchestrator and demo controller, press `Ctrl+C` in each of their respective terminal windows.
