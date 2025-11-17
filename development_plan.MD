## Step 4 (Optional): Enhance the Gradio Frontend with a Distinctive UI

While the backend refactoring requires no frontend changes to function, we can apply a strong design philosophy to make the user interface more visually appealing and informative. This section provides a complete, drop-in replacement for your Gradio `main.py` to implement a "Retro-Futuristic Terminal" aesthetic and add a display for agent hand-offs.

**Action:** Replace the contents of `a2a-on-ae-multiagent-memorybank/a2a_multiagent_mcp_app/frontend_option1/main.py` with the following code.

**Code:**

```python
# FILE: frontend_option1/main.py

import gradio as gr
import time
import random
import json

# --- 1. The Custom CSS for our Retro-Futuristic Terminal Aesthetic ---
css = """
/* --- Typography: Import a distinctive, retro, monospaced font --- */
@import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

/* --- Color & Theme: Define a cohesive, high-contrast theme --- */
:root {
    --accent-color: #00ff99;
    --background-color: #0a0a0a;
    --text-color: #e0e0e0;
    --border-color: rgba(0, 255, 153, 0.3);
    --glow-color: rgba(0, 255, 153, 0.5);
    --container-bg: #141414;
}

/* --- Global Styles & Background Details --- */
body, .gradio-container {
    background-color: var(--background-color) !important;
    font-family: 'VT323', monospace !important;
    color: var(--text-color) !important;
}
/* Add a subtle noise/scanline texture to the background */
body::before {
    content: " ";
    display: block;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0.05;
    background-image: linear-gradient(0deg, transparent 50%, rgba(0, 255, 153, 0.3) 50%);
    background-size: 3px 3px;
    pointer-events: none;
    z-index: -1;
}

/* --- Spatial Composition & Component Styling --- */
#chatbot .message-bubble {
    background-color: var(--container-bg) !important;
    border: 1px solid var(--border-color) !important;
    box-shadow: 0 0 10px var(--glow-color), inset 0 0 5px rgba(0,0,0,0.5) !important;
    border-radius: 4px !important;
    color: var(--text-color) !important;
    padding: 12px !important;
    margin: 8px 0 !important;
}
#chatbot .message-bubble.user {
    background-color: #1a1a1a !important;
    border-color: rgba(255, 255, 255, 0.2) !important;
    box-shadow: none !important;
}

/* --- The Agent Hand-off Box --- */
#agent_activity_log {
    background-color: var(--container-bg);
    border: 1px solid var(--border-color);
    padding: 10px 15px;
    border-radius: 4px;
    text-align: center;
    font-size: 1.2em;
    color: var(--accent-color);
    box-shadow: 0 0 8px var(--glow-color);
    margin-bottom: 20px;
    transition: all 0.3s ease;
}
#agent_activity_log p {
    margin: 0;
}

/* --- Motion: Blinking Cursor Effect for the Text Input --- */
#chat_input textarea {
    background-color: var(--container-bg) !important;
    color: var(--text-color) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 4px !important;
    font-size: 1.2em !important;
    padding-left: 15px !important;
}
#chat_input .gr-input-label { display: none; } /* Hide the default label */
#chat_input textarea::placeholder {
    color: var(--border-color);
    opacity: 1;
}
@keyframes blink { 50% { opacity: 0; } }
#chat_input textarea:focus::after {
    content: '_';
    display: inline-block;
    animation: blink 1s step-end infinite;
    color: var(--accent-color);
    margin-left: 2px;
}
"""

# --- 2. The Gradio Application Layout ---
with gr.Blocks(css=css, theme=gr.themes.Base()) as demo:
    gr.Markdown("# V.I.B.E. - Visual Interface for Bot Execution")

    agent_activity_log = gr.Markdown(
        "**SYSTEM STATUS:** STANDBY",
        elem_id="agent_activity_log"
    )

    chatbot = gr.Chatbot(elem_id="chatbot", height=500)
    chat_input = gr.Textbox(
        elem_id="chat_input",
        placeholder="> Enter your command...",
        show_label=False,
        container=False
    )

    # --- 3. Backend Logic Integration ---
    # This function needs to be adapted to call your actual HostingAgentExecutor
    def handle_user_query(message, chat_history):
        # This is where you will call your refactored HostingAgentExecutor
        # For now, we use a mock function to demonstrate the UI updates.
        
        # 1. Update UI to show the agent is thinking
        yield chat_history, gr.update(value="**SYSTEM STATUS:** ORCHESTSTRATOR PROCESSING...", interactive=False), gr.update(interactive=False)

        # MOCK: Simulate calling the HostingAgentExecutor
        # In your real implementation, you would replace this section
        # with the actual call to your agent's `execute` method.
        time.sleep(1.5) # Simulate network latency
        
        # MOCK: Simulate a multi-step plan
        yield chat_history, gr.update(value="**SYSTEM STATUS:** ROUTING TO `WeatherAgent`..."), gr.update(interactive=False)
        time.sleep(1.5)
        
        yield chat_history, gr.update(value="**SYSTEM STATUS:** SYNTHESIZING RESPONSE..."), gr.update(interactive=False)
        time.sleep(1)

        # MOCK: Final response from the agent
        bot_.message = f"This is a simulated response for '{message}'. The weather is clear, so how about a refreshing Mojito?"
        chat_history.append((message, bot_message))

        # 4. Update UI with the final response and reset state
        yield chat_history, gr.update(value="**SYSTEM STATUS:** STANDBY", interactive=True), gr.update(value="", interactive=True)


    chat_input.submit(
        handle_user_query,
        [chat_input, chatbot],
        [chatbot, agent_activity_log, chat_input]
    )

if __name__ == "__main__":
    demo.launch()
```
**Note on Frontend Integration:** The mock function `handle_user_query` uses `yield` to stream updates to the UI, showing the agent's status in real-time. To make this work with your actual agent, you will need to adapt your `HostingAgentExecutor` to stream status updates back to the Gradio frontend. This can be done by having the `execute` method `yield` status strings before returning the final result.

