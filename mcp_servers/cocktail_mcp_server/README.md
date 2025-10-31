# Set Up MCP Server Using Cloud Run

> **Note**: For step-by-step setup and deployment instructions, please refer to the main `README.md` file in the project root. This document provides additional context on the Cocktail MCP server.

This guide walks you through deploying the Cocktail MCP server to Google Cloud Run.

## Component Guide

### Environment Setup

The `setup_env.sh` script in the parent `mcp_servers` directory is used to set the `PROJECT_ID`, `PROJECT_NUMBER`, and `LOCATION` environment variables.

### Deployment

The `deploy_cocktail.sh` script in the parent `mcp_servers` directory handles the deployment process. It builds the container image, deploys the service to Cloud Run, and grants the necessary IAM permissions to the Agent Engine service account.