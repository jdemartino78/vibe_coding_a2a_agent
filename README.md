# Vibe Coding: Building an A2A Agentic System (Live Training)

> **⚠️ DISCLAIMER**: THIS DEMO IS INTENDED FOR DEMONSTRATION PURPOSES ONLY. IT IS NOT INTENDED FOR USE IN A PRODUCTION ENVIRONMENT.
>
> **⚠️ Important**: A2A is in active development (WIP) thus, in the near future there might be changes that are different from what demonstrated here.
>
> **⚠️ Important**: Please run this lab in **Cloud Shell** to ensure you have the proper permissions.

## Overview
In this 1-hour session, we will build and deploy a multi-agent system using the A2A (Agent-to-Agent) protocol. This system will include a 'Hosting' agent that communicates with 'Weather' and 'Cocktail' agents to fulfill user requests.

## Learning Objectives
By the end of this session, you will be able to:
- Understand the core concepts of the A2A protocol.
- Deploy a tool-using agent (ADK) to Agent Engine.
- Implement agent-to-agent communication.
- Understand the architecture of a multi-agent system with a hosting agent and specialized agents.
- Deploy MCP servers on Cloud Run.

## Prerequisites
- `gcloud` CLI
- `uv` (Python package manager)
- Install `uv` by following the instructions at https://github.com/astral-sh/uv#installation. For example, on Linux:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- Python 3.12+
- Docker
- A Google Cloud Project with billing enabled.
- The following Google Cloud services enabled:
    - Cloud Run
    - Vertex AI
    - Cloud Build
    - Artifact Registry

## Step-by-Step Instructions

### 1. Environment Setup

First, we need to configure the environment variables for our project. We've provided a script to simplify this process.

1.  **Configure Project Details:**
    Copy the example configuration script and edit it with your GCP project details:
    ```bash
    cp configure_project.sh.example configure_project.sh
    # Open configure_project.sh and replace "your-gcp-project-id" and "your-gcp-project-number" with your actual values.
    ```

2.  **Make Configuration Script Executable:**
    ```bash
    chmod +x configure_project.sh
    ```

3.  **Run Configuration Script:**
    Execute the script to set up the environment variables in the necessary files:
    ```bash
    ./configure_project.sh
    ```

3.  **Source Environment Variables:**
    Source the `setup_env.sh` script to export the variables into your shell session:
    ```bash
    source mcp_servers/setup_env.sh
    ```


### 2. Deploy Tooling Servers (MCP Servers)

We are first deploying our MCP Servers. These are not agents. They are simple Cloud Run services that expose tools (like the Cocktail and Weather APIs) for our agents to use.

These servers provide the tools that our agents will use (e.g., weather and cocktail APIs).

1.  **Authenticate gcloud:**
    ```bash
    gcloud auth login
    ```

2.  **Deploy the Cocktail MCP Server:**
    ```bash
    ./mcp_servers/deploy_cocktail.sh
    ```
    After the deployment is complete, copy the service URL from the output.

2.  **Deploy the Weather MCP Server:**
    ```bash
    ./mcp_servers/deploy_weather.sh
    ```
    After the deployment is complete, copy the service URL from the output.

3.  **Update Agents `.env` file:**
    Open the `.env` file located at `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env` and paste the URLs you copied into the `CT_MCP_SERVER_URL` and `WEA_MCP_SERVER_URL` fields.

### 3. Deploy A2A Agents

Now we deploy the agents. The HostingAgent is our Orchestrator. It will find the CocktailAgent and WeatherAgent by reading their Agent Card, which is the 'business card' that describes what an agent can do.

Now, we will deploy our three agents to Vertex AI Agent Engine.

1.  **Create and Activate Virtual Environment & Install Agent Dependencies:**
    Navigate to the agents directory and create a virtual environment, then install dependencies:
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents && uv venv && source .venv/bin/activate && uv sync)
    ```

2.  **Deploy All Agents:**
    Ensure your `.env` file in `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/` is correctly filled out with your `PROJECT_ID`, `PROJECT_NUMBER`, `GOOGLE_API_KEY`, and `BUCKET_NAME`.
    Then, run the `deploy_agents.sh` script to deploy all agents:
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents && ./deploy_agents.sh)
    ```
    This script will deploy the agents and save their URLs and Engine IDs in the `.env` file.

3.  **Update Frontend `.env` file:**
    Copy the `HOSTING_AGENT_ENGINE_ID` from `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env` and paste it into the `.env` file in `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.env`.

### 4. Run the Frontend

This Gradio app is our A2A Client. It only knows about the HostingAgent. We will ask it for a cocktail, and it will orchestrate the other agents to get the answer.

We will run the Gradio frontend locally to interact with our agent system.

1.  **Run the local deployment script:**
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1 && ./deploy_frontend.sh --mode local)
    ```

#### Deploying to Cloud Run (Optional)
You can also deploy the frontend to Cloud Run.

1.  **Run the Cloud Run deployment script:**
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1 && ./deploy_frontend.sh --mode cloudrun)
    ```
    This script will build the container image, deploy the service to Cloud Run, and set up the necessary IAM permissions. Once deployed, you can access the frontend at the URL provided in the output.

### 5. Test the System

Open your web browser and go to `http://127.0.0.1:8080`. You can now chat with your multi-agent system!

Try asking it:
- `Please get weather forecast for New York`
- `Please list a random cocktail`
- `What ingredients are in a Margarita?`

## What We Just Built
Congratulations! You have successfully built a multi-agent system.
- A **Gradio Frontend** (our client)
- Talked to a **Hosting Agent** (our orchestrator)
- Which discovered and called two **Specialized Agents** (Cocktail and Weather)
- Which in turn called their own **Tools** (the MCP Servers)

Here is the architecture you deployed:
![architecture](a2a-on-ae-multiagent-memorybank/asset/a2a_ae_diagram.png)

## Key Files

-   `mcp_servers/`: Contains the simple 'tool' servers (Cocktail, Weather) that our agents will call. These are deployed as Cloud Run services.
-   `a2a-on-ae-multiagent-memorybank/`: Contains the main project components:
    -   `a2a_agents/`: Holds the source code for the three agents (Hosting, Cocktail, and Weather) and their deployment scripts.
    -   `frontend_option1/`: A Gradio-based web interface for interacting with the deployed agents.

## Learn More
- [Agent Development Kit (ADK)](https://github.com/GoogleCloudPlatform/agent-development-kit)
- [Agent to Agent (A2A) Protocol](https://github.com/GoogleCloudPlatform/agent-development-kit/blob/main/docs/a2a.md)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/agent-engine/overview)

## Cleanup
To avoid incurring future charges, you can delete the resources created during this lab by running the cleanup script.

```bash
./cleanup.sh
```
This script will:
- Delete the Cloud Run services for the MCP servers and the frontend.
- Delete the Vertex AI Agent Engine agents.
- Delete the GCS bucket used for staging.
