#!/bin/bash

# This script initializes the project's environment configuration.
# It creates a single .env file from the .env.example template
# and populates it with your specific Google Cloud project details.

# --- Functions ---
prompt_for_input() {
    local prompt_message=$1
    local variable_name=$2
    while [ -z "${!variable_name}" ]; do
        read -p "$prompt_message" $variable_name
    done
}

# --- Main Script ---
echo "--- Project Configuration Setup ---"

# Check if .env.example exists
if [ ! -f ".env.example" ]; then
    echo "ERROR: The .env.example file was not found in the project root."
    exit 1
fi

# Create .env from .env.example
cp .env.example .env

# Prompt for user-specific values
prompt_for_input "Enter your Google Cloud Project ID: " PROJECT_ID
prompt_for_input "Enter your Google Cloud Project Number: " PROJECT_NUMBER
prompt_for_input "Enter your unique Google Cloud Storage Bucket Name: " BUCKET_NAME

# Substitute placeholders in the new .env file
sed -i "s/your-project-id/$PROJECT_ID/g" .env
sed -i "s/your-project-number/$PROJECT_NUMBER/g" .env
sed -i "s/your-unique-bucket-name/$BUCKET_NAME/g" .env

echo ""
echo "✅ Configuration complete."
echo "The .env file has been created in the project root with your settings."
echo "You can now proceed with the deployment steps in the README."
