# Use an official lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies required for OpenCV, PyTorch, and video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy dependency definition
COPY requirements.txt /app/

# Install python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . /app/

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Command to run uvicorn server.
# Cloud Run automatically sets the PORT environment variable.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
