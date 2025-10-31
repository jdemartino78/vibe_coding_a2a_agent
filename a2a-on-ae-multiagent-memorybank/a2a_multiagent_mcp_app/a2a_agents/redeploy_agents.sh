#!/bin/bash

# Navigate to the agents directory
cd /usr/local/google/home/demart/vertex-ai-agents/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/

# Activate the virtual environment
source /usr/local/google/home/demart/vertex-ai-agents/a2a-on-ae-multiagent-memorybank/.venv/bin/activate

# Re-deploy each agent
echo "Deploying Cocktail Agent..."
python deploy_cocktail_agent.py

echo "Deploying Weather Agent..."
python deploy_weather_agent.py

echo "Deploying Hosting Agent..."
python deploy_hosting_agent.py

echo "All agents re-deployed."
