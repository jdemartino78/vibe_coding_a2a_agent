#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/setup_env.sh"

# Change to the script's directory to ensure correct source path
cd "$SCRIPT_DIR"

# Set the service name for the cocktail server
export SERVICE_NAME='cocktail-mcp-server'

gcloud run deploy $SERVICE_NAME \
  --source ./cocktail_mcp_server \
  --region $LOCATION \
  --project $PROJECT_ID \
  --memory 4G \
  --no-allow-unauthenticated


gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="serviceAccount:service-712747314987@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region="$LOCATION"
