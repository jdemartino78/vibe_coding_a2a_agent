#!/bin/bash

# This script deploys the Cocktail, Weather, and Orchestrator agents.
# It can deploy all agents at once or individual agents using flags.
#
# Usage:
#   ./deploy_agents.sh (deploys all agents)
#   ./deploy_agents.sh --cocktail (deploys only the Cocktail agent)
#   ./deploy_agents.sh --weather (deploys only the Weather agent)
#   ./deploy_agents.sh --orchestrator (deploys only the Orchestrator agent)
#   ./deploy_agents.sh --cocktail --weather (deploys Cocktail and Weather agents)
#
# It sources the central .env file from the project root for configuration.
# It also ensures the default service account has the necessary IAM roles.

set -e

#Determine the project root directory.
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

deploy_cocktail() {
  echo "Deploying Cocktail Agent..."
  python -m specialized_agents.cocktail_agent.deploy_cocktail_agent
}

deploy_weather() {
  echo "Deploying Weather Agent..."
  python -m specialized_agents.weather_agent.deploy_weather_agent
}

deploy_orchestrator() {
  # Re-source the environment file to pick up the newly created agent URLs
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
  echo "Deploying Orchestrator Agent..."
  python -m orchestrator.deploy_orchestrator
}

if [ "$#" -eq 0 ]; then
  # No arguments, deploy all agents sequentially
  deploy_cocktail
  deploy_weather
  deploy_orchestrator
  echo "All agents deployed."
else
  # Loop through arguments and deploy specified agents
  for arg in "$@"
  do
    case $arg in
      --cocktail)
        deploy_cocktail
        ;;
      --weather)
        deploy_weather
        ;;
      --orchestrator)
        deploy_orchestrator
        ;;
      *)
        echo "Unknown option: $arg"
        exit 1
        ;;
    esac
  done
fi


# --- IAM Permission Setup ---

echo "Ensuring necessary IAM roles for Agent Engine and its service account..."

# Get the project number from the project ID
PROJECT_NUMBER=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format="value(projectNumber)")

# Construct the Agent Engine Service Agent email (for the Agent Engine itself)
AE_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

echo "Target Agent Engine Service Agent: $AE_SERVICE_AGENT"

# Grant necessary roles to the AE_SERVICE_AGENT. The commands are idempotent.
echo "Granting Secret Manager Secret Accessor role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

echo "Granting Cloud Telemetry Writer role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/telemetry.writer" \
    --condition=None


echo "Granting Cloud AlloyDB Client role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/alloydb.client" \
    --condition=None

echo "Granting Vertex AI User role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/aiplatform.user" \
    --condition=None

echo "Granting Logs Writer role to agent service account..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/logging.logWriter" \
    --condition=None

# Grant necessary roles to the AE_SERVICE_AGENT. The commands are idempotent.
echo "Granting Cloud Run Invoker role to Agent Engine Service Agent..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/run.invoker" \
    --condition=None

echo "Granting Service Usage Consumer role to Agent Engine Service Agent (for logging)..."
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:$AE_SERVICE_AGENT" \
    --role="roles/serviceusage.serviceUsageConsumer" \
    --condition=None

echo "All IAM roles are set."
# --- End of IAM Setup ---
