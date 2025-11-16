# Google Cloud Run Deployment Instructions

Follow these steps to deploy the Charge Consensus AI Orchestrator to Google Cloud Run.

## Prerequisites

1.  **Google Cloud Project:** You need an active Google Cloud Project.
2.  **gcloud CLI:** Ensure you have the Google Cloud SDK (`gcloud` command-line tool) installed and authenticated to your Google Cloud Project.
3.  **Cloud Run API Enabled:** Make sure the Cloud Run API is enabled in your Google Cloud Project.
4.  **Cloud Build API Enabled:** Make sure the Cloud Build API is enabled in your Google Cloud Project.

## Deployment Steps

1.  **Navigate to your project directory:**
    Open your terminal and navigate to the root directory of your project where `Dockerfile`, `orchestrator.py`, and `requirements.txt` are located.

    ```bash
    cd /path/to/your/project/Jannen
    ```

2.  **Build and Deploy to Cloud Run:**
    Use the `gcloud run deploy` command to build your Docker image and deploy it to Cloud Run.

    ```bash
    gcloud run deploy charge-consensus-orchestrator \
      --image gcr.io/<YOUR_PROJECT_ID>/charge-consensus-orchestrator \
      --platform managed \
      --region <YOUR_GCP_REGION> \
      --allow-unauthenticated \
      --set-env-vars GEMINI_API_KEY="YOUR_GEMINI_API_KEY" \
      --port 8080
    ```

    **Replace the placeholders:**
    *   `<YOUR_PROJECT_ID>`: Your Google Cloud Project ID.
    *   `<YOUR_GCP_REGION>`: The Google Cloud region where you want to deploy (e.g., `us-central1`, `europe-west1`).
    *   `"YOUR_GEMINI_API_KEY"`: Your actual Google Gemini API key. **Do not hardcode this in your `Dockerfile` or commit it to source control.** Setting it via `--set-env-vars` is the secure way for Cloud Run.

    **Explanation of flags:**
    *   `charge-consensus-orchestrator`: The name of your Cloud Run service.
    *   `--image`: Specifies the Docker image to build and deploy. `gcr.io/<YOUR_PROJECT_ID>/charge-consensus-orchestrator` is a common convention for images stored in Google Container Registry.
    *   `--platform managed`: Deploys to the fully managed Cloud Run environment.
    *   `--region`: Specifies the region for deployment.
    *   `--allow-unauthenticated`: Allows unauthenticated access to your service. Remove this flag if you want to secure your service.
    *   `--set-env-vars GEMINI_API_KEY="YOUR_GEMINI_API_KEY"`: Sets the `GEMINI_API_KEY` environment variable for your Cloud Run service. This is crucial for your application to access the Gemini API.
    *   `--port 8080`: Specifies that your application listens on port 8080, which is configured in your `Dockerfile` and `orchestrator.py`.

3.  **Monitor Deployment:**
    The `gcloud run deploy` command will show you the build and deployment progress. Once completed, it will provide you with the URL of your deployed service.

4.  **Test the Deployed Service:**
    *   Open the provided URL in your web browser to access the dashboard.
    *   You can also use `curl` or `httpx` to interact with your API endpoints (e.g., `/api/negotiate`, `/api/status`).

## Updating the Service

To deploy new changes, simply run the `gcloud run deploy` command again with the same parameters. Cloud Run will automatically build a new image and roll out the update.
