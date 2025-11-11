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

# Deploy each agent
echo "Deploying Cocktail Agent..."
python "$SCRIPT_DIR/deploy_cocktail_agent.py"

# Re-source the environment file to pick up the newly created agent URL
set -a
source "$PROJECT_ROOT/.env"
set +a

echo "Deploying Weather Agent..."
python "$SCRIPT_DIR/deploy_weather_agent.py"

# Re-source the environment file again
set -a
source "$PROJECT_ROOT/.env"
set +a

echo "Deploying Hosting Agent..."
python "$SCRIPT_DIR/deploy_hosting_agent.py"

echo "All agents deployed."

echo "Granting Agent Engine Service Agent Cloud Run Invoker"
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com"  --role="roles/run.invoker"

