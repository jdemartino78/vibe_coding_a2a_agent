# FILE: a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/a2a_agents/common/a2a_tools.py

import os
import logging
import httpx
import uuid
import json
import asyncio
import contextvars
from typing import Any
from a2a.client import ClientFactory, ClientConfig
from a2a.types import (
    Message,
    Part,
    Role,
    Task,
    TaskState,
    TextPart,
    TransportProtocol,
    TaskQueryParams,
)
from a2a.utils import new_agent_text_message
from shared.auth_utils import GoogleAuth

# --- CONTEXT VARIABLE FOR USER_ID ---
# This context variable will hold the user_id for the current request,
# allowing it to be accessed safely in a concurrent environment.
user_id_context = contextvars.ContextVar('user_id_for_delegation', default='default-user')

# --- CONTEXT VARIABLE FOR TASK UPDATER ---
# This allows the tool to send status updates back to the client (Orchestrator's client).
task_updater_context = contextvars.ContextVar('task_updater_context', default=None)


# --- EFFICIENT, SHARED, AUTHENTICATED, NON-STREAMING CLIENT SETUP ---

# 1. Create an authenticated httpx client that can be shared.
AUTHENTICATED_HTTPX_CLIENT = httpx.AsyncClient(
    timeout=120,
    auth=GoogleAuth(),
)

# 2. Create a config that uses the authenticated client.
# streaming=False is critical for compatibility with Agent Engine.
SHARED_CLIENT_CONFIG = ClientConfig(
    streaming=False,
    httpx_client=AUTHENTICATED_HTTPX_CLIENT,
    supported_transports=[
        TransportProtocol.jsonrpc,
        TransportProtocol.http_json,
    ],
)

# 3. Create the factory with the new authenticated config.
SHARED_CLIENT_FACTORY = ClientFactory(config=SHARED_CLIENT_CONFIG)

logger = logging.getLogger(__name__)

REMOTE_AGENT_URL_VARS = {
    "Cocktail Agent": "COCKTAIL_AGENT_URL",
    "Weather Agent": "WEA_AGENT_URL",
}

TERMINAL_STATES = {
    TaskState.completed,
    TaskState.failed,
    TaskState.canceled,
    TaskState.rejected,
}


def _get_final_text_from_task(response: Task | Message) -> str:
    """
    Helper function to extract the raw text content from a completed Task's artifacts.
    """
    raw_text = ""
    if isinstance(response, Task):
        if response.artifacts:
            for artifact in response.artifacts:
                if artifact.name == "answer" and artifact.parts:
                    for part in artifact.parts:
                        if part.root.kind == "text" and part.root.text is not None:
                            raw_text = part.root.text
                            break
                if raw_text:
                    break
    
    if not raw_text:
        logger.warning("No text artifact named 'answer' found in the agent's response.")
        return "No text content found in the agent's response."

    logger.info(f"Received raw text from specialist agent: '{raw_text}'")
    return raw_text


async def delegate_to_specialist_agent(agent_name: str, query: str) -> str:
    """
    Delegates a query to a specialist agent using a non-streaming, polling pattern
    and returns the final raw response from the task artifacts.
    """
    url_var = REMOTE_AGENT_URL_VARS.get(agent_name)
    if not url_var:
        return f"Error: Unknown agent '{agent_name}'. Available agents: {list(REMOTE_AGENT_URL_VARS.keys())}"

    agent_url = os.getenv(url_var) or os.getenv(url_var.replace("_URL", "_SERVER_URL"))
    
    if not agent_url:
        return f"Error: The URL for '{agent_name}' is not configured via {url_var}."

    # Get the user_id from the context variable
    user_id = user_id_context.get()
    logger.info(f"Attempting to delegate to '{agent_name}' with query: '{query}' for user_id: '{user_id}'")

    # Send a status update via the orchestrator's TaskUpdater (if available)
    updater = task_updater_context.get()
    if updater:
        try:
            delegation_msg = f"Delegating to {agent_name} with query: '{query}'"
            await updater.update_status(
                TaskState.working,
                message=new_agent_text_message(delegation_msg),
                metadata={"delegated_agent": agent_name, "delegated_query": query}
            )
            # Add artifact for persistent logging in non-streaming environments
            await updater.add_artifact(
                [TextPart(text=delegation_msg)],
                name="delegation_log",
                metadata={"agent": agent_name, "query": query, "timestamp": str(asyncio.get_event_loop().time())}
            )
        except Exception as e:
             logger.warning(f"Failed to send status update or add artifact: {e}")
    
    client = None
    try:
        client = await SHARED_CLIENT_FACTORY.connect(
            agent=agent_url,
            client_config=SHARED_CLIENT_CONFIG,
            relative_card_path="/v1/card",
        )
        
        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=query))],
            metadata={"user_id": user_id}  # Pass user_id in metadata
        )
        
        # 1. Send the initial message to start the task
        initial_response = None
        async for event in client.send_message(message):
            if isinstance(event, tuple): # A ClientEvent is a (Task, Update) tuple
                initial_response = event[0]
            else: # Should be a Task in non-streaming
                initial_response = event
            break # In non-streaming, we only get one event

        if not isinstance(initial_response, Task):
            return f"Error: Did not receive a valid Task object to start. Got: {type(initial_response)}"

        task_id = initial_response.id
        logger.info(f"Task received with ID: {task_id} and status: {initial_response.status.state}.")

        # 2. Process the final task
        if initial_response.status.state == TaskState.completed:
            response_text = _get_final_text_from_task(initial_response)
            logger.info(f"Received RAW response from '{agent_name}'. Returning to LLM: '{response_text}'")
            return response_text
        else:
            error_message = f"Task failed with state: {initial_response.status.state}."
            if initial_response.status.message:
                 error_message += f" Reason: {initial_response.status.message.parts[0].root.text}"
            return error_message

    except Exception as e:
        logger.error(f"An exception occurred while communicating with '{agent_name}': {e}", exc_info=True)
        return f"CRITICAL ERROR: Failed to communicate with {agent_name}."
    finally:
        pass