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
# Author: Dave Wang
# a2a_multiagent_mcp_app/frontend_option1/main.py
import asyncio
import logging
import os
import time
import uuid
from typing import AsyncIterator, List, Tuple

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

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
AGENT_ENGINE_ID = os.getenv("HOSTING_AGENT_ENGINE_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


# Initialize Vertex AI session
vertexai.init(project=PROJECT_ID, location=LOCATION)

# This is a global client for fetching the agent card, not for conversations
global_vertex_client = vertexai.Client(
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
    """A custom httpx Auth class for Google Cloud authentication."""

    def __init__(self) -> None:
        """Initializes the GoogleAuth instance with default credentials."""
        self.credentials: Credentials
        self.project: str | None
        self.credentials, self.project = default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.auth_request = AuthRequest()

    def auth_flow(self, request: httpx.Request):
        """Adds the Authorization header to the request."""
        if not self.credentials.valid:
            logger.info("Credentials expired, refreshing...")
            self.credentials.refresh(self.auth_request)
        request.headers["Authorization"] = f"Bearer {self.credentials.token}"
        yield request


async def get_agent_card(resource_name: str) -> object:
    """Fetches the agent card from Vertex AI."""
    config = {"http_options": {"base_url": f"https://{LOCATION}-aiplatform.googleapis.com"}}
    remote_a2a_agent = global_vertex_client.agent_engines.get(name=resource_name, config=config)
    return await remote_a2a_agent.handle_authenticated_agent_card()


async def get_response_from_agent(
    query: str,
    user_id: str,
    a2a_client: Client,
    context_id: str,
) -> AsyncIterator[str]:
    """Get response from host agent using a persistent client. Yields streamed text chunks."""
    try:
        # Format the query to include the user_id for the backend to parse
        formatted_query = f"user_id::{user_id}::{query}"
        message = Message(
            message_id=f"message-{os.urandom(8).hex()}",
            role=Role.user,
            parts=[Part(root=TextPart(text=formatted_query))],
            context_id=context_id,
        )

        logger.info(f"Sending message to agent for user '{user_id}' in context '{context_id}': {query}")
        response_stream = a2a_client.send_message(message)

        full_response_text = ""
        response_yielded = False
        async for response_chunk in response_stream:
            task_object = response_chunk[0]

            # New logic to handle streaming artifacts
            if hasattr(task_object, "artifacts") and task_object.artifacts:
                for artifact in task_object.artifacts:
                    if artifact.name == "answer_chunk" and artifact.parts and isinstance(artifact.parts[0].root, TextPart):
                        new_chunk = artifact.parts[0].root.text
                        full_response_text += new_chunk
                        yield full_response_text
                        response_yielded = True

            if task_object.status.state == TaskState.completed:
                # The final answer might be in a separate artifact
                if hasattr(task_object, "artifacts") and task_object.artifacts:
                    for artifact in task_object.artifacts:
                        if artifact.name == "answer" and artifact.parts and isinstance(artifact.parts[0].root, TextPart):
                            final_text = artifact.parts[0].root.text
                            if final_text != full_response_text: # Append if different
                                full_response_text = final_text
                                yield full_response_text
                                response_yielded = True
                break # End of stream
            elif task_object.status.state == TaskState.failed:
                error_message = f"Task failed: {task_object.status.message if task_object.status else 'Unknown error'}"
                logger.error(error_message)
                yield error_message
                return

        if not response_yielded:
            logger.warning("Stream finished but no text artifact was found")
            yield "I processed your request but found no text response."

    except Exception as e:
        logger.error(f"Error in get_response_from_agent: {e}", exc_info=True)
        yield f"An error occurred: {e}"


async def main() -> None:
    """Main gradio app that launches the Gradio interface."""

    with gr.Blocks(theme=gr.themes.Ocean(), title="A2A Host Agent") as demo:
        # State to hold session-specific data
        user_id_state = gr.State(value=None)
        context_id_state = gr.State(value=None)
        a2a_client_state = gr.State(value=None)
        httpx_client_state = gr.State(value=None)

        # --- Login View ---
        with gr.Group(visible=True) as login_view:
            with gr.Row():
                gr.Image("static/a2a.png", width=100, height=100, scale=0, show_label=False, show_download_button=False, container=False, show_fullscreen_button=False)
            user_id_input = gr.Textbox(
                label="Enter User ID to Start",
                placeholder="e.g., user-jane-doe",
                elem_id="user_id_input"
            )
            start_button = gr.Button("Start Chat Session")

        # --- Chat View ---
        with gr.Group(visible=False) as chat_view:
            gr.Markdown("## A2A Host Agent")
            chatbot = gr.Chatbot(label="Conversation", elem_id="chatbot", height=500)
            msg_input = gr.Textbox(
                label="Your Message",
                placeholder="Ask about weather or cocktails...",
                scale=4
            )
            send_button = gr.Button("Send")
            change_user_button = gr.Button("End Session & Change User")

        # --- Event Handlers ---
        async def start_chat_session(user_id):
            """Handles the 'Start Chat' button click. Creates and stores clients."""
            if not user_id:
                # Return 6 empty/default values to match the outputs if user_id is empty
                return None, None, None, None, gr.update(visible=True), gr.update(visible=False)
            
            start_time = time.time()
            logger.info(f"Starting chat session for user: {user_id}")
            
            # Create clients for this session
            try:
                remote_a2a_agent_card = await get_agent_card(remote_a2a_agent_resource_name)
                httpx_client = httpx.AsyncClient(timeout=120, auth=GoogleAuth())
                factory = ClientFactory(
                    ClientConfig(
                        supported_transports=[TransportProtocol.http_json],
                        use_client_preference=True,
                        httpx_client=httpx_client,
                    )
                )
                a2a_client = factory.create(remote_a2a_agent_card)
                context_id = str(uuid.uuid4())
                logger.info(f"New context ID for session: {context_id}")

                end_time = time.time()
                logger.info(f"Session startup time for user {user_id}: {end_time - start_time:.2f} seconds")

                return (
                    user_id,
                    context_id,
                    a2a_client,
                    httpx_client,
                    gr.update(visible=False),
                    gr.update(visible=True),
                )
            except Exception as e:
                logger.error(f"Failed to create A2A client: {e}", exc_info=True)
                gr.Warning(f"Failed to start session: {e}")
                # Return 6 empty/default values on error
                return None, None, None, None, gr.update(visible=True), gr.update(visible=False)

        async def add_message_and_get_response(message, chat_history, user_id, context_id, a2a_client):
            """Handles sending a message and streaming the response."""
            if not all([user_id, context_id, a2a_client]):
                error_msg = "ERROR: Session not initialized. Please end session and restart."
                chat_history.append((message, error_msg))
                yield chat_history, ""
                return

            chat_history.append((message, ""))
            yield chat_history, ""

            response_generator = get_response_from_agent(
                query=message, user_id=user_id, a2a_client=a2a_client, context_id=context_id
            )
            async for chunk in response_generator:
                chat_history[-1] = (message, chunk)
                yield chat_history, ""

        async def end_chat_session(a2a_client, httpx_client):
            """Handles the 'Change User' button click. Cleans up clients."""
            logger.info("Ending chat session.")
            try:
                if a2a_client:
                    await a2a_client.close()
                    logger.info("A2A client closed.")
                elif httpx_client:
                    await httpx_client.aclose()
                    logger.info("HTTPX client closed as fallback.")
            except Exception as e:
                logger.error(f"Error closing clients: {e}", exc_info=True)
                gr.Warning(f"Error during session cleanup: {e}")

            return {
                user_id_state: None,
                context_id_state: None,
                a2a_client_state: None,
                httpx_client_state: None,
                chatbot: [],
                login_view: gr.update(visible=True),
                chat_view: gr.update(visible=False),
            }

        # --- Wire up components to handlers ---
        start_button.click(
            start_chat_session,
            inputs=[user_id_input],
            outputs=[user_id_state, context_id_state, a2a_client_state, httpx_client_state, login_view, chat_view],
        )

        msg_input.submit(
            add_message_and_get_response,
            inputs=[msg_input, chatbot, user_id_state, context_id_state, a2a_client_state],
            outputs=[chatbot, msg_input],
        )
        send_button.click(
            add_message_and_get_response,
            inputs=[msg_input, chatbot, user_id_state, context_id_state, a2a_client_state],
            outputs=[chatbot, msg_input],
        )

        change_user_button.click(
            end_chat_session,
            inputs=[a2a_client_state, httpx_client_state],
            outputs=[user_id_state, context_id_state, a2a_client_state, httpx_client_state, chatbot, login_view, chat_view],
        )

    logger.info("Launching Gradio interface on http://0.0.0.0:8080")
    demo.queue().launch(server_name="0.0.0.0", server_port=8080)
    logger.info("Gradio application has been shut down")


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
        logger.info("Created 'static' directory. Please add your 'a2a.png' image there.")
    asyncio.run(main())
