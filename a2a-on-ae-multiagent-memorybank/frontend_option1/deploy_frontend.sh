#!/bin/bash
set -e

# deploy_frontend.sh
# This script automates the deployment of the A2A Multi-Agent Frontend.
# It supports deployment to Google Cloud Run or running locally.

# --- Usage ---
# To run locally: ./deploy_frontend.sh --mode local
# To deploy to Cloud Run (default): ./deploy_frontend.sh --mode cloudrun
# For help: ./deploy_frontend.sh --mode help

# Determine the project root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Default deployment mode is local.
DEPLOY_MODE="local"

# --- Command Line Argument Parsing ---
# Use -m or --mode to specify deployment mode: 'local', 'cloudrun', or 'help'.
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -m|--mode)
      if [[ -n "$2" && "$2" != -* ]]; then
        DEPLOY_MODE="$2"
        shift
      else
        echo "Error: --mode requires a value (local, cloudrun, or help)."
        exit 1
      fi
      ;;
    *)
      # Unknown option or argument
      ;;
  esac
  shift
done

# Activate the main virtual environment
source .venv/bin/activate

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

        if [ -z "$ORCHESTRATOR_AGENT_ENGINE_ID" ]; then
            echo "Error: ORCHESTRATOR_AGENT_ENGINE_ID is not set in the .env file."
            exit 1
        fi

        echo "Project ID: $GOOGLE_CLOUD_PROJECT"
        echo "Project Number: $PROJECT_NUMBER"
        echo "Location: $GOOGLE_CLOUD_LOCATION"
        echo "Agent Engine ID: $ORCHESTRATOR_AGENT_ENGINE_ID"
        echo "Cloud Run Service Name: $FRONTEND_SERVICE_NAME"

        # --- Grant Necessary IAM Roles ---
        echo "Ensuring Cloud Run service account has Vertex AI User role..."
        DEFAULT_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
        gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
            --member="serviceAccount:$DEFAULT_SA" \
            --role="roles/aiplatform.user" \
            --condition=None

        echo "Deploying frontend service to Cloud Run..."
        cp ../../.env .
        gcloud run deploy "$FRONTEND_SERVICE_NAME" \
          --source . \
          --region "$GOOGLE_CLOUD_LOCATION" \
          --project "$GOOGLE_CLOUD_PROJECT" \
          --memory 2G \
          --no-allow-unauthenticated \
          --update-env-vars=PROJECT_ID="$GOOGLE_CLOUD_PROJECT",ORCHESTRATOR_AGENT_ENGINE_ID="$ORCHESTRATOR_AGENT_ENGINE_ID",PROJECT_NUMBER="$PROJECT_NUMBER",USER_ID="$USER_ID",GRADIO_TEMP_DIR="/tmp/gradio_files"

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
        echo "To access your Cloud Run service securely, you can set up a proxy:"
        echo "gcloud run services proxy $FRONTEND_SERVICE_NAME --region $GOOGLE_CLOUD_LOCATION --port 8081"
        echo "This will make the service available at http://localhost:8081."
        echo "You can also check the Cloud Run console for the public URL if you prefer direct access (ensure proper IAM roles are set for users)."
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