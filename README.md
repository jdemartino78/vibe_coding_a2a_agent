# Vibe Coding: Building a Stateful A2A Multi-Agent System

> **⚠️ DISCLAIMER**: THIS DEMO IS INTENDED FOR DEMONSTRATION PURPOSES ONLY. IT IS NOT INTENDED FOR USE IN A PRODUCTION ENVIRONMENT.
>
> **⚠️ Important**: A2A is in active development (WIP) thus, in the near future there might be changes that are different from what demonstrated here.
>
> **⚠️ Important**: Please run this lab in **Cloud Shell** to ensure you have the proper permissions.

## Overview
In this session, we will build and deploy a **stateful, production-ready multi-agent system** using the A2A (Agent-to-Agent) protocol. This system features an 'Orchestrator' agent that intelligently delegates tasks to specialized 'Weather' and 'Cocktail' agents. All agent memory, including task status and conversation history, is persisted in a robust **AlloyDB** database, ensuring the system is resilient and maintains context across interactions.

## Learning Objectives
By the end of this session, you will be able to:
- Understand the core concepts of the A2A protocol.
- Implement a persistent state management system for agents using AlloyDB.
- Understand the difference between task state, conversational state, and long-term memory.
- Deploy a tool-using agent (ADK) to Agent Engine.
- Implement secure agent-to-agent communication on Google Cloud.
- Deploy MCP (Model Context Protocol) servers on Cloud Run.

## Prerequisites
- `gcloud` CLI
- `uv` (Python package manager)
- `psql` (PostgreSQL interactive terminal)
- Python 3.12+
- Docker
- A Google Cloud Project with billing enabled.
- The following Google Cloud services enabled:
    - Cloud Run
    - Vertex AI
    - Cloud Build
    - Artifact Registry
    - **AlloyDB**
    - **Secret Manager**

## Step-by-Step Instructions

### 0. Authentication

Ensure your `gcloud` CLI is authenticated and configured for your Google Cloud project.
```bash
gcloud auth login
gcloud auth application-default login
```

### 1. Environment Setup

Run the configuration script. It will prompt you for your Project ID, Project Number, and a unique GCS Bucket Name. This creates a central `.env` file with all necessary environment variables.
```bash
./configure.sh
source .env
gcloud auth application-default set-quota-project $GOOGLE_CLOUD_PROJECT
```

### 2. Deploy the AlloyDB Database

This script provisions a new AlloyDB cluster and instance, creates the database and user, and stores the credentials securely in Secret Manager.
```bash
./deploy_alloydb.sh
```

### 3. Deploy Tooling Servers (MCP Servers)

Deploy the two backend tools (Cocktail and Weather APIs) that your specialized agents will call. This script deploys them to Cloud Run and updates your `.env` file with their URLs.
```bash
./mcp_servers/deploy_mcp_servers.sh
```

### 4. Deploy A2A Agents

This step deploys the Orchestrator, Cocktail, and Weather agents to Vertex AI Agent Engine. The deployment script will also automatically grant all necessary IAM permissions.

```bash
(cd a2a-on-ae-multiagent-memorybank/a2a_agents && uv venv && source .venv/bin/activate && uv sync --python 3.12 && ./deploy_agents.sh)
```

#### A Note on IAM Permissions
For your reference, the deployment script automatically grants the following roles. You do not need to run these commands manually.

*   **Agent Engine Service Agent (`service-...@gcp-sa-aiplatform-re.iam.gserviceaccount.com`):**
    *   `roles/run.invoker`: To invoke the specialized agents on Cloud Run.

*   **Compute Engine Service Account (`...-compute@developer.gserviceaccount.com`):**
    *   `roles/aiplatform.user`: To interact with Vertex AI services.
    *   `roles/run.invoker`: To invoke other services.
    *   `roles/artifactregistry.writer`: To push container images.
    *   `roles/alloydb.client`: To connect to the AlloyDB database.
    *   `roles/secretmanager.secretAccessor`: To read database credentials from Secret Manager.

### 5. Run the Frontend

Run the Gradio frontend locally to interact with your agent system. The script will install dependencies and start the web server.

```bash
(cd a2a-on-ae-multiagent-memorybank/frontend_option1 && uv venv && source .venv/bin/activate && uv sync --python 3.12 && ./deploy_frontend.sh --mode local)
```

### 6. Test the System

Open your web browser to `http://127.0.0.1:8080`. You can now chat with your multi-agent system.

Here are several test cases, ranging from simple to complex, to validate the full capabilities of the agent.

**Test 1: Simple Delegation**

These queries test if the orchestrator can correctly route a single request to the appropriate specialized agent.

-   `Please get weather forecast for New York`
-   `What ingredients are in a Margarita?`

**Test 2: Multi-Turn Conversation & Context**

This sequence tests the agent's conversational memory, which is persisted in the AlloyDB session store.

1.  **First Turn:** Ask for a cocktail.
    > `Give me a random cocktail.`
2.  **Second Turn:** The agent will respond with a cocktail (e.g., a "Royal Flush"). Now, ask a follow-up question that relies on the previous context.
    > `Great, what's the weather in a good city to drink that?`

The orchestrator should use its reasoning to infer a relevant city (e.g., Las Vegas for a Royal Flush) and then call the Weather Agent. This proves the session is being correctly maintained between turns.

**Test 3: Complex Reasoning and Information Synthesis**

This single query requires the agent to perform a multi-step plan, extract information from one tool's output, and use it as the input for another tool.

> `I'm planning a trip. Give me a classic, sophisticated cocktail to drink, and tell me what the weather is like right now in the city where that drink was invented.`

To answer this, the agent must:
1.  Call the **Cocktail Agent** to find a classic cocktail.
2.  **Extract the city of origin** from the cocktail's data (e.g., "Louisville").
3.  Call the **Weather Agent** using the extracted city.
4.  **Synthesize** both results into a single, helpful answer.

## What We Just Built
Congratulations! You have successfully built a stateful multi-agent system.
- A **Gradio Frontend** (our client)
- Talked to an **Orchestrator Agent**
- Which discovered and called two **Specialized Agents** (Cocktail and Weather)
- Which in turn called their own **Tools** (the MCP Servers)
- Crucially, the entire system is **stateful**, with all task and conversation history persisted in a robust **AlloyDB** database.

Here is the architecture you deployed:
![architecture](a2a-on-ae-multiagent-memorybank/asset/a2a_ae_diagram.png)

## Learn More
- [Agent Development Kit (ADK)](https://github.com/GoogleCloudPlatform/agent-development-kit)
- [Agent to Agent (A2A) Protocol](https://github.com/GoogleCloudPlatform/agent-development-kit/blob/main/docs/a2a.md)
- [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/agent-engine/overview)

## Cleanup
To avoid incurring future charges, run the cleanup script. This will deprovision the agents, MCP servers, and the AlloyDB cluster.

```bash
./cleanup.sh
```
