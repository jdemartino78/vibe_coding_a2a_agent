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
import time

from google import adk
from google.adk.memory import VertexAiMemoryBankService, base_memory_service
from google.genai import types
import vertexai


logger = logging.getLogger(__name__)


class PersistentVertexAiMemoryBankService(VertexAiMemoryBankService):
    """
    Fixed version of VertexAiMemoryBankService that keeps the httpx client alive.

    The original implementation creates a new Client (and httpx client) for each request,
    which causes "Cannot send a request, as the client has been closed" errors in
    deployed Agent Engine environments.

    This subclass maintains a single persistent Client (and thus API client) for the
    lifetime of the service, preventing premature httpx client closure.
    """

    def __init__(
        self, project: str = None, location: str = None, agent_engine_id: str = None
    ):
        super().__init__(
            project=project, location=location, agent_engine_id=agent_engine_id
        )
        # Create and cache both the Client and API client once
        self._persistent_client = None
        self._persistent_api_client = None

    def _get_api_client(self):
        """Override to return a persistent API client instead of creating new ones."""
        if self._persistent_api_client is None:
            # Keep the Client object alive to prevent httpx client closure
            self._persistent_client = vertexai.Client(
                project=self._project, location=self._location
            )
            self._persistent_api_client = self._persistent_client
        return self._persistent_api_client

    async def add_session_to_memory(self, session: adk.sessions.Session):
        client = self._get_api_client()
        agent_engine_name = (
            f"projects/{self._project}/locations/{self._location}/"
            f"reasoningEngines/{self._agent_engine_id}"
        )
        # Convert ADK session events to the format expected by Agent Engine SDK
        events_for_memory_bank = []
        for event in session.events:
            if event.content and event.content.parts:
                # Assuming simple text parts for now
                text_content = " ".join([p.text for p in event.content.parts if p.text])
                if text_content:
                    events_for_memory_bank.append({
                        "content": {"role": event.author, "parts": [{"text": text_content}]}
                    })

        if not events_for_memory_bank:
            logger.info(f"No meaningful events in session {session.id} for memory generation.")
            return

        session_resource_name = (
            f"projects/{self._project}/locations/{self._location}/"
            f"reasoningEngines/{self._agent_engine_id}/sessions/{session.id}"
        )
        logger.info(f"Memory generation for session: {session_resource_name}")

        logger.info(f"Events for memory bank: {events_for_memory_bank}")

        # *** ADD THE SCOPE EXPLICITLY ***
        # Ensure session.app_name is a string. It should be self.runner.app_name
        # or similar from where this is called. Assuming session object has app_name.
        if not session.app_name:
             logging.warning(f"session.app_name is not set for session {session.id}")
             # Fallback or raise error - for this fix, I'll use the runner's app_name
             app_name = self.runner.app_name
        else:
             app_name = session.app_name

        memory_scope = {"app_name": app_name, "user_id": session.user_id}
        logging.info(f"Using scope for memory generation: {memory_scope}")

        operation = client.agent_engines.memories.generate(
            name=agent_engine_name,
            vertex_session_source={"session": session_resource_name},
            config={"wait_for_completion": False},
            scope=memory_scope,  # *** PASS THE SCOPE HERE ***
        )
        logging.info(f"Memory generation operation: {operation.name}")

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> base_memory_service.SearchMemoryResponse:
        """Overrides the base search_memory to use the persistent client."""
        if not self._agent_engine_id:
            raise ValueError("Agent Engine ID is required for Memory Bank.")

        client = self._get_api_client()
        agent_engine_name = (
            f"projects/{self._project}/locations/{self._location}/"
            f"reasoningEngines/{self._agent_engine_id}"
        )

        scope = {"app_name": app_name, "user_id": user_id}
        similarity_search_params = {"search_query": query}

        logging.info(f"Searching memory with scope: {scope}, query: '{query}', params: {similarity_search_params}")

        try:
            retrieved_memories_iterator = client.agent_engines.memories.retrieve(
                name=agent_engine_name,
                scope=scope,
                similarity_search_params=similarity_search_params,
            )

            logging.info("Search memory API call complete.")

            # Consume iterator to log raw results
            raw_results = list(retrieved_memories_iterator)

            if not raw_results:
                logging.warning(f"NO MEMORIES RETRIEVED for scope {scope} and query '{query}'")
            else:
                logging.info(f"Raw retrieved memories ({len(raw_results)}): {raw_results}")

            memory_entries = []
            for retrieved_memory in raw_results:
                logging.debug(f"Processing raw retrieved memory: {retrieved_memory}")
                if hasattr(retrieved_memory, 'memory') and hasattr(retrieved_memory.memory, 'fact'):
                    memory_entries.append(
                        adk.memory.memory_entry.MemoryEntry(
                            author="user",  # Or appropriate author
                            content=types.Content(
                                parts=[types.Part(text=retrieved_memory.memory.fact)],
                                role="user",
                            ),
                            timestamp=retrieved_memory.memory.update_time.isoformat(),
                        )
                    )
                else:
                    logging.warning(f"Retrieved memory in unexpected format: {retrieved_memory}")

            return base_memory_service.SearchMemoryResponse(memories=memory_entries)

        except Exception as e:
            logging.error(f"Error during search_memory call: {e}", exc_info=True)
            return base_memory_service.SearchMemoryResponse(memories=[])
