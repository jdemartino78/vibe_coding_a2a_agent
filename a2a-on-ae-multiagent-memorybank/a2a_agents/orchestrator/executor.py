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
import json
import re
from typing import NoReturn, Optional, Dict, Any

# A2A Imports
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskStore, TaskUpdater
from a2a.types import Role, TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from dotenv import load_dotenv

# ADK Imports
from google.adk import Runner
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import VertexAiSessionService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.plugins.logging_plugin import LoggingPlugin
from google.genai import types as genai_types
from vertexai.preview.reasoning_engines.templates.adk import (
    _default_instrumentor_builder,
)

# Custom Imports
from shared.tools import delegate_to_specialist_agent, user_id_context, task_updater_context
from shared.services import PersistentVertexAiMemoryBankService
from shared.database.sessions import get_session_mapping, set_session_mapping, initialize_session_store
from shared.database.connection import get_database_task_store, get_db_engine

# Load environment variables
load_dotenv()

MAX_ORCHESTRATION_TURNS = 5

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
You are a master orchestrator agent. Your purpose is to fulfill user requests by breaking them down into steps and delegating those steps to the correct specialized agent using the 'delegate_to_specialist_agent' tool. After you have gathered all necessary information, provide a concise final answer in Markdown.

**AVAILABLE SPECIALIZED AGENTS:**
- **Cocktail Agent**: Use for questions about cocktails, recipes, or ingredients. **Limitation: Can handle 'warming', 'refreshing', 'sophisticated' type queries.**
- **Weather Agent**: Use for questions about weather or forecasts. **Limitation: This agent only supports locations within the United States.**

**OUTPUT FORMAT:**
Your response MUST be a single JSON object. It should contain EITHER a tool call OR a final answer.
DO NOT output any text outside the JSON object.

**A. Tool Call:** If you need to delegate to a specialized agent:
```json
{
  "tool_name": "delegate_to_specialist_agent",
  "tool_query": {
    "agent_name": "[Name of agent: 'Cocktail Agent' or 'Weather Agent']",
    "query": "[Specific query for the specialized agent]"
  }
}
```

**B. Final Answer:** If you have gathered all information and are ready to respond to the user:
```json
{
  "final_answer": "[Your comprehensive answer in Markdown format]"
}
```

**CRITICAL RULES FOR TOOL CALLS:**
1.  **Capability Check:** Before delegating, always verify if the request is within the specialized agent's capabilities (e.g., Weather Agent only for US locations). If not, provide a `final_answer` explaining the limitation.
2.  **Translate Vibe:** If the user asks for a 'vibe' (e.g., 'warming', 'refreshing') for a cocktail, directly translate that into the `query` for the 'Cocktail Agent'. The Cocktail Agent is now smart enough to understand these. 
3.  **Sequential Execution:** Always make one tool call, wait for its result, and process it before considering the next step. DO NOT make parallel tool calls.
4.  **Information Synthesis:** After all necessary tool calls are made and information is gathered, formulate a `final_answer` for the user in Markdown. Wrap this markdown in the JSON structure shown above.

**MEMORY:**
- Remember previous turns in the conversation to maintain context.
- Utilize pre-loaded memories for historical context. Use your memory to recall context from the conversation to answer questions.

**LOCATION NORMALIZATION:**
- If the user provides a common abbreviation like 'NYC' or 'LA', you must resolve it to the full name (e.g., 'New York, NY', 'Los Angeles, CA') before calling the 'Weather Agent'.

**EXAMPLE SCENARIOS (Illustrative, do not copy verbatim):**
- **User:** "What's the weather in Seattle and what should I drink?"
  - **Your Output:**
    ```json
    {
      "tool_name": "delegate_to_specialist_agent",
      "tool_query": {
        "agent_name": "Weather Agent",
        "query": "What is the weather in Seattle, WA?"
      }
    }
    ```
  - **After Weather Agent responds:** (Assuming weather is cold)
    ```json
    {
      "tool_name": "delegate_to_specialist_agent",
      "tool_query": {
        "agent_name": "Cocktail Agent",
        "query": "Suggest a warming cocktail for cold weather."
      }
    }
    ```
  - **After Cocktail Agent responds:**
    ```json
    {
      "final_answer": "The weather in Seattle is cold. I recommend a Hot Toddy... [Martini Recipe]"
    }
    ```

