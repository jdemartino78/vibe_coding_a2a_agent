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
) -> AsyncIterator[Tuple[str, List[Dict[str, Any]], Dict[str, Any]]]:
    """Get response from host agent and capture protocol logs."""

    a2a_client: Client = None
    httpx_client: httpx.AsyncClient = None
    logs: List[Dict[str, Any]] = []

    def add_log(event: str, details: Any, level: str = "INFO"):
        logs.append({
            "event": event,
            "details": details,
            "level": level,
            "timestamp": asyncio.get_event_loop().time()
        })
        logger.info(f"[{event}] {details}")

    try:
        add_log("Initialization", f"Fetching agent card for: {remote_a2a_agent_resource_name}")
        remote_a2a_agent_card = await get_agent_card(remote_a2a_agent_resource_name)
        
        agent_card_json = json.loads(remote_a2a_agent_card.json())
        agent_name = agent_card_json.get("name", "Unknown Agent")
        add_log("Agent Card Received", agent_card_json)

        httpx_client = httpx.AsyncClient(
            timeout=120,
            auth=GoogleAuth(),
        )

        factory = ClientFactory(
            ClientConfig(
                supported_transports=[TransportProtocol.http_json],
                use_client_preference=True,
                httpx_client=httpx_client,
                streaming=False,
            )
        )
        a2a_client = factory.create(remote_a2a_agent_card)
        add_log("Client Created", "A2A Client initialized with HTTP/JSON transport (Non-streaming)")

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

        add_log("Sending Message", message_payload)
        
        message = Message(**message_payload)
        response_stream = a2a_client.send_message(message)

        final_result_text = None
        final_task_object = None

        async for response_chunk in response_stream:
            if isinstance(response_chunk, tuple):
                task_object = response_chunk[0]
            else:
                task_object = response_chunk
            
            final_task_object = task_object
            
            # Convert task object to dict for logging, handling non-serializable types if needed
            task_dict = json.loads(task_object.json())

            # Process task artifacts for custom logs (delegation steps)
            if hasattr(task_object, 'artifacts') and task_object.artifacts:
                for artifact in task_object.artifacts:
                    if artifact.name == "delegation_log" and artifact.parts:
                         for part in artifact.parts:
                             if part.root.kind == "text":
                                 add_log(
                                     "Orchestrator Delegation", 
                                     {"message": part.root.text, "metadata": artifact.metadata}, 
                                     level="INFO"
                                 )

            # Process task history for intermediate logs (fallback)
            if hasattr(task_object, 'history') and task_object.history:
                for hist_message in task_object.history:
                    if hist_message.role == Role.agent and hist_message.parts:
                        # Check if it's a delegation message (from the orchestrator's TaskState.working update)
                        # Fix: Access .root.text, not .text directly on the Part object
                        if any(
                            p.root.kind == "text" and p.root.text and "Delegating to" in p.root.text 
                            for p in hist_message.parts
                        ):
                             # Find the first text part to display
                            first_text_part = next((p.root.text for p in hist_message.parts if p.root.kind == "text"), "")
                            add_log(
                                "Orchestrator Delegation (History)", 
                                {"message": first_text_part, "metadata": hist_message.metadata}, 
                                level="INFO"
                            )

            add_log("Task Update", task_dict)
            
            # Yield current state with logs
            yield "", logs, session_state

            if task_object.status.state in (TaskState.completed, TaskState.failed):
                if hasattr(task_object, "artifacts") and task_object.artifacts:
                    # Priority 1: Look for explicit "final_answer" or "answer" artifact
                    for artifact in task_object.artifacts:
                        if artifact.name in ("final_answer", "answer") and artifact.parts:
                             if isinstance(artifact.parts[0].root, TextPart):
                                final_result_text = artifact.parts[0].root.text
                                break 
                    
                    # Priority 2: If no explicit answer found, take the last text artifact (fallback)
                    if not final_result_text:
                         for artifact in reversed(task_object.artifacts):
                            if artifact.parts and isinstance(artifact.parts[0].root, TextPart):
                                # Ignore delegation logs in fallback if possible
                                if artifact.name != "delegation_log":
                                    final_result_text = artifact.parts[0].root.text
                                    break
                
                if final_result_text:
                    break
            
            elif task_object.status.state == TaskState.input_required:
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
            add_log("Final Response", final_result_text)
            yield final_result_text, logs, session_state
        else:
            msg = "I processed your request but found no text response."
            add_log("Warning", msg, level="WARNING")
            yield msg, logs, session_state

    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        add_log("Error", error_msg, level="ERROR")
        yield error_msg, logs, session_state
    finally:
        if a2a_client:
            await a2a_client.close()
        elif httpx_client:
            await httpx_client.aclose()


