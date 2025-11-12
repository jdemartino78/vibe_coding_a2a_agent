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

if [ $? -eq 0 ]; then
    echo "Deployment successful. Fetching Service URL..."
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
      --platform managed \
      --region $GOOGLE_CLOUD_LOCATION \
      --project $GOOGLE_CLOUD_PROJECT \
      --format="text(metadata.annotations.'run.googleapis.com/urls')" | sed 's/.*\["//' | sed 's/".*//')

    if [ -n "$SERVICE_URL" ]; then
        echo "Service URL: $SERVICE_URL"
        # Update the .env file with the new URL
        sed -i "s|^CT_MCP_SERVER_URL=.*|CT_MCP_SERVER_URL=\"$SERVICE_URL\"|" "$PROJECT_ROOT/.env"
        echo "CT_MCP_SERVER_URL updated in .env file."
    else
        echo "Error: Could not fetch Service URL after deployment."
        exit 1
    fi
else
    echo "Error: Cloud Run deployment failed."
    exit 1
fi

