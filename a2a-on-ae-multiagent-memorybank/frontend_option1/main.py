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
import asyncio
import logging
import os
from typing import AsyncIterator, List, Dict, Any, Tuple

import gradio as gr
import httpx
import vertexai
from a2a.client import Client, ClientConfig, ClientFactory
from a2a.types import (
    Message,
    Part,
    Role,
    TaskState,
    TextPart,
    TransportProtocol,
)
from dotenv import load_dotenv
from google.auth import default
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest
from google.genai import types as genai_types  # Aliased to avoid conflict
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
AGENT_ENGINE_ID = os.getenv("ORCHESTRATOR_AGENT_ENGINE_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
USER_ID = os.getenv("USER_ID", "default-user")


# Initialize Vertex AI session
vertexai.init(project=PROJECT_ID, location=LOCATION)

client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
    http_options=genai_types.HttpOptions(
        api_version="v1beta1", base_url=f"https://{LOCATION}-aiplatform.googleapis.com/"
    ),
)


remote_a2a_agent_resource_name = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{AGENT_ENGINE_ID}"
)


class GoogleAuth(httpx.Auth):
    """A custom httpx Auth class for Google Cloud authentication.

    This class implements httpx's Auth interface to automatically handle
    Google Cloud authentication by:
    1. Using Application Default Credentials (ADC)
    2. Automatically refreshing expired tokens
    3. Adding the Authorization header to all requests
    """

    def __init__(self) -> None:
        """Initializes the GoogleAuth instance with default credentials.

        Uses Application Default Credentials with cloud-platform scope.
        """
        self.credentials: Credentials
        self.project: str | None
        self.credentials, self.project = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.auth_request = AuthRequest()

    def auth_flow(self, request: httpx.Request):
        """Adds the Authorization header to the request.

        Args:
            request: The httpx request to add the header to.

        Yields:
            The request with the Authorization header added.
        """
        # Refresh the credentials if they are expired
        if not self.credentials.valid:
            logger.info("Credentials expired, refreshing...")
            self.credentials.refresh(self.auth_request)

        # Add the Authorization header to the request
        request.headers["Authorization"] = f"Bearer {self.credentials.token}"
        yield request


async def get_agent_card(resource_name: str) -> object:
    """Fetches the agent card from Vertex AI.

    Args:
        resource_name: The full resource name of the agent engine.

    Returns:
        The agent card object.
    """
    config = {"http_options": {"base_url": f"https://{LOCATION}-aiplatform.googleapis.com"}}

    remote_a2a_agent = client.agent_engines.get(
        name=resource_name,
        config=config,
    )

    return await remote_a2a_agent.handle_authenticated_agent_card()


