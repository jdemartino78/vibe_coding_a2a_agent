#!/bin/bash

# This script deploys the Cocktail, Weather, and Hosting agents.
# It sources the central .env file from the project root for configuration.

# Determine the project root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../../.."

# Activate the virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Deploy Cocktail and Weather agents in parallel
echo "Deploying Cocktail Agent in the background..."
python "$SCRIPT_DIR/deploy_cocktail_agent.py" &
cocktail_pid=$!

echo "Deploying Weather Agent in the background..."
python "$SCRIPT_DIR/deploy_weather_agent.py" &
weather_pid=$!

# Wait for both background jobs to complete
wait $cocktail_pid
wait $weather_pid

# Re-source the environment file to pick up the newly created agent URLs
set -a
source "$PROJECT_ROOT/.env"
set +a

echo "Deploying Hosting Agent..."
python "$SCRIPT_DIR/deploy_hosting_agent.py"

echo "All agents deployed."

echo "Granting Agent Engine Service Account Cloud Run Invoker"
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com"  --role="roles/run.invoker"

echo "Granting Agent Engine Service Account AI Platform User"
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com"  --role="roles/aiplatform.user"
