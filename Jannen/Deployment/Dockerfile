# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Cloud Run services must listen on the port defined by the PORT environment variable.
# Default to 8080 for local development.
ENV PORT 8080
EXPOSE $PORT

# Run the application using uvicorn
# The $PORT environment variable is automatically provided by Cloud Run.
CMD ["uvicorn", "orchestrator:app", "--host", "0.0.0.0", "--port", "$PORT"]
