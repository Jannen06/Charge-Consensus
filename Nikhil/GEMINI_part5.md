You will output exactly one file.

===== Dockerfile =====

Create a production-friendly Dockerfile for the orchestrator app with these constraints:

- Use python:3.10-slim as base.
- Use non-root user `appuser` with uid 1000.
- Set WORKDIR /app
- Copy only requirements and install deps first to leverage layer caching.
- Install minimal packages: pip, build-essential (only if required), and cleanup apt caches.
- Copy orchestrator_server.py and dashboard.html into /app.
- Set environment variables defaults: PYTHONUNBUFFERED=1, DENSO_API_HOST=https://hackathon.dndappsdev.net
- Expose port 8000.
- Entrypoint: uvicorn orchestrator_server:app --host 0.0.0.0 --port 8000 --proxy-headers
- Use a small number of layers and ensure no secrets are baked into the image.

Include comments for how to build and run locally with `docker build` and `docker run -e DENSO_API_TOKEN=...`.

No extra text outside the file marker. The content must be a complete Dockerfile.
