# Use an official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compiling certain python packages like spacy or psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download Spacy English model
RUN python -m spacy download en_core_web_md

# Copy the rest of the application code
COPY . .

# Set Python Path so it finds the app module
ENV PYTHONPATH=/app

# Default command (overridden by docker-compose for the worker)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
