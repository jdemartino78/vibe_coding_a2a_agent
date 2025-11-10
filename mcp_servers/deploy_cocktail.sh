#!/bin/bash

# This script deploys the Cocktail MCP Server to Google Cloud Run.
# It sources the central .env file from the project root for configuration.

# Determine the project root directory, assuming this script is in a subdirectory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Set the service name for the cocktail server
export SERVICE_NAME='cocktail-mcp-server'

echo "Deploying Cocktail MCP Server..."
gcloud run deploy $SERVICE_NAME \
  --source "$SCRIPT_DIR/cocktail_mcp_server" \
  --region $GOOGLE_CLOUD_LOCATION \
  --project $GOOGLE_CLOUD_PROJECT \
  --memory 4G \
  --min-instances=1 \
  --no-allow-unauthenticated

