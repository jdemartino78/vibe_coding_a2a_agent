#!/bin/bash

# Prompt for PROJECT_ID and PROJECT_NUMBER
read -p "Enter your Google Cloud Project ID: " PROJECT_ID
read -p "Enter your Google Cloud Project Number: " PROJECT_NUMBER

# Create agent .env file and replace placeholders
AGENT_ENV_EXAMPLE="a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env.example"
AGENT_ENV="a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env"
cp "$AGENT_ENV_EXAMPLE" "$AGENT_ENV"
sed -i "s/PROJECT_ID=.*/PROJECT_ID=$PROJECT_ID/" "$AGENT_ENV"
sed -i "s/PROJECT_NUMBER=.*/PROJECT_NUMBER=$PROJECT_NUMBER/" "$AGENT_ENV"

# Create frontend .env file and replace placeholders
FRONTEND_ENV_EXAMPLE="a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.env.example"
FRONTEND_ENV="a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.env"
cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV"
sed -i "s/PROJECT_ID=.*/PROJECT_ID=$PROJECT_ID/" "$FRONTEND_ENV"
sed -i "s/PROJECT_NUMBER=.*/PROJECT_NUMBER=$PROJECT_NUMBER/" "$FRONTEND_ENV"

# Update mcp_servers/setup_env.sh with project details
SETUP_ENV_SH="mcp_servers/setup_env.sh"
sed -i "s/PROJECT_ID=.*/PROJECT_ID=$PROJECT_ID/" "$SETUP_ENV_SH"
sed -i "s/PROJECT_NUMBER=.*/PROJECT_NUMBER=$PROJECT_NUMBER/" "$SETUP_ENV_SH"

echo "Configuration complete. Your project details have been set in all necessary files."
