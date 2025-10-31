# Vibe Coding: Building an A2A Agentic System (Live Training)

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

First, we need to configure the environment variables for our project.

1.  **Configure MCP Servers Environment:**
    Open the file `mcp_servers/setup_env.sh` and replace the placeholder values for `PROJECT_ID` and `PROJECT_NUMBER` with your Google Cloud project details.

2.  **Configure A2A Agents Environment:**
    Navigate to the agents directory and copy the example `.env` file:
    ```bash
    cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents
    cp .env.example .env
    ```
    Open the newly created `.env` file and fill in your `PROJECT_ID`, `PROJECT_NUMBER`, and `BUCKET_NAME`. You will fill in the server and agent URLs in the next steps.

3.  **Configure Frontend Environment:**
    Navigate to the frontend directory and copy the example `.env` file:
    ```bash
    cd ../frontend_option1
    cp .env.example .env
    ```
    Open the newly created `.env` file and fill in your `PROJECT_ID` and `PROJECT_NUMBER`. You will fill in the `HOSTING_AGENT_ENGINE_ID` later.

4.  **Source Environment Variables:**
    Go back to the root of the project and source the `setup_env.sh` script to export the variables into your shell session:
    ```bash
    cd ../../../..
    source mcp_servers/setup_env.sh
    ```

### 2. Deploy Tooling Servers (MCP Servers)

These servers provide the tools that our agents will use (e.g., weather and cocktail APIs).

1.  **Deploy the Cocktail MCP Server:**
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

Now, we will deploy our three agents to Vertex AI Agent Engine.

1.  **Navigate to the agents directory and install dependencies:**
    ```bash
    cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents
    uv sync
    ```

2.  **Deploy the Cocktail Agent:**
    ```bash
    python deploy_cocktail_agent.py
    ```
    This script will deploy the agent and save its URL and Engine ID in the `.env` file.

3.  **Deploy the Weather Agent:**
    ```bash
    python deploy_weather_agent.py
    ```
    This script will deploy the agent and save its URL in the `.env` file.

4.  **Deploy the Hosting Agent:**
    ```bash
    python deploy_hosting_agent.py
    ```
    This script deploys the main hosting agent that will orchestrate the other two. It will also save its URL and Engine ID in the `.env` file.

5.  **Update Frontend `.env` file:**
    Copy the `HOSTING_AGENT_ENGINE_ID` from `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/.env` and paste it into the `.env` file in `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.env`.

### 4. Run the Frontend

We will run the Gradio frontend locally to interact with our agent system.

1.  **Navigate to the frontend directory:**
    ```bash
    cd ../frontend_option1
    ```

2.  **Run the local deployment script:**
    ```bash
    ./deploy_frontend.sh --mode local
    ```

### 5. Test the System

Open your web browser and go to `http://127.0.0.1:8080`. You can now chat with your multi-agent system!

Try asking it:
- `Please get weather forecast for New York`
- `Please list a random cocktail`
- `What ingredients are in a Margarita?`

## Key Files

-   `mcp_servers/`: Contains the simple 'tool' servers (Cocktail, Weather) that our agents will call. These are deployed as Cloud Run services.
-   `a2a-on-ae-multiagent-memorybank/`: Contains the main project components:
    -   `a2a_agents/`: Holds the source code for the three agents (Hosting, Cocktail, and Weather) and their deployment scripts.
    -   `frontend_option1/`: A Gradio-based web interface for interacting with the deployed agents.

## Learn More
- [Agent Development Kit (ADK)](https://github.com/GoogleCloudPlatform/agent-development-kit)
- [Agent to Agent (A2A) Protocol](https://github.com/GoogleCloudPlatform/agent-development-kit/blob/main/docs/a2a.md)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/agent-engine/overview)