---

## Appendix: Handling Advanced Queries & MCP Tool Capabilities

This new architecture changes how you should think about the capabilities of your specialist agents.

**Your `CocktailAgent`'s MCP tools are for data lookup, not reasoning.** They can `search`, `list`, and `lookup`, but they cannot answer a subjective question like "what's a good drink for a chilly day?".

This is the correct design. Your specialist agents should be simple and robust data providers.

**The orchestrator's powerful LLM should handle all creative reasoning.**

With the new prompt, the orchestrator will now follow this intelligent workflow for a subjective query:

1.  **Orchestrator LLM Reasoning:** "The user wants a suggestion. The `Cocktail Agent` can't 'suggest', but it can list cocktails. I will ask it for a classic or random cocktail, and then use my own world knowledge to determine if it's suitable for a chilly evening."
2.  **Orchestrator Tool Call:** `delegate_to_specialist_agent(agent_name='Cocktail Agent', query='list a random cocktail')`
3.  **Tool Result:** `"ID: 11001, Name: Old Fashioned, Category: Classic..."`
4.  **Orchestrator LLM Synthesis (Final Answer):** "For a chilly evening, a classic **Old Fashioned** is a great choice. It's a warming drink made with whiskey that's perfect for sipping by the fire."

This pattern fully leverages the power of your central orchestrator, keeps the specialist agents simple and focused, and is the most efficient way to handle complex, multi-faceted user requests.


# Agent Development Best Practices: Learnings from Debugging Session

This document summarizes key learnings and recommendations from a recent debugging session focused on an A2A multi-agent system. The session highlighted common challenges in agentic development, particularly around dependency management, API design for LLM consumption, and proactive system maintenance.

---

## 1. The Ripple Effect of Dependency Management

**Problem:** A seemingly minor dependency update (`a2a-sdk` from `0.3.7` to `>=0.3.12`) triggered a cascade of breaking changes across multiple components:
*   `A2ACardResolver` constructor signature changed.
*   `ClientFactory.connect` method signature changed.
*   `Part.from_text` class method was removed.
*   `client.send_message` changed from returning an awaitable to an `async_generator`.

