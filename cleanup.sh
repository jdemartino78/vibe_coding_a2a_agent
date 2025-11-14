#!/bin/bash

# This script deletes all the resources created during the training session.

# --- Load Environment Variables ---
echo "Loading environment variables..."

# Determine the project root directory, assuming this script is in the root.
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Load environment variables from the root .env file
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "Error: .env file not found in the project root. Please ensure it exists and contains the necessary variables."
    exit 1
fi

# --- Confirmation Prompt ---
read -p "This script will attempt to delete all Cloud Run services, Vertex AI Agent Engines, and the GCS bucket created by this project. Are you sure you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cleanup cancelled."
    exit 1
fi

# --- Delete Cloud Run Services ---
echo "
--- Deleting Cloud Run Services ---"
SERVICES=("cocktail-mcp-server" "weather-remote-mcp-server" "$FRONTEND_SERVICE_NAME")
for SERVICE in "${SERVICES[@]}"; do
    if [ -z "$SERVICE" ]; then
        echo "Service name not set, skipping."
        continue
    fi
    if gcloud run services describe $SERVICE --project=$GOOGLE_CLOUD_PROJECT --region=$GOOGLE_CLOUD_LOCATION &> /dev/null; then
        echo "Deleting Cloud Run service: $SERVICE..."
        gcloud run services delete $SERVICE --project=$GOOGLE_CLOUD_PROJECT --region=$GOOGLE_CLOUD_LOCATION --quiet
    else
        echo "Cloud Run service: $SERVICE not found, skipping."
    fi
done

# --- Delete Vertex AI Agent Engines ---
echo "
--- Deleting Vertex AI Agent Engines ---"
AGENT_IDS=("$COCKTAIL_AGENT_ENGINE_ID" "$WEATHER_AGENT_ENGINE_ID" "$HOSTING_AGENT_ENGINE_ID")
for AGENT_ID in "${AGENT_IDS[@]}"; do
    if [ ! -z "$AGENT_ID" ]; then
        # Get a bearer token for authentication
        TOKEN=$(gcloud auth print-access-token)

        # Check if the Agent Engine exists
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET \
            -H "Authorization: Bearer $TOKEN" \
            "https://aiplatform.googleapis.com/v1/projects/$GOOGLE_CLOUD_PROJECT/locations/$GOOGLE_CLOUD_LOCATION/reasoningEngines/$AGENT_ID")

        if [ "$HTTP_STATUS" -eq 200 ]; then
            echo "Deleting Agent Engine: $AGENT_ID..."
            # Delete the Agent Engine
            curl -s -X DELETE \
                -H "Authorization: Bearer $TOKEN" \
                "https://aiplatform.googleapis.com/v1/projects/$GOOGLE_CLOUD_PROJECT/locations/$GOOGLE_CLOUD_LOCATION/reasoningEngines/$AGENT_ID?force=true"
            echo "Agent Engine: $AGENT_ID deleted."
        elif [ "$HTTP_STATUS" -eq 404 ]; then
            echo "Agent Engine: $AGENT_ID not found, skipping."
        else
            echo "Error checking Agent Engine: $AGENT_ID. HTTP Status: $HTTP_STATUS"
        fi
    else
        echo "Agent Engine ID not set, skipping."
    fi
done

# --- Delete GCS Bucket ---
echo "
--- Deleting GCS Bucket ---"
if [ ! -z "$BUCKET_NAME" ]; then
    if gsutil ls -b gs://$BUCKET_NAME &> /dev/null; then
        echo "Deleting GCS Bucket: $BUCKET_NAME..."
        gsutil rm -r gs://$BUCKET_NAME
    else
        echo "GCS Bucket: $BUCKET_NAME not found, skipping."
    fi
else
    echo "BUCKET_NAME not found in .env file, skipping bucket deletion."
fi

echo "
Cleanup complete."