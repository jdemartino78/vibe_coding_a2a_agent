# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# # deploy_weather_agent.py
# This script deploys the Weather Agent to Google Cloud's Vertex AI Agent Engine.

import os
import vertexai
from google.genai import types
from dotenv import load_dotenv, set_key
import logging
import asyncio
from a2a.types import AgentCard
from google.auth import default
from google.auth.transport.requests import Request as AuthRequest

# Import the Agent Card and Agent Executor specific to the Weather Agent
from specialized.weather.card import weather_agent_card
from specialized.weather.executor import WeatherAgentExecutor

# Import the A2aAgent class from Vertex AI SDK for deployment
from vertexai.preview.reasoning_engines import A2aAgent

# Configure logging for better visibility during deployment
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_bearer_token() -> str | None:
    """Fetches a Google Cloud bearer token using Application Default Credentials."""
    try:
        credentials, project = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        request = AuthRequest()
        credentials.refresh(request)
        return credentials.token
    except Exception as e:
        logger.error(f"Error getting credentials: {e}")
        logger.error(
            "Please ensure you have authenticated with 'gcloud auth application-default login'."
        )
    return None

# Determine the project root and construct the path to the .env file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
DOTENV_PATH = os.path.join(PROJECT_ROOT, '.env')

# Load environment variables from the root .env file
load_dotenv(dotenv_path=DOTENV_PATH)

# --- Configuration from Environment Variables ---
# These variables are crucial for identifying your Google Cloud project and resources.
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
LOCATION = os.getenv("LOCATION", "us-central1") # Default to 'us-central1' if not set
BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_URI = f"gs://{BUCKET_NAME}"

# The URL of the previously deployed Weather MCP server (Cloud Run service)
# This is a critical dependency for the Weather Agent to function.
WEA_MCP_SERVER_URL = os.getenv("WEA_MCP_SERVER_URL")

# Validate essential environment variables
if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set. Please set it in your .env file.")
if not PROJECT_NUMBER:
    raise ValueError("PROJECT_NUMBER environment variable is not set. Please set it in your .env file.")
if not BUCKET_NAME:
    raise ValueError("BUCKET_NAME environment variable is not set. Please set it in your .env file.")
if not WEA_MCP_SERVER_URL:
    raise ValueError("WEA_MCP_SERVER_URL environment variable is not set. Please provide the URL of the deployed weather MCP server in your .env file.")

logger.info(f"Using Project ID: {PROJECT_ID}")
logger.info(f"Using Project Number: {PROJECT_NUMBER}")
logger.info(f"Using Location: {LOCATION}")
logger.info(f"Using Staging Bucket: {BUCKET_URI}")
logger.info(f"Using Weather MCP Server URL:. {WEA_MCP_SERVER_URL}")

# --- Initialize Vertex AI Session ---
# This sets up the connection to Google Cloud's Vertex AI services.
vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=BUCKET_URI)

# Initialize the Gen AI client with specific API version and base URL.
# This is used for interacting with Agent Engine.
client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
    http_options=types.HttpOptions(
        api_version="v1beta1",
        base_url=f"https://{LOCATION}-aiplatform.googleapis.com/"
    ),
)

# --- Agent Engine ID Management ---
# We check if an Agent Engine ID for the Weather Agent already exists.
# If not, we create a new one. This ID is crucial for managing the deployed agent.
weather_agent_engine_id = os.getenv("WEATHER_AGENT_ENGINE_ID")
remote_a2a_agent = None

# Base configuration for the Agent Engine resource
agent_engine_config={
    "display_name": f"{weather_agent_card.name}-MemoryBank",
    "description": weather_agent_card.description,
    "http_options": {
        "base_url": f"https://{LOCATION}-aiplatform.googleapis.com",
        "api_version": "v1beta1",
    },
    "staging_bucket": BUCKET_URI,
}

if not weather_agent_engine_id:
    logger.info("WEATHER_AGENT_ENGINE_ID not found. Creating a new Agent Engine resource.")
    
    weather_memory_config = {
        "memory_topics": [
            {"custom_memory_topic": {"label": "location", "description": "city and state mentioned in the conversation"}},
            {"custom_memory_topic": {"label": "weather_forecast", "description": "weather forecast from MCP server"}},
            {"managed_memory_topic": {"managed_topic_enum": "USER_PERSONAL_INFO"}},
            {"managed_memory_topic": {"managed_topic_enum": "USER_PREFERENCES"}},
            {"managed_memory_topic": {"managed_topic_enum": "KEY_CONVERSATION_DETAILS"}},
            {"managed_memory_topic": {"managed_topic_enum": "EXPLICIT_INSTRUCTIONS"}},
        ],
    }
    
    creation_config = agent_engine_config.copy()
    creation_config["context_spec"] = {
        "memory_bank_config": {
            "generation_config": {
                "model": f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash"
            },
            "customization_configs": [weather_memory_config],
        }
    }
    
    # Create the resource without the agent code
    agent_engine_resource = client.agent_engines.create(config=creation_config)
    weather_agent_engine_id = agent_engine_resource.api_resource.name.split('/')[-1]
    set_key(DOTENV_PATH, "WEATHER_AGENT_ENGINE_ID", weather_agent_engine_id)
    logger.info(f"Newly created WEATHER_AGENT_ENGINE_ID: {weather_agent_engine_id}")

# --- Now, with a valid ID, define the A2A Agent and deploy the code ---
logger.info(f"Using WEATHER_AGENT_ENGINE_ID: {weather_agent_engine_id}")

a2a_agent = A2aAgent(
    agent_card=weather_agent_card,
    agent_executor_builder=WeatherAgentExecutor,
    agent_executor_kwargs={"agent_engine_id": weather_agent_engine_id},
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
        "google-cloud-secret-manager",
        "google-cloud-alloydb-connector[asyncpg]",
        "sqlalchemy",
        "asyncpg",
    ],
    "env_vars": {
        "WEA_MCP_SERVER_URL": WEA_MCP_SERVER_URL,
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
        "PROJECT_ID": PROJECT_ID,
        "LOCATION": LOCATION,
    },
    "extra_packages": ["specialized/weather", "shared"]
})

agent_engine_resource_name = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{weather_agent_engine_id}"
)
logger.info(f"Attempting to deploy Weather Agent to Agent Engine: {agent_engine_resource_name}")
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

weather_agent_card_deployed = asyncio.run(get_agent_card_async(remote_a2a_agent_retrieved))

# Extract the URL from the deployed agent card
weather_agent_url = weather_agent_card_deployed.url

# Normalize the URL to ensure it has the correct /a2a suffix for client compatibility
weather_agent_url = weather_agent_url.rstrip('/')
if not weather_agent_url.endswith('/a2a'):
    weather_agent_url += '/a2a'


logger.info(f"Weather Agent deployed successfully. Normalized URL: {weather_agent_url}")
logger.info(f"Agent Engine ID: {weather_agent_engine_id}")

# Save the deployed agent's URL to the .env file.
# This URL will be needed by the Hosting Agent.
set_key(DOTENV_PATH, "WEA_AGENT_URL", weather_agent_url)
logger.info("WEA_AGENT_URL saved to .env file.")