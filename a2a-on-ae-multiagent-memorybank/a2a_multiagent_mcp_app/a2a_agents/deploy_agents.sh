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
