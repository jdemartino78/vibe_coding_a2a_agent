#!/bin/bash

# This script deploys the Weather MCP Server to Google Cloud Run.
# It sources the central .env file from the project root for configuration.

# Determine the project root directory, assuming this script is in a subdirectory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Set the service name for the weather server
export SERVICE_NAME='weather-remote-mcp-server'

echo "Deploying Weather MCP Server..."
gcloud run deploy $SERVICE_NAME \
  --source "$SCRIPT_DIR/weather_mcp_server" \
  --region $GOOGLE_CLOUD_LOCATION \
  --project $GOOGLE_CLOUD_PROJECT \
  --memory 4G \
  --no-allow-unauthenticated