**Learning:** This is a classic example of "Dependency Hell." Even minor version bumps in external libraries can introduce significant breaking changes, especially in rapidly evolving ecosystems.

**Recommendation:**
*   **Explicit & Locked Dependencies:** Continue using tools like `pyproject.toml` and `uv.lock` to explicitly define and lock dependency versions. This ensures consistent environments across development and deployment.
*   **Cautious Upgrades:** Treat dependency upgrades as deliberate acts. Always review library changelogs for breaking changes before upgrading.
*   **Automated Testing (See below):** A robust test suite is the ultimate safety net for dependency updates.

---

## 2. API Design for LLM Consumption: The "Stateless Tool" Principle

**Problem:** The `delegate_to_specialist_agent` tool was initially designed to be "stateful," requiring the orchestrator LLM to manage and pass `context_id` and `task_id` for multi-turn conversations. This complex signature (`param: str | None = None`) caused the Google ADK's automatic tool parser to fail with a `ValueError`.

**Learning:** LLMs, while powerful, are automated consumers of tool definitions. Their underlying frameworks (like ADK) often have limitations in parsing complex function signatures for automatic tool calling. Simplicity is key.

**Recommendation:**
*   **Stateless Tools:** Design tools to be as stateless and simple as possible from the LLM's perspective.
    *   **Tool Signature:** Aim for minimal, unambiguous parameters (e.g., `tool_name(agent_name: str, query: str)`).
    *   **Context Management:** Push the responsibility of maintaining conversational context up to the orchestrator LLM's reasoning layer. The LLM should formulate complete, self-contained queries for each turn (e.g., "What is the weather in NYC tomorrow?" instead of just "What about tomorrow?").
    *   **Return Values:** Tools should return simple, easily parsable data (e.g., a plain string) rather than complex JSON objects that the LLM then needs to deconstruct for state.
*   **Benefit:** This approach makes tools robust, compatible with automatic parsing, and reduces the cognitive load on the LLM, leading to more reliable agent behavior.

---

## 3. Proactive Maintenance: Heeding Warnings

**Problem:** We encountered `FutureWarning` from `google-cloud-aiplatform` regarding `google-cloud-storage` and a `uv` warning about an invalid `google-auth[openid]` extra. These were not immediate errors but indicated future breakage or incorrect configuration.

**Learning:** Warnings are "bugs that haven't happened yet." Ignoring them accumulates technical debt and makes future maintenance more difficult.

**Recommendation:**
*   **Address Warnings Promptly:** Treat warnings as high-priority items. Investigate their cause and apply fixes (e.g., updating dependency versions, correcting dependency specifiers) proactively.
*   **Clean Dependency Files:** Maintain clean and accurate `pyproject.toml` (or `requirements.txt`) files. Remove deprecated or invalid specifiers.
*   **Benefit:** Prevents unexpected breakages during future upgrades and ensures a stable, predictable development environment.

---

## Strategic Improvements for Future Development

Beyond the immediate fixes, consider these strategic improvements:

### A. Introduce Automated Testing

*   **Recommendation:** Implement a comprehensive testing strategy using `pytest`.
    *   **Unit Tests:** For critical components like `a2a_tools.py`, write unit tests that mock external dependencies (e.g., `SHARED_CLIENT_FACTORY.connect`) to verify internal logic in isolation.
    *   **Integration Tests:** Develop tests that run against deployed agents to validate end-to-end communication and functionality.
*   **Benefit:** Provides a crucial safety net for all changes, accelerates development, and builds confidence in the system's correctness.

### B. Centralize and Decouple Configuration

*   **Recommendation:** Move environment-specific configurations (like `REMOTE_AGENT_URL_VARS`) out of code files and into a dedicated configuration management system (e.g., a `config.yaml` file, or a `settings.py` module).
*   **Benefit:** Improves modularity, simplifies adding new agents, and makes the system easier to configure and deploy across different environments without code changes.

### C. Enhance Specific Error Handling

