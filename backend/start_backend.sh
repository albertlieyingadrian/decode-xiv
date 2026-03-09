#!/bin/bash
echo "Stopping any existing processes on port 8000..."
lsof -t -i:8000 | xargs -r kill -9
echo "Starting FastAPI server..."
source venv/bin/activate
uvicorn main:app --reload