async def main() -> None:
    """Main gradio app that launches the Gradio interface."""
    
    # Custom CSS for a modern, clean look
    custom_css = """
    .gradio-container {
        font-family: 'Google Sans', 'Helvetica Neue', sans-serif;
    }
    .header-image {
        display: block;
        margin-left: auto;
        margin-right: auto;
        width: 80px;
        margin-bottom: 10px;
    }
    .header-text {
        text-align: center;
        margin-bottom: 20px;
    }
    .chat-column {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .inspector-column {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e9ecef;
        height: 100%;
    }
    .json-viewer {
        font-family: 'Fira Code', monospace;
        font-size: 12px;
    }
    """

    theme = gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="blue",
        neutral_hue="slate",
    ).set(
        body_background_fill="#f0f2f5",
        block_background_fill="#ffffff",
        block_border_width="0px",
        block_shadow="0 2px 4px rgba(0,0,0,0.05)",
    )

    with gr.Blocks(theme=theme, css=custom_css, title="A2A Host Agent") as demo:
        session_state = gr.State({})
        
        with gr.Column(elem_classes="header-text"):
            gr.Image(
                value="static/a2a.png",
                interactive=False,
                show_label=False,
                show_download_button=False,
                container=False,
                elem_classes="header-image",
                height=80,
                width=80
            )
            gr.Markdown("# A2A Host Agent\nThis assistant can help you check weather and find cocktail information.")

        with gr.Row():
            # Left Column: Chat Interface
            with gr.Column(scale=3, elem_classes="chat-column"):
                chatbot = gr.Chatbot(
                    height=600,
                    type="messages",
                    bubble_full_width=False,
                    avatar_images=(None, "static/a2a.png"), # Optional: Add user avatar if available
                )
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Type a message...",
                        show_label=False,
                        scale=8,
                        container=False
                    )
                    submit_btn = gr.Button("Send", scale=1, variant="primary")
                clear = gr.ClearButton([msg, chatbot, session_state])

            # Right Column: Protocol Inspector
            with gr.Column(scale=2, elem_classes="inspector-column"):
                gr.Markdown("### 🔍 Protocol Inspector\nLive view of A2A protocol messages and events.")
                protocol_logs = gr.JSON(
                    label="Protocol Trace",
                    value=[],
                    elem_classes="json-viewer"
                )

        async def respond(
            message: str,
            chat_history: List[Dict[str, str]],
            session: Dict[str, Any],
        ) -> AsyncIterator[Tuple[List[Dict[str, str]], List[Dict[str, Any]], Dict[str, Any]]]:
            """Wrapper to provide immediate feedback and stream responses."""
            # 1. Immediately append the user's message to the history
            chat_history.append({"role": "user", "content": message})
            yield chat_history, [], session

            # 2. Stream the response from the agent
            async for bot_response_text, logs, new_session in get_response_from_agent(
                message, session
            ):
                # If we have a partial or final text response, show it
                # Note: Gradio Chatbot 'messages' format expects a full history list
                
                current_history = list(chat_history) # Copy
                if bot_response_text:
                    # Check if last message is from assistant to update it, else append
                    if current_history and current_history[-1]["role"] == "assistant":
                         current_history[-1]["content"] = bot_response_text
                    else:
                         current_history.append({"role": "assistant", "content": bot_response_text})
                
                yield current_history, logs, new_session

        # Bind events
        msg.submit(
            respond, [msg, chatbot, session_state], [chatbot, protocol_logs, session_state]
        ).then(lambda: gr.update(value=""), None, [msg]) # Clear input after submit
        
        submit_btn.click(
            respond, [msg, chatbot, session_state], [chatbot, protocol_logs, session_state]
        ).then(lambda: gr.update(value=""), None, [msg])

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
        allowed_paths=["static"]
    )


if __name__ == "__main__":
    # Create the 'static' directory if it doesn't exist for the image
    if not os.path.exists("static"):
        os.makedirs("static")
        logger.info("Created 'static' directory. Please add your 'a2a.png' image there.")

    asyncio.run(main())