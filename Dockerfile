FROM python:3.10

# Set working directory inside the container
WORKDIR /app

# Copy all project files into /app
COPY . /app

# Ensure /data directory is explicitly created first, then copy contents from /app/data
RUN mkdir -p /data && \
    cp -r /app/data/* /data/ || true && \
    chmod -R 777 /data

# Install required dependencies
RUN pip install --no-cache-dir fastapi uvicorn openai db-sqlite3 requests markdown duckdb gitpython pillow SpeechRecognition

# Set environment variable
ENV AIPROXY_TOKEN=${AIPROXY_TOKEN}

# Start the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