*   **Recommendation:** Instead of catching generic `Exception`s, catch specific exceptions provided by libraries (e.g., `a2a.client.errors.A2AClientHTTPError`).
*   **Benefit:** Allows the orchestrator LLM to provide more nuanced and helpful responses to users based on the specific type of failure (e.g., "Agent not found" vs. "Agent temporarily unavailable"), leading to a more intelligent and robust user experience.

By adopting these practices, your agentic system will become more resilient, maintainable, and scalable, ready to handle the complexities of ongoing development.

---
# Future Enhancement: Implement a Persistent Task Store

The current implementation uses an `InMemoryTaskStore`, which is suitable for local development but not for a scalable, production environment. To make the agent robust, the task store should be replaced with a persistent, distributed solution. The following plan is based on the `a2a-sdk`'s `DatabaseTaskStore` and best practices for cloud deployment.

## Plan

1.  **Add Dependencies:** Modify the `pyproject.toml` to include the necessary database drivers and libraries. The `a2a-sdk` provides a convenient extra for this.
    *   **Action:** Change `"a2a-sdk>=0.3.12"` to `"a2a-sdk[sql]>=0.3.12"`. This will install `SQLAlchemy`.

2.  **Create a Shared Database Engine:** In a shared module (e.g., `shared/database.py`), create a function to initialize and return a `sqlalchemy.ext.asyncio.AsyncEngine`. This ensures all parts of the application use the same database connection pool. For production, this would connect to a service like **Google Cloud AlloyDB** or **Cloud SQL**.
    *   **Example (`shared/database.py`):**
        ```python
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
        from google.cloud.alloydb.connector import AsyncConnector
        import os

        # This should be a singleton or cached
        _engine = None

        async def get_db_engine() -> AsyncEngine:
            global _engine
            if _engine:
                return _engine

            # In production, use the AlloyDB connector
            # For local testing, you could use a simple SQLite connection:
            # _engine = create_async_engine("sqlite+aiosqlite:///./tasks.db")
            
            connector = AsyncConnector()
            
            async def get_conn():
                return await connector.connect(
                    os.environ["ALLOYDB_INSTANCE_URI"],
                    "asyncpg",
                    user=os.environ["ALLOYDB_USER"],
                    password=os.environ["ALLOYDB_PASS"],
                    db=os.environ["ALLOYDB_NAME"],
                )

            _engine = create_async_engine("postgresql+asyncpg://", async_creator=get_conn)
            return _engine
        ```

3.  **Replace `InMemoryTaskStore` in `StatefulAgentExecutor`:** Modify `shared/stateful_agent_executor.py` to use the `DatabaseTaskStore`.
    *   **Action:**
        ```python
        # In shared/stateful_agent_executor.py

        # Remove InMemoryTaskStore import
        from a2a.server.tasks import DatabaseTaskStore
        from shared.database import get_db_engine # Import the new engine function
        import asyncio

        class StatefulAgentExecutor(AgentExecutor):
            _task_store = None
            _task_store_lock = asyncio.Lock()

            def __init__(self) -> None:
                # The initialization of the task store now needs to be async
                # This should be called from an async context before the first request.
                pass

            async def _initialize_task_store(self):
                async with self._task_store_lock:
                    if StatefulAgentExecutor._task_store is None:
                        engine = await get_db_engine()
                        db_task_store = DatabaseTaskStore(engine)
                        await db_task_store.initialize() # Create tables if they don't exist
                        StatefulAgentExecutor._task_store = db_task_store
            
            # ... rest of the class ...
            # The __init__ would need to be refactored to handle the async initialization
            # of the task store, perhaps by having a factory method.
        ```
    *   **Note:** This change requires refactoring the `__init__` method to handle the asynchronous initialization of the database engine. A common pattern is to have an async factory function that creates the `StatefulAgentExecutor` instance after the database is ready.

4.  **Configure Environment:** The deployment environment (e.g., Cloud Run) must be configured with the necessary environment variables (`ALLOYDB_INSTANCE_URI`, `ALLOYDB_USER`, etc.) and the appropriate IAM permissions for the service account to access the database.

5.  **Testing:** Thoroughly test the new implementation to ensure that conversation state persists across agent restarts and can be accessed correctly.

---
# Future Enhancement: Implement a Persistent Session Store for Conversation History

