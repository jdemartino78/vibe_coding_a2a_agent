#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/setup_env.sh"

# Set the service name for the weather server
export SERVICE_NAME='weather-remote-mcp-server'

gcloud run deploy $SERVICE_NAME \
  --source ./weather_mcp_server \
  --region $LOCATION \
  --project $PROJECT_ID \
  --memory 4G \
  --no-allow-unauthenticated

gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="serviceAccount:service-1077649599081@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region="$LOCATION"
