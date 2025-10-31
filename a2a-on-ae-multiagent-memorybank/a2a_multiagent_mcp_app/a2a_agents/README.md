# A2A Multi-Agent System

## Overview

This project implements a multi-agent system using the A2A (Agent-to-Agent) protocol and Google's Vertex AI. The system consists of an orchestrator agent and several specialized agents that work together to handle user requests.

The architecture follows a hierarchical pattern where a `HostingAgent` acts as the main entry point, delegating tasks to the appropriate specialized agents through an `OrchestratorAgent`.

## Project Structure

```
/
├── cocktail_agent/         # Specialized agent for cocktail recipes
│   ├── cocktail_agent_card.py
│   └── cocktail_agent_executor.py
├── common/                # Common modules and base classes
│   ├── adk_base_mcp_agent_executor.py
│   ├── adk_orchestrator_agent_executor.py
│   ├── adk_orchestrator_agent.py
│   ├── agent_configs.py
│   └── remote_connection.py
├── hosting_agent/          # Main entry point and orchestrator
│   ├── agent_executor.py
│   └── hosting_agent_card.py
├── weather_agent/          # Specialized agent for weather forecasts
│   ├── weather_agent_card.py
│   └── weather_agent_executor.py
├── deploy_cocktail_agent.py  # Script for deploying the cocktail agent
├── deploy_hosting_agent.py   # Script for deploying the hosting agent
├── deploy_weather_agent.py   # Script for deploying the weather agent
├── redeploy_agents.sh     # Utility script to redeploy all agents
├── pyproject.toml          # Project dependencies
└── README.md               # This file
```

## Agents

### Orchestrator Agent

The `OrchestratorAgent` is the core of the multi-agent system. It is responsible for:

-   **Agent Discovery:** Discovering available agents and their capabilities by retrieving their agent cards.
-   **Task Delegation:** Receiving user requests and delegating them to the most appropriate specialized agent.
-   **Session Management:** Managing the conversation and context across multiple turns.

### Hosting Agent

The `HostingAgent` is the main entry point for user requests. It wraps the `OrchestratorAgent` and provides a unified interface to the multi-agent system. It is responsible for initializing the orchestrator with the addresses of the remote agents.

### Cocktail Agent

The `CocktailAgent` is a specialized agent that provides information about cocktails. It can answer questions about cocktail recipes and ingredients.

### Weather Agent

The `WeatherAgent` is a specialized agent that provides weather forecasts. It can retrieve the weather for a given city or state.

## Getting Started

1.  **Install dependencies:**

    ```bash
    uv sync
    ```

2.  **Set up environment variables:**

    Create a `.env` file by copying the `.env.example` file and populate it with the necessary credentials and agent URLs.

3.  **Deploy the agents:**

    The agents can be deployed to Google's Agent Engine using the provided deployment scripts. See the "Deployment Scripts" section for more details.

## Deployment Scripts

The project includes Python scripts for deploying the agents to Google's Agent Engine:

-   `deploy_cocktail_agent.py`: Deploys the Cocktail Agent.
-   `deploy_hosting_agent.py`: Deploys the Hosting Agent.
-   `deploy_weather_agent.py`: Deploys the Weather Agent.

These scripts handle the entire deployment process, including creating the agent engine, configuring the service account, and setting up the necessary environment variables.

### Redeploying Agents

The `redeploy_agents.sh` script is a utility to quickly redeploy all the agents. This is useful when you have made changes to the agent code and want to update the deployed services.