FROM python:3.12-slim

WORKDIR /app

# Ensure your service_account_key.json is in the same directory as your Dockerfile
# when you build the image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- ADD THIS LINE ---
COPY service_account_key.json /app/secrets/service_account_key.json
# --- END ADDITION ---

COPY . .

# Cloud Run expects PORT environment variable
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
