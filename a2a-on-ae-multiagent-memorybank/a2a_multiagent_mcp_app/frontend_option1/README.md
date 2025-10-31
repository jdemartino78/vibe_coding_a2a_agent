# A2A Multi-Agent Frontend

> **Note**: For step-by-step setup and deployment instructions, please refer to the main `README.md` file in the project root. This document provides additional context on the frontend application.

This is the frontend for the A2A Multi-Agent on Agent Engine application.

> **⚠️ DISCLAIMER: THIS IS NOT AN OFFICIALLY SUPPORTED GOOGLE PRODUCT. THIS PROJECT IS INTENDED FOR DEMONSTRATION PURPOSES ONLY. IT IS NOT INTENDED FOR USE IN A PRODUCTION ENVIRONMENT.**

## Component Guide

### Prerequisites

This frontend requires a Google Cloud project with billing enabled, the `gcloud` SDK, and the `uv` Python package manager.

### Environment Variables

A `.env` file is used to configure the `PROJECT_ID`, `PROJECT_NUMBER`, and `AGENT_ENGINE_ID`. An example is provided in `.env.example`.

### Execution

The `deploy_frontend.sh` script can be used to run the application locally. When run with the `--mode local` flag, it starts a Gradio server available at `http://127.0.0.1:8080`.

### Deployment

The `deploy_frontend.sh` script can also deploy the application to Cloud Run using the `--mode cloudrun` flag. The script handles building the container image, deploying the service, and setting up the necessary environment variables and IAM permissions.