#!/bin/bash

# Activate the virtual environment
source .venv/bin/activate

# Load environment variables from .env file
set -a
source .env
set +a

# Deploy each agent
echo "Deploying Cocktail Agent..."
python deploy_cocktail_agent.py

echo "Deploying Weather Agent..."
python deploy_weather_agent.py

echo "Deploying Hosting Agent..."
python deploy_hosting_agent.py

echo "All agents deployed."

echo "Granting Agent Engine Service Agent Cloud Run Invoker"    
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com"  --role="roles/run.invoker"

#a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents
#projects/997110692467/locations/us-central1/reasoningEngines/3132240346696646656