**Problem:** The current implementation uses an in-memory Python dictionary (`CONTEXT_ID_TO_SESSION_MAP`) to map a conversation's `context_id` to the underlying ADK session. If the agent server restarts, this mapping is lost. While our recent fix prevents the application from crashing, the agent will forget the conversation history and start a new session, breaking the continuity of multi-turn interactions.

**Solution:** To ensure true conversational persistence, this in-memory map must be replaced with a durable, distributed key-value store. For a Google Cloud environment, **Firestore in Datastore Mode** is an excellent choice due to its simplicity, scalability, and low operational overhead for this use case.

## Plan

1.  **Add Dependencies:** Add the Google Cloud Firestore library to the project's dependencies in `pyproject.toml`.
    *   **Action:** Add `"google-cloud-firestore"` to the `[tool.poetry.dependencies]` section.

2.  **Create a Session Store Module:** Create a new file, `shared/session_store.py`, to manage interactions with Firestore. This will abstract the database logic from the agent executor.
    *   **Example (`shared/session_store.py`):**
        ```python
        from google.cloud import firestore
        import os

        _db = None

        def _get_db():
            global _db
            if _db is None:
                project_id = os.environ.get("PROJECT_ID")
                _db = firestore.AsyncClient(project=project_id)
            return _db

        async def get_session_mapping(key: str) -> str | None:
            """Retrieves the Vertex AI session ID for a given context key."""
            db = _get_db()
            doc_ref = db.collection("session_mappings").document(key)
            doc = await doc_ref.get()
            if doc.exists:
                return doc.to_dict().get("vertex_session_name")
            return None

        async def set_session_mapping(key: str, vertex_session_name: str):
            """Saves the mapping between a context key and a Vertex AI session ID."""
            db = _get_db()
            doc_ref = db.collection("session_mappings").document(key)
            await doc_ref.set({"vertex_session_name": vertex_session_name})
        ```

3.  **Refactor `AdkOrchestratorAgentExecutor`:** Modify `shared/adk_orchestrator_agent.py` to use the new `session_store` instead of the in-memory dictionary.
    *   **Action:**
        ```python
        # In shared/adk_orchestrator_agent.py

        # Remove the CONTEXT_ID_TO_SESSION_MAP dictionary
        # from shared.session_store import get_session_mapping, set_session_mapping

        # ... inside AdkOrchestratorAgentExecutor ...

        async def _get_or_create_session(self, session_service: VertexAiSessionService, context_id: str, user_id: str):
            session_key = f"{user_id}-{context_id}"
            vertex_session_name = await get_session_mapping(session_key) # Use Firestore getter

            if vertex_session_name:
                # ... (logic to get session from service) ...

            # ... (logic to create new session) ...
            new_session = await session_service.create_session(...)

            await set_session_mapping(session_key, new_session.id) # Use Firestore setter
            return new_session
        ```

4.  **Configure Environment & IAM:** The service account for the agent will need the `Cloud Datastore User` role to read from and write to Firestore.

5.  **Testing:** Deploy the updated agent and verify that if you stop and restart the server, you can continue a conversation and the agent remembers the context from previous turns.
---
# Refactoring for Production-Readiness: Dependency Injection

To prepare the agent for a production environment and the introduction of the `DatabaseTaskStore`, the code should be refactored to use the **Dependency Injection** pattern. This will simplify the code, make it more testable, and handle asynchronous initialization gracefully.

**Problem:** Currently, classes create their own dependencies internally (e.g., `StatefulAgentExecutor` creates its own `InMemoryTaskStore`). This hides dependencies, makes testing difficult, and complicates the asynchronous setup required for a database connection.

**Solution:** We will create dependencies like the `TaskStore` at the application's entry point and "inject" them into the classes that need them.

## Plan

### Step 1: Decouple the `TaskStore` from `StatefulAgentExecutor`
Modify `StatefulAgentExecutor` to accept a `TaskStore` in its constructor instead of creating one itself.

