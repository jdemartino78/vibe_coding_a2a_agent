# deploy_cocktail_agent.py
# This script deploys the Cocktail Agent to Google Cloud's Vertex AI Agent Engine.

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

# Import the Agent Card and Agent Executor specific to the Cocktail Agent
from cocktail_agent.cocktail_agent_card import cocktail_agent_card
from cocktail_agent.cocktail_agent_executor import CocktailAgentExecutor

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
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
DOTENV_PATH = os.path.join(PROJECT_ROOT, '.env')

# Load environment variables from the root .env file
load_dotenv(dotenv_path=DOTENV_PATH)

# --- Configuration from Environment Variables ---
# These variables are crucial for identifying your Google Cloud project and resources.
PROJECT_ID = os.getenv("PROJECT_ID")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
LOCATION = os.getenv("LOCATION", "us-central1") # Default to 'us-central1' if not set
BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_URI = f"gs://{BUCKET_NAME}"

# The URL of the previously deployed Cocktail MCP server (Cloud Run service)
# This is a critical dependency for the Cocktail Agent to function.
CT_MCP_SERVER_URL = os.getenv("CT_MCP_SERVER_URL")

# Validate essential environment variables
if not PROJECT_ID:
    raise ValueError("PROJECT_ID environment variable is not set. Please set it in your .env file.")
if not PROJECT_NUMBER:
    raise ValueError("PROJECT_NUMBER environment variable is not set. Please set it in your .env file.")
if not BUCKET_NAME:
    raise ValueError("BUCKET_NAME environment variable is not set. Please set it in your .env file.")
if not CT_MCP_SERVER_URL:
    raise ValueError("CT_MCP_SERVER_URL environment variable is not set. Please provide the URL of the deployed cocktail MCP server in your .env file.")

logger.info(f"Using Project ID: {PROJECT_ID}")
logger.info(f"Using Project Number: {PROJECT_NUMBER}")
logger.info(f"Using Location: {LOCATION}")
logger.info(f"Using Staging Bucket: {BUCKET_URI}")
logger.info(f"Using Cocktail MCP Server URL: {CT_MCP_SERVER_URL}")

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
# We check if an Agent Engine ID for the Cocktail Agent already exists.
# If not, we create a new one. This ID is crucial for managing the deployed agent.
cocktail_agent_engine_id = os.getenv("COCKTAIL_AGENT_ENGINE_ID")

if not cocktail_agent_engine_id:
    logger.info("COCKTAIL_AGENT_ENGINE_ID not found. Creating a new Agent Engine.")
    # The CocktailAgentExecutor's get_agent_engine method handles the creation
    # of a new Agent Engine and returns its ID.
    temp_executor = CocktailAgentExecutor()
    cocktail_agent_engine_id = temp_executor.agent_engine_id
    logger.info(f"Newly created COCKTAIL_AGENT_ENGINE_ID: {cocktail_agent_engine_id}")

    # Save the newly created ID to the .env file for future use.
    # This ensures consistency across deployments and allows other agents to reference it.
    set_key(DOTENV_PATH, "COCKTAIL_AGENT_ENGINE_ID", cocktail_agent_engine_id)
else:
    logger.info(f"Using existing COCKTAIL_AGENT_ENGINE_ID: {cocktail_agent_engine_id}")

# Construct the full resource name for the Agent Engine.
# This format is required by Vertex AI for identifying the deployed agent.
agent_engine_resource_name = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{cocktail_agent_engine_id}"
)

# --- Define the A2A Agent for Deployment ---
# The A2aAgent class wraps our agent's logic (card and executor) for deployment
# to Agent Engine.
a2a_agent = A2aAgent(
    agent_card=cocktail_agent_card,
    agent_executor_builder=CocktailAgentExecutor,
    agent_executor_kwargs={"agent_engine_id": cocktail_agent_engine_id},
)

logger.info(f"Attempting to deploy Cocktail Agent to Agent Engine: {agent_engine_resource_name}")

# --- Deploy/Update the Agent Engine ---
# This call deploys or updates the agent on Vertex AI Agent Engine.
# It includes configuration for display name, description, service account,
# Python package requirements, HTTP options, staging bucket, environment variables,
# and extra Python packages needed by the agent.
remote_a2a_agent = client.agent_engines.update(
    name=agent_engine_resource_name,
    agent=a2a_agent,
    config={
        "display_name": f"{a2a_agent.agent_card.name}-MemoryBank",
        "description": a2a_agent.agent_card.description,
        "service_account": f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
        "requirements": [
            "google-cloud-aiplatform[agent_engines,adk]>=1.112.0",
            "a2a-sdk >= 0.3.4",
            "pydantic==2.11.9",
            "cloudpickle==3.1.1",
            "google-auth-oauthlib>=1.2.2",
            "google-auth[openid]>=2.40.3",
            "google-genai>=1.36.0",
        ],
        "http_options": {
            "base_url": f"https://{LOCATION}-aiplatform.googleapis.com",
            "api_version": "v1beta1",
        },
        "staging_bucket": BUCKET_URI,
        "env_vars": {
            "COCKTAIL_REMOTE_MCP_SERVER_NAME": "cocktail-remote-mcp-server",
            "CT_MCP_SERVER_URL": CT_MCP_SERVER_URL,
            "PROJECT_ID": PROJECT_ID,
            "LOCATION": LOCATION,
        },
        "extra_packages": ["cocktail_agent/", "common/"]
    },
)

# Retrieve the deployed AgentEngine object to access its agent_card
remote_a2a_agent_retrieved = client.agent_engines.get(
    name=agent_engine_resource_name,
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

cocktail_agent_card_deployed = asyncio.run(get_agent_card_async(remote_a2a_agent_retrieved))

# Extract the URL from the deployed agent card
cocktail_agent_url = cocktail_agent_card_deployed.url

logger.info(f"Cocktail Agent deployed successfully. URL: {cocktail_agent_url}")
logger.info(f"Agent Engine ID: {cocktail_agent_engine_id}")

# Save the deployed agent's URL to the .env file.
# This URL will be needed by the Hosting Agent.
set_key(DOTENV_PATH, "COCKTAIL_AGENT_URL", cocktail_agent_url)
logger.info("COCKTAIL_AGENT_URL saved to .env file.")
