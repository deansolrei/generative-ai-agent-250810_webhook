# Use Python 3.12 for better compatibility unless 3.13 is absolutely needed
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT 8080

# IMPORTANT: Entrypoint must match your file and Flask app variable!
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 flask_healthcare_bot:app