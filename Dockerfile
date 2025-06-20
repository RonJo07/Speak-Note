# Use the official Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (libGL for OpenCV, tesseract for pytesseract, and other common image libs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        tesseract-ocr \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code
COPY . .

# Expose the port (matches your Procfile)
EXPOSE 8080

# Start the FastAPI app with Uvicorn (matches your Procfile)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 