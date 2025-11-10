#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/setup_env.sh"

# Set the service name for the cocktail server
export SERVICE_NAME='cocktail-mcp-server'

gcloud run deploy $SERVICE_NAME \
  --source $SCRIPT_DIR/cocktail_mcp_server \
  --region $LOCATION \
  --project $PROJECT_ID \
  --memory 4G \
  --no-allow-unauthenticated

