# deploy_orchestrator.py
# This script deploys the Orchestrator Agent to Google Cloud's Vertex AI Agent Engine.

import os
import vertexai
from google.genai import types
from dotenv import load_dotenv, set_key
import logging
import asyncio
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import TransportProtocol, AgentCard
from google.auth import default
from google.auth.transport.requests import Request as AuthRequest

# Import the Agent Card and Agent Executor specific to the Orchestrator Agent
from orchestrator.card import orchestrator_card
from orchestrator.executor import OrchestratorAgentExecutor
from shared.custom_context_builder import CustomCallContextBuilder
from shared.database.connection import build_global_task_store

# Import the A2aAgent class from Vertex AI SDK for deployment
from vertexai.preview.reasoning_engines import A2aAgent

# ... (rest of imports and setup) ...

# --- Now, with a valid ID, define the A2A Agent and deploy the code ---
logger.info(f"Using ORCHESTRATOR_AGENT_ENGINE_ID: {orchestrator_agent_engine_id}")

a2a_agent = A2aAgent(
    agent_card=orchestrator_card,
    agent_executor_builder=OrchestratorAgentExecutor,
    agent_executor_kwargs={"agent_engine_id": orchestrator_agent_engine_id},
    task_store_builder=build_global_task_store,
    task_store_kwargs={},
)

# Configuration for deploying the agent code
agent_code_config = agent_engine_config.copy()
agent_code_config.update({
    "requirements": [
        "google-cloud-aiplatform[agent_engines,adk]>=1.112.0",
        "a2a-sdk >= 0.3.4",
        "pydantic==2.11.9",
        "cloudpickle==3.1.1",
        "google-auth-oauthlib>=1.2.2",
        "google-auth[openid]>=2.40.3",
        "google-genai>=1.36.0",
        "google-cloud-alloydb-connector[asyncpg]",
        "google-cloud-secret-manager",
    ],
    "env_vars": {
        "COCKTAIL_AGENT_URL": COCKTAIL_AGENT_URL,
        "WEA_AGENT_URL": WEA_AGENT_URL,
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
        "PROJECT_ID": PROJECT_ID,
        "LOCATION": LOCATION
    },
    "extra_packages": ["orchestrator", "shared"]
})

agent_engine_resource_name = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{orchestrator_agent_engine_id}"
)
logger.info(f"Attempting to deploy Orchestrator Agent code to Agent Engine: {agent_engine_resource_name}")

remote_a2a_agent = client.agent_engines.update(
    name=agent_engine_resource_name,
    agent=a2a_agent,
    config=agent_code_config,
)

# Retrieve the deployed AgentEngine object to access its agent_card
remote_a2a_agent_retrieved = client.agent_engines.get(
    name=remote_a2a_agent.api_resource.name,
    config={
        "http_options": {
            "base_url": f"https://{LOCATION}-aiplatform.googleapis.com",
            "api_version": "v1beta1",
        },
    },
)

# Get the agent card from the retrieved AgentEngine object using asyncio.run
async def get_agent_card_async(agent_engine_obj) -> AgentCard:
    return await agent_engine_obj.handle_authenticated_agent_card()

orchestrator_agent_card_deployed = asyncio.run(get_agent_card_async(remote_a2a_agent_retrieved))

# Extract the URL from the deployed agent card
orchestrator_agent_url = orchestrator_agent_card_deployed.url

# Normalize the URL to ensure it has the correct /a2a suffix for client compatibility
orchestrator_agent_url = orchestrator_agent_url.rstrip('/')
if not orchestrator_agent_url.endswith('/a2a'):
    orchestrator_agent_url += '/a2a'

logger.info(f"Orchestrator Agent deployed successfully. Normalized URL: {orchestrator_agent_url}")
logger.info(f"Agent Engine ID: {orchestrator_agent_engine_id}")

# Save the deployed agent's URL to the .env file.
set_key(DOTENV_PATH, "ORCHESTRATOR_AGENT_URL", orchestrator_agent_url)
logger.info("ORCHESTRATOR_AGENT_URL saved to .env file.")