*   **File:** `a2a-on-ae-multiagent-memorybank/a2a_agents/shared/stateful_agent_executor.py`
*   **Action:** Refactor the `__init__` method.

    **Before:**
    ```python
    class StatefulAgentExecutor(AgentExecutor):
        _task_store = None

        def __init__(self) -> None:
            if StatefulAgentExecutor._task_store is None:
                StatefulAgentExecutor._task_store = InMemoryTaskStore()

            core_executor = self._get_core_executor()
            self._request_handler = DefaultRequestHandler(
                agent_executor=core_executor,
                task_store=StatefulAgentExecutor._task_store,
            )
    ```

    **After:**
    ```python
    from a2a.server.tasks import TaskStore # Import the base class

    class StatefulAgentExecutor(AgentExecutor):
        def __init__(self, core_executor: AgentExecutor, task_store: TaskStore) -> None:
            self._task_store = task_store
            self._request_handler = DefaultRequestHandler(
                agent_executor=core_executor,
                task_store=self._task_store,
            )
    ```

### Step 2: Update the `OrchestratorAgentExecutor` to Inject Dependencies

Modify `OrchestratorAgentExecutor` to accept the `TaskStore` and pass it to the `StatefulAgentExecutor` parent class.

*   **File:** `a2a-on-ae-multiagent-memorybank/a2a_agents/orchestrator/orchestrator_executor.py`
*   **Action:** Refactor the `__init__` method and remove the now-redundant `_get_core_executor` method.

    **Before:**
    ```python
    class OrchestratorAgentExecutor(StatefulAgentExecutor):
        def __init__(self, agent_engine_id: str = None) -> None:
            self._orchestrator = AdkOrchestratorAgentExecutor(...)
            super().__init__()

        def _get_core_executor(self) -> AgentExecutor:
            return self._orchestrator
    ```
    
    **After:**
    ```python
    from a2a.server.tasks import TaskStore # Import the base class

    class OrchestratorAgentExecutor(StatefulAgentExecutor):
        def __init__(self, task_store: TaskStore, agent_engine_id: str = None) -> None:
            self._orchestrator = AdkOrchestratorAgentExecutor(...)
            # Pass the core_executor and task_store to the parent
            super().__init__(core_executor=self._orchestrator, task_store=task_store)

        # The _get_core_executor method is no longer needed.
    ```

### Step 3: Create a Centralized, Asynchronous Entrypoint

The final step is to create all the dependencies in a single, asynchronous entry point for the application. This solves the async initialization problem and makes the configuration explicit.

*   **File:** A new entrypoint file, e.g., `main.py` or `server.py`.
*   **Action:** Implement an `async` function to set up and run the application.

    **Conceptual Example (`main.py`):**
    ```python
    import asyncio
    from a2a.server.tasks import DatabaseTaskStore, InMemoryTaskStore
    from shared.database import get_db_engine # From your development plan
    from orchestrator.orchestrator_executor import OrchestratorAgentExecutor

    async def main():
        # 1. Asynchronously initialize the database engine
        db_engine = await get_db_engine()

        # 2. Create and initialize the DatabaseTaskStore
        # For local dev, you could swap this with: task_store = InMemoryTaskStore()
        task_store = DatabaseTaskStore(engine=db_engine)
        await task_store.initialize()

        # 3. Now, create the executor with the fully initialized task_store
        # This is now a simple, synchronous call.
        my_agent_executor = OrchestratorAgentExecutor(task_store=task_store)

        # 4. Start your web server (e.g., FastAPI) and pass it the executor
        # server.run(app, agent=my_agent_executor)

    if __name__ == "__main__":
        asyncio.run(main())
    ```

### Summary of Benefits

This refactoring provides significant advantages for the project:
*   **Simple & Clear:** Constructors are now straightforward and declare their dependencies explicitly.
*   **Testable:** It's easy to unit test components by passing in mock or in-memory versions of their dependencies (like `InMemoryTaskStore`).
*   **Flexible:** Changing the storage backend (e.g., from SQLite to AlloyDB, or from Firestore to Redis) only requires a change in the main entrypoint, not in the agent logic itself.
*   **Handles Async Gracefully:** All asynchronous setup is handled correctly at the start of the application, avoiding complex and error-prone initialization within constructors.
