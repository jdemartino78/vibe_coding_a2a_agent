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
    - Telemetry API 

## Step-by-Step Instructions

### 0. Authentication

Before proceeding, ensure your `gcloud` CLI is authenticated and configured for your Google Cloud project.

1.  **Authenticate with Google Cloud:**
    Log in to your Google Cloud account:
    ```bash
    gcloud auth login
    ```

2.  **Set Application Default Credentials:**
    This command sets up credentials for applications to use Google Cloud APIs:
    ```bash
    gcloud auth application-default login
    ```

3.  **Set Quota Project:**
    Configure the project to be used for billing and quota management:
    ```bash
    gcloud auth application-default set-quota-project $GOOGLE_CLOUD_PROJECT
    ```
    **Note:** `$GOOGLE_CLOUD_PROJECT` will be set after running `./configure.sh` in the next step.

### 1. Environment Setup

Run the configuration script. It will prompt you for your Google Cloud Project ID, Project Number, and a **unique Google Cloud Storage Bucket Name**. This will create a central `.env` file in the project root with all necessary environment variables.
```bash
./configure.sh
```

### 2. Grant IAM Permissions
The following IAM roles are required for the Agent Engine Service Agent and the Compute Engine Service Account to interact correctly with Vertex AI and Cloud Run.

*   **Agent Engine Service Agent:**
    *   `roles/aiplatform.user` (Vertex AI User)
    *   `roles/run.invoker` (Cloud Run Invoker)

*   **Compute Engine Service Account:**
    *   `roles/aiplatform.user` (Vertex AI User)
    *   `roles/run.invoker` (Cloud Run Invoker)
    *   `roles/artifactregistry.writer` (Artifact Registry Writer)

Run the following commands to grant these permissions. The script will use the `GOOGLE_CLOUD_PROJECT` and `PROJECT_NUMBER` variables from the `.env` file you just created.

```bash
# Grant Vertex AI User and Cloud Run Invoker to the Agent Engine Service Account
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Grant Vertex AI User, Cloud Run Invoker, and Artifact Registry Writer to the Compute Engine Service Account
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
```


### 2. Deploy Tooling Servers (Model Context Protocol Servers)

Next, deploy the two MCP (Model Context Protocol) servers. These are the backend tools (Cocktail and Weather APIs) that your agents will call.

1.  **Deploy the Cocktail MCP Server**

    Run the following command from the project root:
    ```bash
    ./mcp_servers/deploy_cocktail.sh
    ```
    After the deployment is complete, copy the **Service URL** from the output. Open the `.env` file in the **project root** and paste the URL into the `CT_MCP_SERVER_URL` variable. **Crucially, append `/mcp` to the end of the URL.**

2.  **Deploy the Weather MCP Server**

    Run the following command from the project root:
    ```bash
    ./mcp_servers/deploy_weather.sh
    ```
    Again, copy the **Service URL** from the output. Open the `.env` file in the **project root** and paste this URL into the `WEA_MCP_SERVER_URL` variable. **Crucially, append `/mcp` to the end of the URL.**

Your `.env` file in the **project root** should now have the URLs populated, similar to this:
```env
# ... (other variables)
CT_MCP_SERVER_URL="https://cocktail-mcp-server-....a.run.app/mcp/"
WEA_MCP_SERVER_URL="https://weather-remote-mcp-server-....a.run.app/mcp/"
# ... (other variables)
```

### 3. Deploy A2A Agents

Now we deploy the agents. The HostingAgent is our Orchestrator. It will find the CocktailAgent and WeatherAgent by reading their Agent Card, which is the 'business card' that describes what an agent can do.

Now, we will deploy our three agents to Vertex AI Agent Engine.

1.  **Create and Activate Virtual Environment & Install Agent Dependencies:**
    Navigate to the agents directory and create a virtual environment, then install dependencies. **Ensure `google-cloud-aiplatform` is at least version `1.127.0` to avoid `TypeError: _default_instrumentor_builder() got an unexpected keyword argument 'enable_tracing'`.**
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents && uv venv && source .venv/bin/activate && uv sync --python 3.12)
    ```

2.  **Deploy All Agents:**
    Run the `deploy_agents.sh` script to deploy all agents:
    ```bash
    (cd a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents && ./deploy_agents.sh)
    ```
    This script will deploy the agents and save their URLs and Engine IDs in the root `.env` file.

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

TODO: 
- deploy_frontend script (local vs cloudrun) not reading in correctly - always defaults to local 
TODO: 
- debug error An error occurred: 'AgentEngine' object has no attribute 'handle_authenticated_agent_card'
Traceback (most recent call last):
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/main.py", line 142, in get_response_from_agent
    remote_a2a_agent_card = await get_agent_card(remote_a2a_agent_resource_name)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/main.py", line 127, in get_agent_card
    return await remote_a2a_agent.handle_authenticated_agent_card()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.venv/lib/python3.13/site-packages/pydantic/main.py", line 991, in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
AttributeError: 'AgentEngine' object has no attribute 'handle_authenticated_agent_card'
2025-11-06 19:29:57,992 - __main__ - INFO - Fetching agent card...
2025-11-06 19:29:58,284 - httpx - INFO - HTTP Request: GET https://us-central1-aiplatform.googleapis.com/v1beta1/projects/997110692467/locations/us-central1/reasoningEngines/ "HTTP/1.1 200 OK"
2025-11-06 19:29:58,285 - __main__ - ERROR - Error in get_response_from_agent (Type: AttributeError): 'AgentEngine' object has no attribute 'handle_authenticated_agent_card'
Traceback (most recent call last):
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/main.py", line 142, in get_response_from_agent
    remote_a2a_agent_card = await get_agent_card(remote_a2a_agent_resource_name)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/main.py", line 127, in get_agent_card
    return await remote_a2a_agent.handle_authenticated_agent_card()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lizraymond/vibe_coding_a2a_agent/a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/.venv/lib/python3.13/site-packages/pydantic/main.py", line 991, in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
AttributeError: 'AgentEngine' object has no attribute 'handle_authenticated_agent_card'






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
**Note:** If you encounter errors deleting Agent Engines due to child resources, you may need to modify `cleanup.sh` to include `?force=true` in the `curl -X DELETE` command for reasoning engines.
