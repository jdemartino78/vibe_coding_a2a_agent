#!/bin/bash

# deploy_frontend.sh
# This script automates the deployment of the A2A Multi-Agent Frontend.
# It supports deployment to Google Cloud Run or running locally.

# --- Usage ---
# To run locally: ./deploy_frontend.sh --mode local
# To deploy to Cloud Run (default): ./deploy_frontend.sh --mode cloudrun
# For help: ./deploy_frontend.sh --mode help

# Determine the project root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../../.."

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Default deployment mode is local.
DEPLOY_MODE="local"

# --- Command Line Argument Parsing ---
# Use -m or --mode to specify deployment mode: 'local', 'cloudrun', or 'help'.
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--mode)
      DEPLOY_MODE="$2"
      shift 2
      ;;
    -m=*|--mode=*)
      DEPLOY_MODE="${1#*=}"
      shift 1
      ;;
    *)
      # unknown option
      shift
      ;;
  esac
done

# Activate the main virtual environment
source .venv/bin/activate

# source /usr/local/google/home/demart/vertex-ai-agents/a2a-on-ae-multiagent-memorybank/.venv/bin/activate

# --- Execute based on Deployment Mode ---
case "$DEPLOY_MODE" in
    "local")
        echo "Running frontend locally..."
        # To run locally, ensure you have 'uv' installed and the necessary Python dependencies.
        uv run main.py
        if [ $? -eq 0 ]; then
            echo "Frontend running locally. Access at http://127.0.0.1:8080"
        else
            echo "Error: Local frontend execution failed."
            exit 1
        fi
        ;;
    "cloudrun")
        # --- Validate Essential Environment Variables (for Cloud Run mode) ---
        # Ensure that the required variables are present if deploying to Cloud Run.
        if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
            echo "Error: GOOGLE_CLOUD_PROJECT is not set in the .env file."
            exit 1
        fi

        if [ -z "$PROJECT_NUMBER" ]; then
            echo "Error: PROJECT_NUMBER is not set in the .env file."
            exit 1
        fi

        if [ -z "$HOSTING_AGENT_ENGINE_ID" ]; then
            echo "Error: HOSTING_AGENT_ENGINE_ID is not set in the .env file."
            exit 1
        fi

        echo "Project ID: $GOOGLE_CLOUD_PROJECT"
        echo "Project Number: $PROJECT_NUMBER"
        echo "Location: $GOOGLE_CLOUD_LOCATION"
        echo "Agent Engine ID: $HOSTING_AGENT_ENGINE_ID"
        echo "Cloud Run Service Name: $FRONTEND_SERVICE_NAME"

        echo "Deploying frontend service to Cloud Run..."
        gcloud run deploy "$FRONTEND_SERVICE_NAME" \
          --source . \
          --region "$GOOGLE_CLOUD_LOCATION" \
          --project "$GOOGLE_CLOUD_PROJECT" \
          --memory 2G \
          --no-allow-unauthenticated \
          --update-env-vars=PROJECT_ID="$GOOGLE_CLOUD_PROJECT",HOSTING_AGENT_ENGINE_ID="$HOSTING_AGENT_ENGINE_ID",PROJECT_NUMBER="$PROJECT_NUMBER"

        if [ $? -eq 0 ]; then
            echo "Frontend service deployed successfully to Cloud Run."
        else
            echo "Error: Cloud Run deployment failed."
            exit 1
        fi

        echo "Authorizing Cloud Run service account..."
        gcloud run services add-iam-policy-binding "$FRONTEND_SERVICE_NAME" \
            --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/run.invoker" \
            --region="$GOOGLE_CLOUD_LOCATION" \
            --project="$GOOGLE_CLOUD_PROJECT"

        if [ $? -eq 0 ]; then
            echo "Cloud Run service account authorized successfully."
        else
            echo "Error: Cloud Run service account authorization failed."
            exit 1
        fi

        echo "Frontend deployment and authorization complete."
        echo "You can now access your Cloud Run service. Check the Cloud Run console for the URL."
        echo "For temporary testing, you can also authorize all users with the following command:"
        echo "gcloud run services add-iam-policy-binding \"$SERVICE_NAME\" --member=\"allUsers\" --role=\"roles/run.invoker\" --region=\"$LOCATION\" --project=\"$PROJECT_ID\""
        ;;
    "help")
        echo "Usage: ./deploy_frontend.sh [--mode <local|cloudrun|help>]"
        echo "  --mode local: Runs the frontend application locally (default)."
        echo "  --mode cloudrun: Deploys the frontend application to Google Cloud Run."
        echo "  --mode help: Displays this help message."
        ;;
    *)
        echo "Error: Invalid deployment mode specified. Use 'local', 'cloudrun', or 'help'."
        exit 1
        ;;
esac