# Enact Cloud — production Dockerfile
# Runs the FastAPI backend (receipt storage, HITL, dashboard)
# DB: Supabase Postgres via DATABASE_URL env var

FROM python:3.11-slim

WORKDIR /app

# Install cloud dependencies from requirements.txt
COPY cloud/requirements.txt cloud/requirements.txt
RUN pip install --no-cache-dir -r cloud/requirements.txt

# Copy only the cloud package (not the SDK — cloud/ is self-contained)
COPY cloud/ cloud/

EXPOSE 8080

# Fly.io expects the app on 8080 by default
CMD ["uvicorn", "cloud.main:app", "--host", "0.0.0.0", "--port", "8080"]
