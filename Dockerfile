FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY src/ src/

# Port will be set by Railway/Render via PORT env var
EXPOSE 8000

CMD ["python", "main.py"]
