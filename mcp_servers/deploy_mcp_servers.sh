#!/bin/bash
set -e

# This script deploys both the Cocktail and Weather MCP Servers to Google Cloud Run.
# It sources the central .env file from the project root for configuration.
# After deployment, it retrieves the service URLs and updates the .env file.

# Determine the project root directory, assuming this script is in a subdirectory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Load environment variables from the root .env file
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "Error: .env file not found in the project root. Please run the configure.sh script first."
    exit 1
fi

# --- IAM Permission Setup for MCP Server Deployment ---
echo "--- Ensuring necessary IAM roles for MCP Server deployment ---"

# Get the project number from the project ID
PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format="value(projectNumber)")

# Construct the default compute service account email
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Target Service Account for MCP Deployment: $SERVICE_ACCOUNT"

# Grant roles necessary for building, pushing, and deploying Cloud Run services.
# These commands are idempotent.
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/artifactregistry.writer" \
    --condition=None

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/run.admin" \
    --condition=None

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/storage.objectAdmin" \
    --condition=None # For Cloud Build artifacts

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/iam.serviceAccountUser" \
    --condition=None # To allow acting as the runtime service account

echo "--- IAM roles for MCP deployment are set ---"
# --- End of IAM Setup ---


# --- Function to deploy a service in the background ---
deploy_service() {
    local SERVICE_NAME=$1
    local SOURCE_DIR=$2

    echo "--- Starting deployment for $SERVICE_NAME ---"
    gcloud run deploy "$SERVICE_NAME" \
      --source "$SOURCE_DIR" \
      --region "$GOOGLE_CLOUD_LOCATION" \
      --project "$GOOGLE_CLOUD_PROJECT" \
      --memory 4G \
      --min-instances=1 \
      --no-allow-unauthenticated &
}

# --- Function to fetch URL and update .env file ---
fetch_and_update() {
    local SERVICE_NAME=$1
    local ENV_VAR_NAME=$2

    echo "--- Constructing URL for $SERVICE_NAME ---"
    SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${GOOGLE_CLOUD_LOCATION}.run.app/mcp/"

    echo "Service URL for $SERVICE_NAME: $SERVICE_URL"

    echo "--- Updating .env file with $SERVICE_NAME URL ---"
    # Use a temporary file for sed to ensure compatibility across different sed versions (e.g., macOS vs. Linux)
    sed -i.bak "s|^$ENV_VAR_NAME=.*|$ENV_VAR_NAME=\"$SERVICE_URL\"|" "$PROJECT_ROOT/.env"
    rm "$PROJECT_ROOT/.env.bak"

    echo "Successfully updated $ENV_VAR_NAME in the .env file."
    echo ""
}

# --- Deploy Services in Parallel ---
deploy_service "cocktail-mcp-server" "$SCRIPT_DIR/cocktail_mcp_server"
deploy_service "weather-remote-mcp-server" "$SCRIPT_DIR/weather_mcp_server"

echo "--- Waiting for deployments to complete ---"
wait

# --- Fetch URLs and Update .env File ---
fetch_and_update "cocktail-mcp-server" "CT_MCP_SERVER_URL"
fetch_and_update "weather-remote-mcp-server" "WEA_MCP_SERVER_URL"

echo "✅ Both MCP servers have been deployed and the .env file has been updated."
