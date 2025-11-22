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

import logging
import os
import re
from abc import ABC
from typing import NoReturn, Optional

# A2A Imports
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Role, TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from dotenv import load_dotenv

# ADK Imports
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import VertexAiSessionService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types as genai_types
import vertexai
from sqlalchemy.ext.asyncio import AsyncEngine
from vertexai.preview.reasoning_engines.templates.adk import (
    _default_instrumentor_builder,
)

# Custom Imports
from shared.tools import delegate_to_specialist_agent, user_id_context, task_updater_context
from shared.base_executor import PersistentVertexAiMemoryBankService
from shared.database.sessions import get_session_mapping, set_session_mapping

# Set logging
logging.getLogger().setLevel(logging.INFO)
load_dotenv()


async def auto_save_session_to_memory_callback(callback_context: CallbackContext):
    """
    Callback to save conversation session to Vertex AI Memory Bank.
    """
    session = callback_context._invocation_context.session
    memory_service = callback_context._invocation_context.memory_service

    logging.info(
        f"Saving session {session.id} to memory bank for user_id={session.user_id}"
    )

    try:
        await memory_service.add_session_to_memory(session)
        logging.info(f"Memory generation completed for session {session.id}")
    except Exception as e:
        logging.error(
            f"Memory generation failed for session {session.id}: {e}",
            exc_info=True,
        )


def _telemetry_enabled() -> Optional[bool]:
    """Return status of telemetry enablement depending on enablement env variable."""
    env_value = os.getenv(
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "unspecified"
    ).lower()
    if env_value in ("true", "1"):
        return True
    if env_value in ("false", "0"):
        return False
    return None


# --- 1. PROMPT DEFINITION (The Core Planner Logic) ---
ORCHESTRATOR_INSTRUCTION = """
You are a master orchestrator agent. Your purpose is to fulfill user requests by breaking them down into steps and delegating those steps to the correct specialized agent using the 'delegate_to_specialist_agent' tool.

**AVAILABLE SPECIALIZED AGENTS:**
- **Cocktail Agent**: Use for questions about cocktails, recipes, or ingredients.
- **Weather Agent**: Use for questions about weather or forecasts. **Limitation: This agent only supports locations within the United States.**

**CRITICAL RULES:**

1.  **Capability Check First:** Before planning or delegating, review the user's request and check if it's possible given the limitations of the available agents. If a request cannot be fulfilled (e.g., asking for weather in Paris, France), do not proceed. Instead, politely inform the user about the specific limitation.
2.  **Analyze & Plan:** Carefully examine the user's query to identify all the distinct pieces of information needed and decide the logical order for delegation.
3.  **Execute Sequentially:** Call the 'delegate_to_specialist_agent' tool for the first step. **Wait for the result.** Then, if necessary, call the tool again for the next step. DO NOT make parallel or concurrent tool calls.
4.  **Handle Subjective Queries:** If the user's request is subjective or vague (e.g., "a sophisticated cocktail," "a fun drink"), you must translate it into a concrete query for the specialist agent. For cocktails, default to asking for a 'random' cocktail. For example, convert "a classic drink" to the query "get a random classic cocktail".
5.  **Dynamic Reasoning (Multi-Step):** If the request requires multiple domains (e.g., 'cocktail and weather'):
    a.  **Step 1:** Call `Cocktail Agent` first.
    b.  **Step 2:** Read the structured output. **Use your world knowledge and reasoning** to infer a plausible city and country where that cocktail should be enjoyed (e.g., Mojito -> 'Havana, Cuba').
    c.  **Step 3:** Call `Weather Agent` using the inferred location.
6.  **Synthesis:** Once all data is gathered (which will be structured JSON), combine the results into a single, comprehensive, and helpful answer for the user. **DO NOT return raw JSON.** Use Markdown for a final presentation.

**MEMORY:**
- This is a multi-turn conversation. It is VERY IMPORTANT that you remember previous parts of the conversation.
- Relevant memories from past conversations have been pre-loaded into the context. Use this information to help answer the user's request.
- Use your memory to recall context from the conversation to answer questions.

**LOCATION NORMALIZATION:**
- If the user provides a common abbreviation like 'NYC' or 'LA', you must resolve it to the full name (e.g., 'New York, NY', 'Los Angeles, CA') before calling the 'Weather Agent'.

**EXAMPLE:**
- User: "What's the weather in London and give me a cold drink?"
- You call: `delegate_to_specialist_agent(agent_name='Weather Agent', query='What is the weather in London?')`
- You read result: "The weather is 10°C and chilly."
- You call: `delegate_to_specialist_agent(agent_name='Cocktail Agent', query='Suggest a cold, refreshing cocktail for a chilly day.')`
- You synthesize the two results into one final, polished answer.
"""


