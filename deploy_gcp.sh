#!/bin/bash
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REPO_NAME="visual-arxiv-repo"

echo "Deploying to Project: $PROJECT_ID in Region: $REGION"

# 1. Enable APIs
echo "Enabling necessary APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  containerregistry.googleapis.com

# 2. Create Artifact Registry Repo (if not exists)
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $REPO_NAME \
      --repository-format=docker \
      --location=$REGION \
      --description="Docker repository for Visual ArXiv"
else
    echo "Artifact Registry repository '$REPO_NAME' already exists."
fi

# 3. Load Environment Variables
if [ -f backend/.env ]; then
    export $(grep -v '^#' backend/.env | xargs)
else
    echo "Error: backend/.env file not found. Please create it with GEMINI_API_KEY."
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY is missing in backend/.env"
    exit 1
fi

# 4. Submit Build
echo "Submitting Cloud Build..."
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_REPO_NAME=$REPO_NAME,_GEMINI_API_KEY="$GEMINI_API_KEY",_OPENROUTER_API_KEY="$OPENROUTER_API_KEY" .

echo "Deployment Complete!"
echo "Backend Service: $(gcloud run services describe visual-arxiv-backend --platform managed --region $REGION --format 'value(status.url)')"
echo "Frontend Service: $(gcloud run services describe visual-arxiv-frontend --platform managed --region $REGION --format 'value(status.url)')"
