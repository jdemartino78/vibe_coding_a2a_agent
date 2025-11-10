#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/setup_env.sh"

# Set the service name for the weather server
export SERVICE_NAME='weather-remote-mcp-server'

gcloud run deploy $SERVICE_NAME \
  --source $SCRIPT_DIR/weather_mcp_server \
  --region $LOCATION \
  --project $PROJECT_ID \
  --memory 4G \
  --no-allow-unauthenticated

