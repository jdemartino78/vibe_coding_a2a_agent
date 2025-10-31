# A2A Multi-Agent Frontend

This is the frontend for the A2A Multi-Agent on Agent Engine application.

> **⚠️ DISCLAIMER: THIS IS NOT AN OFFICIALLY SUPPORTED GOOGLE PRODUCT. THIS PROJECT IS INTENDED FOR DEMONSTRATION PURPOSES ONLY. IT IS NOT INTENDED FOR USE IN A PRODUCTION ENVIRONMENT.**

## Prerequisites

Before you begin, ensure you have the following:

*   A Google Cloud project with billing enabled.
*   The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated.
*   The `uv` Python package manager installed.

## Getting Started

### 1. Create the `.env` file

Create a `.env` file by copying the `.env.example` file.

```bash
cp .env.example .env
```

You will need to fill in the values for `PROJECT_ID`, `PROJECT_NUMBER`, and `AGENT_ENGINE_ID` in the `.env` file. You can get these values from your Google Cloud project.

### 2. Execution

To run the application locally, execute the following command:

```bash
./deploy_frontend.sh --mode local
```

The application will be available at `http://127.0.0.1:8080`.

## Deployment

To deploy the application to Cloud Run, execute the following command:

```bash
./deploy_frontend.sh --mode cloudrun
```

The script will handle the entire deployment process, including:

-   Building the container image.
-   Deploying the service to Cloud Run.
-   Setting up the necessary environment variables.
-   Authorizing the Cloud Run service account.