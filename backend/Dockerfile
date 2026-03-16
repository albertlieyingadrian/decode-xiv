# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies required for Manim and other tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    texlive \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create necessary directories for static files
RUN mkdir -p static/videos static/pdfs static/notebooks

# Expose the port
EXPOSE 8080

# Command to run the application
# Use the PORT environment variable for Cloud Run compatibility
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
