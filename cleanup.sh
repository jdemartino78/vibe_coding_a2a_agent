#!/bin/bash

# This script deletes all the resources created during the training session.

# --- Load Environment Variables ---
echo "Loading environment variables..."

# Source the main setup file to get PROJECT_ID and LOCATION
if [ -f "mcp_servers/setup_env.sh" ]; then
    source "mcp_servers/setup_env.sh"
else
    echo "Error: mcp_servers/setup_env.sh not found. Please ensure you are running this script from the project root."
    exit 1
fi

# Source the agents .env file to get agent and bucket details
if [ -f "a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env" ]; then
    export $(sed -e '/^ *#/d' -e '/^$/d' -e 's/ *= */=/' -e "s/'//g" -e 's/"//g' a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env | xargs)
else
    echo "Warning: a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env not found. Some resources may not be deleted."
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
SERVICES=("cocktail-mcp-server" "weather-remote-mcp-server" "a2a-server-frontend")
for SERVICE in "${SERVICES[@]}"; do
    if gcloud run services describe $SERVICE --project=$PROJECT_ID --region=$LOCATION &> /dev/null; then
        echo "Deleting Cloud Run service: $SERVICE..."
        gcloud run services delete $SERVICE --project=$PROJECT_ID --region=$LOCATION --quiet
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
        if gcloud ai reasoning-engines describe $AGENT_ID --project=$PROJECT_ID --region=$LOCATION &> /dev/null; then
            echo "Deleting Agent Engine: $AGENT_ID..."
            gcloud ai reasoning-engines delete $AGENT_ID --project=$PROJECT_ID --region=$LOCATION --quiet
        else
            echo "Agent Engine: $AGENT_ID not found, skipping."
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