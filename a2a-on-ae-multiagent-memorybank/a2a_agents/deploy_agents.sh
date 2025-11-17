#!/bin/bash

# This script deploys the Cocktail, Weather, and Orchestrator agents.
# It sources the central .env file from the project root for configuration.
# It also ensures the default service account has the necessary IAM roles.

set -e

# Determine the project root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

# Activate the virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Change to the agents directory to ensure correct path resolution
cd "$SCRIPT_DIR"

# Load environment variables from the root .env file
set -a
source "$PROJECT_ROOT/.env"
set +a


# Deploy specialized agents in parallel
echo "Deploying Cocktail Agent in the background..."
python -m specialized_agents.cocktail_agent.deploy_cocktail_agent &

echo "Deploying Weather Agent in the background..."
python -m specialized_agents.weather_agent.deploy_weather_agent &

# Wait for both background jobs to complete
echo "Waiting for specialized agents to finish deploying..."
wait
echo "Both specialized agents have been deployed."

# Re-source the environment file to pick up the newly created agent URLs
set -a
source "$PROJECT_ROOT/.env"
set +a

echo "Deploying Orchestrator Agent..."
python -m orchestrator.deploy_orchestrator

echo "All agents deployed."

# --- IAM Permission Setup ---
echo "Ensuring necessary IAM roles for Agent Engine and its service account..."

# Get the project number from the project ID
PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format="value(projectNumber)")

# Construct the default compute service account email (for the agent's code)
AGENT_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Construct the Agent Engine Service Agent email (for the Agent Engine itself)
AE_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

echo "Target Agent Service Account: $AGENT_SERVICE_ACCOUNT"
echo "Target Agent Engine Service Agent: $AE_SERVICE_AGENT"

# Grant necessary roles to the AGENT_SERVICE_ACCOUNT. The commands are idempotent.
echo "Granting Secret Manager Secret Accessor role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AGENT_SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

echo "Granting Cloud AlloyDB Client role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AGENT_SERVICE_ACCOUNT" \
    --role="roles/alloydb.client" \
    --condition=None

echo "Granting Vertex AI User role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AGENT_SERVICE_ACCOUNT" \
    --role="roles/aiplatform.user" \
    --condition=None

# Grant necessary roles to the AE_SERVICE_AGENT. The commands are idempotent.
echo "Granting Cloud Run Invoker role to Agent Engine Service Agent..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/run.invoker" \
    --condition=None

echo "All IAM roles are set."
# --- End of IAM Setup ---
