# Set Up MCP Server Using Cloud Run

This guide walks you through deploying the Cocktail MCP server to Google Cloud Run.

## Environment Setup

Before deploying the service, you need to set up your environment variables. The `setup_env.sh` script is provided to simplify this process. 

```bash
source ../setup_env.sh
```

This script will set the `PROJECT_ID`, `PROJECT_NUMBER`, and `LOCATION` environment variables.

## Deployment

To deploy the Cocktail MCP server, execute the following command:

```bash
../deploy_cocktail.sh
```

This script will handle the entire deployment process, including:

-   Building the container image.
-   Deploying the service to Cloud Run.
-   Setting up the necessary environment variables.
-   Granting IAM permissions to the Agent Engine service account.