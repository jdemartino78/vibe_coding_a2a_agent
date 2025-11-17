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
# Author: Gemini
import asyncio
from a2a.server.agent_execution import AgentExecutor, RequestContext
from shared.adk_orchestrator_agent import AdkOrchestratorAgentExecutor
from shared.custom_context_builder import CustomCallContextBuilder
from shared.dependencies import get_database_task_store, initialize_dependencies
import logging
import os
from dotenv import load_dotenv
from a2a.server.events import EventQueue

# Set logging
logging.getLogger().setLevel(logging.INFO)
load_dotenv()


from a2a.server.tasks import TaskStore

class OrchestratorAgentExecutor(AgentExecutor):
    """Agent Executor that wraps AdkOrchestratorAgentExecutor with environment-based
    configuration and a custom context builder, and provides stateful conversation
    management.
    """

    def __init__(self, agent_engine_id: str = None) -> None:
        """
        Initializes the OrchestratorAgentExecutor.

        Args:
            agent_engine_id: Optional agent engine ID.
        """
        self._core_executor = AdkOrchestratorAgentExecutor(
            remote_agent_addresses=[
                os.getenv("COCKTAIL_AGENT_URL", "http://localhost:10002"),
                os.getenv("WEA_AGENT_URL", "http://localhost:10001"),
            ],
            agent_engine_id=agent_engine_id,
        )
        self._task_store: TaskStore | None = None
        self._setup_lock = asyncio.Lock()

    async def _ensure_setup(self) -> None:
        """
        Ensures that the asynchronous setup (database initialization) is completed.
        Uses a lock to prevent race conditions during the first initialization.
        """
        if self._task_store is None:
            async with self._setup_lock:
                # Double-check after acquiring the lock to ensure initialization
                # hasn't happened while waiting.
                if self._task_store is None:
                    await initialize_dependencies()
                    self._task_store = get_database_task_store()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Executes the agent's logic for a given request context, first ensuring
        that the task context is valid and handling stateful conversation management.
        """
        # Ensure the database is initialized before proceeding.
        await self._ensure_setup()

        message = context.message
        if message and message.task_id:
            if self._task_store is None:
                # This should not happen due to _ensure_setup, but as a safeguard:
                raise RuntimeError("TaskStore not initialized.")
            task = await self._task_store.get(message.task_id)
            if task is None:
                # If the task does not exist (e.g., after a server restart),
                # nullify the task_id. This will cause the RequestContext logic
                # to generate a new task for a new conversation.
                message.task_id = None

        # Delegate the execution to the core agent logic.
        await self._core_executor.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Handles a cancellation request by delegating to the core executor.
        """
        await self._core_executor.cancel(context, event_queue)
