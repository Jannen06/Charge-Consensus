You are an expert in deploying Python apps to Google Cloud. Take the provided FastAPI code (orchestrator.py) and generate the following files for serverless deployment on Google Cloud Run:

1. **requirements.txt**: List all dependencies from the code (e.g., fastapi, uvicorn, httpx, pydantic, google-generativeai). Use exact versions if possible for reproducibility.

2. **Dockerfile**: A multi-stage Dockerfile using Python 3.12-slim base. Copy the app files, install deps, expose port 8080 (Cloud Run standard), and set CMD to run uvicorn with --host 0.0.0.0 --port $PORT.

3. **app.yaml** (optional for App Engine, but include for flexibility): Basic config if needed, but prioritize Cloud Run.

4. **Modified orchestrator.py**: Update the code to:
   - Use os.environ.get('PORT', 8080) for the port.
   - Load the Google API key from env var GEMINI_API_KEY (remove hardcoded key for security).
   - Ensure it handles dashboard.html serving.

Output each file as a code block in your response, labeled clearly (e.g., ### requirements.txt). Ensure the app is production-ready: add health checks if needed, handle env vars for secrets, and make it scalable.

Vibe: Clean, efficient, secure deployment setup for a hackathon project.