- **User:** "What ingredients are in a Margarita?"
  - **Your Output:**
    ```json
    {
      "tool_name": "delegate_to_specialist_agent",
      "tool_query": {
        "agent_name": "Cocktail Agent",
        "query": "What ingredients are in a Margarita?"
      }
    }
    ```
  - **After Cocktail Agent responds:**
    ```json
    {
      "final_answer": "A Margarita contains Tequila, Triple Sec, and Lime Juice."
    }
    ```
"""


class OrchestratorAgentExecutor(AgentExecutor):
    """
    Refactored Tool-Driven Orchestrator Executor.
    Merges initialization logic directly into the executor.
    Uses Vertex AI persistent services for sessions and memory.
    """

    def __init__(self, agent_engine_id: Optional[str] = None, **kwargs) -> None:
        """
        Initialize with the new Tool-Driven approach.
        """
        super().__init__(**kwargs)
        self.agent_engine_id = agent_engine_id
        self._task_store: TaskStore | None = None
        self._setup_lock = asyncio.Lock()
        self.agent = None
        self.runner = None
        self.db_engine = None

        self.project_id = os.environ.get("PROJECT_ID")
        self.location = os.environ.get("LOCATION")
        if not self.project_id or not self.location:
            # Allow initialization even if env vars missing, they might be checked later or injected
            logging.warning("PROJECT_ID or LOCATION env vars are missing.")

        if self.project_id:
            _default_instrumentor_builder(
                project_id=self.project_id,
                enable_tracing=_telemetry_enabled(),
                enable_logging=_telemetry_enabled(),
            )

    async def _ensure_setup(self) -> None:
        """
        Ensures that the asynchronous setup (database initialization, agent setup) is completed.
        Uses a lock to prevent race conditions during the first initialization.
        """
        if self._task_store is None:
            async with self._setup_lock:
                if self._task_store is None:
                    logging.info("Starting OrchestratorAgentExecutor setup...")
                    
                    # Wrap synchronous database initialization in asyncio.to_thread
                    self._task_store = await asyncio.to_thread(get_database_task_store)
                    self.db_engine = await asyncio.to_thread(get_db_engine)
                    await initialize_session_store(self.db_engine)
                    
                    self._init_agent()
                    logging.info("OrchestratorAgentExecutor setup complete.")

    def _init_agent(self) -> None:
        """
        Initializes the ADK agent and runner with the A2A tool and Vertex AI services.
        """
        if self.agent is None:
            if not self.agent_engine_id:
                 logging.warning("agent_engine_id not provided, skipping ADK agent initialization (logic might fail)")
                 return

            # 1. Configure Agent with Static Instruction for Caching
            self.agent = LlmAgent(
                model="gemini-2.5-flash",
                static_instruction=ORCHESTRATOR_INSTRUCTION,  # Cached system prompt
                instruction="",  # Dynamic/Turn-based prompt (unused for now)
                tools=[
                    delegate_to_specialist_agent,
                    PreloadMemoryTool(),
                ], 
                name="orchestrator_agent",
                description="The central routing agent for multi-step tasks.",
                before_model_callback=self.before_model_callback,
                after_agent_callback=auto_save_session_to_memory_callback,
            )

            # 2. Configure App with Optimization Settings
            app = App(
                name="a2a_orchestrator_app",
                root_agent=self.agent,
                context_cache_config=ContextCacheConfig(
                    min_tokens=1000,  # Only cache if prompt > 1000 tokens
                    ttl_seconds=3600, # Keep cache alive for 1 hour
                ),
                events_compaction_config=EventsCompactionConfig(
                    compaction_interval=5,  # Summarize every 5 turns
                    overlap_size=2,         # Keep 2 turns of overlap
                ),
                plugins=[LoggingPlugin()],
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

            # 3. Initialize Runner with the App
            self.runner = Runner(
                app=app,  # Pass the configured App instead of just the agent
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
        await self._ensure_setup()

        message = context.message
        if message and message.task_id:
            if self._task_store is None:
                raise RuntimeError("TaskStore not initialized.")
            task = await self._task_store.get(message.task_id)
            if task is None:
                logging.warning(f"Task {message.task_id} not found. Treating as new conversation.")
                message.task_id = None

        raw_query = context.get_user_input()
        logging.info(f"Received raw input: {raw_query}")
        
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

        import datetime
        timestamp_key = "github.com/a2aproject/a2a-samples/samples/extensions/timestamp/v1/timestamp"
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        task_metadata = {
            "user_id": user_id,
            timestamp_key: current_time
        }

        updater = TaskUpdater(event_queue, context.task_id, context_id)

        if not context.current_task:
            try:
                logging.info(f"Attempting to submit task {context.task_id} via TaskUpdater...")
                await updater.update_status(
                    state=TaskState.submitted,
                    message=new_agent_text_message(f"Orchestrator handling query for user {user_id}"),
                    metadata=task_metadata
                )
                logging.info("Task submission event enqueued successfully.")

            except Exception as e:
                logging.error(f"Failed to submit task via TaskUpdater: {e}", exc_info=True)

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

            # Delegate to extracted reasoning loop logic
            final_response_text = await self._run_reasoning_loop(session, user_id, raw_query, updater)
            
            # --- Final Response Handling ---
            if not final_response_text: 
                 final_response_text = "Error: No final response generated."

            await updater.add_artifact(
                [TextPart(text=final_response_text)],
                name="final_answer",
            )
            await updater.complete()

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

    async def _run_reasoning_loop(
        self, session: Any, user_id: str, raw_query: str, updater: TaskUpdater
    ) -> str:
        """
        Executes the core reasoning loop: LLM -> Tool Call -> LLM -> Final Answer.
        
        Args:
            session: The Vertex AI session object.
            user_id: The ID of the user.
            raw_query: The user's initial query.
            updater: The TaskUpdater for logging.

        Returns:
            The final text response to be returned to the user.
        """
        tool_result: Optional[str] = None
        final_response_text: Optional[str] = None
        turns = 0 

        while final_response_text is None and turns < MAX_ORCHESTRATION_TURNS:
            turns += 1

            # Construct the message for the LLM
            llm_message_parts = [genai_types.Part(text=raw_query)]
            if tool_result:
                llm_message_parts.append(genai_types.Part(text=f"Tool Result: {tool_result}"))
                tool_result = None # Consume the tool result after passing it to the LLM

            content = genai_types.Content(role=Role.user, parts=llm_message_parts)
            
            if not self.runner:
                raise RuntimeError("ADK Runner is not initialized.")

            llm_output = ""
            try:
                async for event in self.runner.run_async(
                    session_id=session.id,
                    user_id=user_id,
                    new_message=content,
                ):
                    if event.is_final_response():
                        llm_output = self._extract_answer(event, raw_query)
            except Exception as e:
                logging.error(f"Error during Orchestrator run_async: {e}", exc_info=True)
                return f"Error: An unexpected error occurred during orchestration: {e}"

            logging.info(f"Orchestrator LLM Raw Output: {llm_output}")

            # Robust JSON Parsing and Decision Making
            parsed_output = self._parse_llm_output(llm_output)

            if "final_answer" in parsed_output:
                final_response_text = parsed_output["final_answer"]
            elif "tool_name" in parsed_output and "tool_query" in parsed_output:
                tool_name = parsed_output["tool_name"]
                tool_query_args = parsed_output["tool_query"]
                
                if tool_name == "delegate_to_specialist_agent":
                    agent_name = tool_query_args.get("agent_name")
                    query = tool_query_args.get("query")

                    if agent_name and query:
                        logging.info(f"Orchestrator delegating to {agent_name} with query: '{query}'")
                        tool_result = await delegate_to_specialist_agent(agent_name=agent_name, query=query) # type: ignore
                        logging.info(f"Received tool result from {agent_name}: {tool_result}")
                    else:
                        logging.error(f"Invalid arguments for delegate_to_specialist_agent: {tool_query_args}")
                        final_response_text = f"Error: Invalid delegation command: {tool_query_args}"
                else:
                    logging.error(f"Unknown tool_name in LLM output: {tool_name}")
                    final_response_text = f"Error: Orchestrator tried to use an unknown tool: {tool_name}"
            else:
                # Fallback if structure is lost, but some text exists, or unknown structure
                logging.warning(f"Orchestrator LLM output did not conform to expected JSON structure: {parsed_output}")
                final_response_text = parsed_output.get("final_answer", f"Error: Orchestrator failed to understand its own plan based on output: {llm_output}")
        
        if not final_response_text:
            final_response_text = f"Error: Orchestrator exceeded maximum {MAX_ORCHESTRATION_TURNS} turns. Please try again with a more specific query."
            
        return final_response_text

    async def _get_or_create_session(self, session_service: VertexAiSessionService, context_id: str, user_id: str):
        """
        Gets or creates a Vertex AI session, using the database to map A2A context_id
        to the Vertex AI session ID.
        """
        # Define the agent name for scoping the session
        agent_name = "orchestrator"
        
        vertex_session_name = await get_session_mapping(self.db_engine, user_id, context_id, agent_name)

        if vertex_session_name:
            logging.info(f"Found existing session mapping for user {user_id}, context {context_id}, agent {agent_name}: {vertex_session_name}")
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

        logging.info(f"No valid session found for user {user_id}, context {context_id}, agent {agent_name}. Creating a new session.")
        new_session = await session_service.create_session(
            app_name=self.runner.app_name,
            user_id=user_id,
        )
        
        await set_session_mapping(self.db_engine, user_id, context_id, agent_name, new_session.id)
        logging.info(f"Created and mapped new session {new_session.id} for user {user_id} and context {context_id}")
        
        return new_session

    def _extract_answer(self, event, query: str) -> str:
        """Extract text answer from agent response."""
        parts = event.content.parts
        text_parts = [part.text for part in parts if part.text]

        answer = " ".join(text_parts) if text_parts else "No answer found."

        if answer.startswith(query):
            answer = answer[len(query):].strip()

        return answer

    def _parse_llm_output(self, output: str) -> Dict[str, Any]:
        """Robustly parse JSON from LLM output, handling markdown and malformed cases."""
        # 1. Attempt direct JSON parse
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass # Fall through to more robust parsing

        # 2. Try to find a JSON code block (```json...```)
        match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse JSON from ```json block: {match.group(1)}")

        # 3. Try to find a generic code block (```...```)
        match = re.search(r"```\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse JSON from generic ``` block: {match.group(1)}")

        # 4. Try to find the first '{' and last '}' for a raw JSON string
        start = output.find('{')
        end = output.rfind('}')
        if start != -1 and end != -1 and end > start:
            potential_json_str = output[start:end+1]
            try:
                return json.loads(potential_json_str)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse JSON from raw braces: {potential_json_str}")

        # 5. If all JSON parsing attempts fail, check if it resembles a tool call (heuristic)
        # If it contains "tool_name" but isn't valid JSON, it's likely a malformed tool call attempt
        if "tool_name" in output or "final_answer" in output:
            logging.error(f"LLM output appears to be a malformed JSON tool call/final answer: {output}")
            return {"final_answer": f"Error: Orchestrator received malformed JSON. Raw output: {output}"}

        # 6. Default to treating the entire output as a final answer text
        logging.info(f"LLM output is not JSON and not a malformed tool call, treating as direct text response: {output}")
        return {"final_answer": output.strip()}

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> NoReturn:
        raise ServerError(error=UnsupportedOperationError())