class AdkOrchestratorAgentExecutor(AgentExecutor, ABC):
    """
    Refactored Tool-Driven Orchestrator Executor.
    Relies on the delegate_to_specialist_agent tool and the LLM's prompt for all A2A logic.
    Uses Vertex AI persistent services for sessions and memory.
    """

    def __init__(self, remote_agent_addresses: list[str] = None, agent_engine_id: str = None, db_engine: AsyncEngine = None) -> None:
        """
        Initialize with the new Tool-Driven approach.
        """
        if not agent_engine_id:
            raise ValueError("agent_engine_id must be provided.")
        if not db_engine:
            raise ValueError("db_engine must be provided.")

        self.remote_agent_addresses = remote_agent_addresses
        self.agent = None
        self.runner = None
        self.agent_engine_id = agent_engine_id
        self.db_engine = db_engine

        self.project_id = os.environ.get("PROJECT_ID")
        self.location = os.environ.get("LOCATION")
        if not self.project_id or not self.location:
            raise ValueError(
                "Both PROJECT_ID and LOCATION must be set as environment variables."
            )

        _default_instrumentor_builder(
            project_id=self.project_id,
            enable_tracing=_telemetry_enabled(),
            enable_logging=_telemetry_enabled(),
        )

        self._init_agent()


    def _init_agent(self) -> None:
        """
        Initializes the ADK agent and runner with the A2A tool and Vertex AI services.
        """
        if self.agent is None:
            self.agent = LlmAgent(
                model="gemini-2.5-pro",
                instruction=ORCHESTRATOR_INSTRUCTION,
                tools=[
                    delegate_to_specialist_agent,
                    PreloadMemoryTool(),
                ], # ADK implicitly wraps these functions
                name="orchestrator_agent",
                description="The central routing agent for multi-step tasks.",
                before_model_callback=self.before_model_callback,
                after_agent_callback=auto_save_session_to_memory_callback,
            )

            my_memory_service = PersistentVertexAiMemoryBankService(
                project=self.project_id,
                location=self.location,
                agent_engine_id=self.agent_engine_id,
            )
            my_session_service = VertexAiSessionService(
                project=self.project_id,
                location=self.location,
                agent_engine_id=self.agent_engine_id,
            )

            self.runner = Runner(
                app_name=self.agent.name,
                agent=self.agent,
                artifact_service=InMemoryArtifactService(),
                session_service=my_session_service,
                memory_service=my_memory_service,
            )

    def before_model_callback(self, callback_context, llm_request):
        """Logs memories preloaded into the LLM request context."""
        if hasattr(llm_request, "context") and hasattr(llm_request.context, "related_data"):
            for data in llm_request.context.related_data:
                if data.source and data.source.startswith("memory_bank"):
                    logging.info(f"Preloaded Memory: {data.content.parts[0].text}")

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Process a user query using the ADK Runner and Tool-Driven logic."""

        raw_query = context.get_user_input()
        logging.info(f"Received raw input: {raw_query}")
        
        # 1. Fix Context ID: Generate a valid UUID if missing or 'pending_creation'
        context_id = context.context_id
        if not context_id or context_id == "pending_creation":
            import uuid
            context_id = str(uuid.uuid4())
            logging.info(f"Context ID was '{context.context_id}'. Generated new context_id: {context_id}")

        if context.message and context.message.metadata and "user_id" in context.message.metadata:
            user_id = context.message.metadata["user_id"]
        else:
            raise ValueError("user_id not found in message metadata.")

        logging.info(f"Executing request for user_id: '{user_id}' with context_id: '{context_id}'")

        # 2. Prepare Metadata (User ID & Timestamp Extension)
        import datetime
        timestamp_key = "github.com/a2aproject/a2a-samples/samples/extensions/timestamp/v1/timestamp"
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        task_metadata = {
            "user_id": user_id,
            timestamp_key: current_time
        }

        # 3. Initialize Updater with valid context_id
        updater = TaskUpdater(event_queue, context.task_id, context_id)

        if not context.current_task:
            # 4. Submit with metadata and description
            await updater.submit(
                description=f"Orchestrator handling query for user {user_id}",
                metadata=task_metadata
            )

        await updater.start_work()

        user_id_token = None
        updater_token = None
        try:
            user_id_token = user_id_context.set(user_id)
            updater_token = task_updater_context.set(updater)

            session_service = VertexAiSessionService(
                project=self.project_id,
                location=self.location,
                agent_engine_id=self.agent_engine_id,
            )
            session = await self._get_or_create_session(
                session_service, context_id, user_id=user_id
            )
            logging.info(f"Using session: {session.id} for user: {user_id}")

            content = genai_types.Content(role=Role.user, parts=[genai_types.Part(text=raw_query)])

            answer_sent = False
            async for event in self.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content,
            ):
                if event.is_final_response() and not answer_sent:
                    answer = self._extract_answer(event, raw_query)
                    logging.info(f"Final Answer: {answer}")

                    await updater.add_artifact(
                        [TextPart(text=answer)],
                        name="final_answer",
                    )
                    await updater.complete()
                    answer_sent = True

        except Exception as e:
            logging.error(f"Error during execution: {e!s}", exc_info=True)
            await updater.update_status(
                TaskState.failed, message=new_agent_text_message(f"Error: {e!s}")
            )
            raise
        finally:
            if user_id_token:
                user_id_context.reset(user_id_token)
            if updater_token:
                task_updater_context.reset(updater_token)

    async def _get_or_create_session(self, session_service: VertexAiSessionService, context_id: str, user_id: str):
        """
        Gets or creates a Vertex AI session, using the database to map A2A context_id
        to the Vertex AI session ID.
        """
        session_key = f"{user_id}-{context_id}"
        vertex_session_name = await get_session_mapping(self.db_engine, session_key)

        if vertex_session_name:
            logging.info(f"Found existing session mapping for key {session_key}: {vertex_session_name}")
            session_id_for_get = vertex_session_name.split('/')[-1]
            session = await session_service.get_session(
                app_name=self.runner.app_name,
                user_id=user_id,
                session_id=session_id_for_get,
            )
            if session:
                return session
            else:
                logging.warning(f"Session {vertex_session_name} not found on backend. Creating a new one.")

        logging.info(f"No valid session found for key {session_key}. Creating a new session.")
        new_session = await session_service.create_session(
            app_name=self.runner.app_name,
            user_id=user_id,
        )
        
        await set_session_mapping(self.db_engine, session_key, new_session.id)
        logging.info(f"Created and mapped new session {new_session.id} for key {session_key}")
        
        return new_session

    def _extract_answer(self, event, query: str) -> str:
        """Extract text answer from agent response."""
        parts = event.content.parts
        text_parts = [part.text for part in parts if part.text]

        answer = " ".join(text_parts) if text_parts else "No answer found."

        if answer.startswith(query):
            answer = answer[len(query):].strip()

        return answer

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> NoReturn:
        raise ServerError(error=UnsupportedOperationError())