async def get_response_from_agent(
    query: str,
    session_state: Dict[str, Any]
) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
    """Get response from host agent."""

    a2a_client: Client = None
    httpx_client: httpx.AsyncClient = None

    try:
        logger.info("Fetching agent card...")
        remote_a2a_agent_card = await get_agent_card(remote_a2a_agent_resource_name)
        logger.info("Agent card fetched successfully")
        agent_card_json = json.loads(remote_a2a_agent_card.json())
        agent_name = agent_card_json["name"]
        logger.info(f"Agent card for {agent_name} fetched successfully") 

        httpx_client = httpx.AsyncClient(
            timeout=120,
            auth=GoogleAuth(),
        )


        factory = ClientFactory(
            ClientConfig(
                supported_transports=[TransportProtocol.http_json],
                use_client_preference=True,
                httpx_client=httpx_client,
            )
        )
        a2a_client = factory.create(remote_a2a_agent_card)
        logger.info("A2A client created successfully")

        message_payload = {
            "message_id": f"message-{os.urandom(8).hex()}",
            "role": Role.user,
            "parts": [Part(root=TextPart(text=query))],
            "metadata": {"user_id": USER_ID},
        }
        if session_state.get("task_id"):
            message_payload["task_id"] = session_state["task_id"]
        if session_state.get("context_id"):
            message_payload["context_id"] = session_state["context_id"]

        message = Message(**message_payload)

        logger.info(f"Sending message to agent {agent_name}: {query}")
        response_stream = a2a_client.send_message(message)

        final_result_text = None
        final_task_object = None

        async for response_chunk in response_stream:
            task_object = response_chunk[0]
            final_task_object = task_object

            logger.debug(f"Received task update. Status: {task_object.status.state}")

            if task_object.status.state in (TaskState.completed, TaskState.failed):
                logger.info(f"Task reached terminal state: {task_object.status.state}")
                if hasattr(task_object, "artifacts") and task_object.artifacts:
                    for artifact in task_object.artifacts:
                        if artifact.parts and isinstance(artifact.parts[0].root, TextPart):
                            final_result_text = artifact.parts[0].root.text
                            logger.info(f"Found artifact text: {final_result_text[:50]}...")
                            break
                if final_result_text:
                    break
            
            elif task_object.status.state == TaskState.input_required:
                logger.info("Task requires more input.")
                if task_object.status.message and task_object.status.message.parts:
                    final_result_text = task_object.status.message.parts[0].root.text
                    break

        if final_task_object:
            session_state["context_id"] = final_task_object.context_id
            if final_task_object.status.state in (TaskState.completed, TaskState.failed):
                session_state["task_id"] = None
            else:
                session_state["task_id"] = final_task_object.id

        if final_result_text:
            yield final_result_text, session_state
        else:
            logger.warning("Task finished but no text artifact was found")
            no_response_message = "I processed your request but found no text response."
            yield no_response_message, session_state

    except Exception as e:
        logger.error(
            f"Error in get_response_from_agent (Type: {type(e).__name__}): {e}", exc_info=True
        )
        error_response = f"An error occurred: {e}"
        yield error_response, session_state
    finally:
        if a2a_client:
            await a2a_client.close()
            logger.debug("A2A client closed")
        elif httpx_client:
            await httpx_client.aclose()
            logger.debug("HTTPX client closed")


async def main() -> None:
    """Main gradio app that launches the Gradio interface."""

    with gr.Blocks(theme=gr.themes.Ocean(), title="A2A Host Agent") as demo:
        session_state = gr.State({})
        
        with gr.Row():
            gr.Image(
                value="static/a2a.png",
                interactive=False,
                width=100,
                height=100,
                scale=0,
                show_label=False,
                show_download_button=False,
                container=False,
                show_fullscreen_button=False,
            )
        
        gr.Markdown("# A2A Host Agent")
        gr.Markdown("This assistant can help you to check weather and find cocktail information")

        chatbot = gr.Chatbot()
        msg = gr.Textbox()
        clear = gr.ClearButton([msg, chatbot, session_state])

        async def respond(
            message: str,
            chat_history: List[Tuple[str, str]],
            session: Dict[str, Any],
        ) -> AsyncIterator[Tuple[str, List[Tuple[str, str]], Dict[str, Any]]]:
            """Wrapper to provide immediate feedback and stream responses."""
            # 1. Immediately append the user's message to the history
            chat_history.append((message, None))
            yield "", chat_history, session

            # 2. Stream the response from the agent
            async for bot_response, new_session in get_response_from_agent(
                message, session
            ):
                # 3. Update the history with the final response
                chat_history.append((None, bot_response))
                yield "", chat_history, new_session

        msg.submit(
            respond, [msg, chatbot, session_state], [msg, chatbot, session_state]
        )

    # Add a health check endpoint to the underlying FastAPI app
    @demo.app.get("/health")
    async def health_check():
        return {"status": "ok"}

    # Get port from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Launching Gradio interface on http://0.0.0.0:{port}")
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=port,
    )


if __name__ == "__main__":
    # Create the 'static' directory if it doesn't exist for the image
    if not os.path.exists("static"):
        os.makedirs("static")
        logger.info("Created 'static' directory. Please add your 'a2a.png' image there.")

    asyncio.run(main())