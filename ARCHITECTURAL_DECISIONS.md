# Backend Architecture Guide

This document explains the backend architecture of the A2A multi-agent system. It is designed as a teaching guide to connect high-level concepts to the specific code that implements them.

## Guiding Principle: Separating Logic from Infrastructure

The architecture's primary goal is to separate the agent's "brain" from its "shell."

-   **Agent Logic (Brain):** This is the agent's reasoning core. It includes the LLM prompts, tool definitions, and the decision-making process for a single turn of a conversation.
-   **Infrastructure (Shell):** This is the surrounding system that handles state persistence, database connections, authentication, and the low-level details of the A2A communication protocol.

This separation makes the system more flexible, easier to test, and simpler to maintain.

---

## 1. Codebase Structure

The code within `a2a-on-ae-multiagent-memorybank/a2a_agents/` is organized by function. Here are the key files and their roles:

-   `orchestrator/`: Contains the central **Orchestrator Agent**.
    -   `orchestrator_executor.py`: The main entry point ("Shell") for the orchestrator. It handles database setup and manages the A2A task lifecycle.

-   `specialized_agents/`: Contains the simple, stateless "worker" agents.
    -   `cocktail_agent/cocktail_agent_executor.py`: The implementation for the Cocktail Agent.
    -   `weather_agent/weather_agent_executor.py`: The implementation for the Weather Agent.

-   `shared/`: Contains the core logic and infrastructure used by all agents.
    -   `adk_orchestrator_agent.py`: The "Brain" of the orchestrator. This file defines the core LLM prompt (`ORCHESTRATOR_INSTRUCTION`) and the ADK agent that uses it.
    -   `a2a_tools.py`: Defines the crucial `delegate_to_specialist_agent` function, which is the tool the orchestrator LLM uses to communicate with other agents.
    -   `remote_connection.py`: A low-level A2A client used by the delegation tool to handle HTTP requests.
    -   `auth_utils.py`: Handles secure service-to-service authentication on Google Cloud.
    -   `session_store.py`: Manages the mapping between A2A `context_id` and ADK `session_id` in the database, ensuring conversational memory.
    -   `dependencies.py`: Manages the creation of the shared AlloyDB database connection.

---

## 2. Core Design Patterns

### Composition over Inheritance

The `OrchestratorAgentExecutor` (the Shell) holds an instance of `AdkOrchestratorAgentExecutor` (the Brain). This allows the Brain's complex reasoning to be unit-tested in isolation, without needing to mock a database connection.

### Distinguishing Between Messages and Artifacts

A key concept in the A2A protocol is the difference between a `Message` and an `Artifact`. The system uses both, but for distinct purposes:

-   **`Message`:** Used for the conversational, turn-by-turn dialogue between agents. When a specialist agent needs more information, it returns a `Message` with a clarifying question, setting the task state to `input_required`.

-   **`Artifact`:** Represents the final, tangible output or "deliverable" of a completed task. It is not part of the conversation but is the result of it.

This project establishes a clear convention: when a specialist agent successfully completes its task, it packages its final answer into an `Artifact` named **`"answer"`**. The orchestrator is specifically designed to look for this artifact to retrieve the result.

This pattern is explicitly implemented in the `shared/a2a_tools.py` file within the `_get_final_text_from_task` helper function, which is responsible for parsing the response from a specialist agent and extracting the content from the `"answer"` artifact.

### Leveraging the Official A2A Python SDK

The project does not implement the A2A communication protocol from scratch. Instead, it relies on the high-level abstractions provided by the official `a2a-python` SDK. This ensures compliance with the A2A standard and simplifies the communication logic.

The primary example of this is in `shared/a2a_tools.py`, which uses the following core components from the SDK:

-   **`ClientFactory`**: This is the main entry point for creating A2A clients. The code creates a `SHARED_CLIENT_FACTORY` to manage connections.
-   **`ClientConfig`**: This data structure is used to configure the behavior of the clients created by the factory.
-   **`client.send_message(...)`**: This is the high-level method used to send a message to a specialist agent, abstracting away the underlying HTTP requests and protocol details.

A key architectural choice is how authentication is handled. Rather than bypassing the SDK, the project injects a custom-configured `httpx.AsyncClient` into the SDK's `ClientConfig`:

```python
# In shared/a2a_tools.py

# 1. A custom httpx client is created with Google-specific auth.
AUTHENTICATED_HTTPX_CLIENT = httpx.AsyncClient(
    auth=GoogleAuth(),
    ...
)

# 2. The custom client is injected into the standard A2A SDK ClientConfig.
SHARED_CLIENT_CONFIG = ClientConfig(
    httpx_client=AUTHENTICATED_HTTPX_CLIENT,
    ...
)

# 3. The config is used to create the SDK's ClientFactory.
SHARED_CLIENT_FACTORY = ClientFactory(config=SHARED_CLIENT_CONFIG)
```

This is the intended and recommended pattern for integrating custom authentication or other advanced HTTP configurations with the `a2a-python` SDK. It allows the project to benefit from the SDK's robust protocol handling while seamlessly layering in necessary custom behavior.

### Modern vs. Legacy SDK Patterns

This project's use of the `a2a-python` SDK represents the modern, recommended **SDK Factory Pattern**, which stands in contrast to older, legacy patterns found in other examples.

-   **Legacy Client Pattern:** This older approach involves directly instantiating a deprecated `A2AClient` and manually constructing protocol-specific request objects (like `SendMessageRequest`). This pattern is more verbose, tightly coupled to a specific transport (JSON-RPC), and relies on code that is marked for future removal from the SDK.

-   **Modern Factory Pattern (This Project):** The approach used in this codebase is centered on the `ClientFactory`. It abstracts away the transport layer, allowing the SDK to negotiate the best communication protocol (JSON-RPC, gRPC, etc.) automatically. The code is cleaner, as it only needs to create a high-level `Message` object rather than the full request boilerplate.

From a software engineering perspective, the modern Factory Pattern is unequivocally superior. It avoids deprecated code, promotes loose coupling, reduces boilerplate, and is significantly more maintainable and robust against future changes in the SDK. This project therefore serves as a better blueprint for building production-ready, future-proof multi-agent systems.

### Dependency Injection and Lazy Initialization

The `shared/dependencies.py` module creates a single, shared connection pool to the AlloyDB database. This connection is initialized "lazily" on the first incoming request via the `OrchestratorAgentExecutor._ensure_setup` method, solving the challenge of `async` database connections in `sync` class constructors.

---

## 3. Architectural Shift: From Executor-Driven to Tool-Driven Orchestration

A primary decision in this project's evolution was the shift from an **Executor-Driven** architecture to a more flexible **Tool-Driven** model. This change fundamentally alters where the orchestration logic resides, moving it from complex Python code into the reasoning capabilities of the orchestrator's LLM.

### The Old Model: Executor-Driven Orchestration
-   **Orchestration Logic:** Lived in Python classes.
-   **Flexibility:** Low. Adding a new agent required modifying the orchestrator's Python code.
-   **Complexity:** High Python complexity (managing protocols, state, and workflow).

### The New Model: Tool-Driven Orchestration
-   **Orchestration Logic:** Lives **entirely within the LLM's prompt**. The prompt instructs a powerful model (e.g., Gemini Pro) on how to form a multi-step plan and execute it by calling a simple tool.
-   **Flexibility:** **High.** Adding a new agent only requires updating a dictionary in `a2a_tools.py` and the orchestrator's prompt.
-   **Complexity:** **Low Python complexity.** The complexity is shifted to the LLM's reasoning.

This shift fully embraces the "Brain vs. Shell" principle. The Python code provides the "hands" (the tool), while the LLM serves as the "brain."

---

## 4. Anatomy of a Multi-Agent Request (Tool-Driven Flow)

This section traces a user query like *"What's the weather in Boston and what's a good drink for that?"* through the system, highlighting the key files and functions involved.

**Step 1: Request Entry**
-   The user query enters the system via the Gradio frontend.
-   **File:** `orchestrator/orchestrator_executor.py`
-   **Function:** The `OrchestratorAgentExecutor.execute()` method is called. It ensures the database is connected and retrieves the conversational session.

**Step 2: Orchestrator Planning**
-   The query is passed to the orchestrator's LLM.
-   **File:** `shared/adk_orchestrator_agent.py`
-   **Logic:** The LLM uses the `ORCHESTRATOR_INSTRUCTION` prompt to form a plan. It reasons: "I need weather first, then a drink suggestion. I must call the Weather Agent, wait for the result, and then call the Cocktail Agent."

**Step 3: First Tool Call (Weather)**
-   The LLM generates a tool call to the `delegate_to_specialist_agent` function.
-   **File:** `shared/a2a_tools.py`
-   **Function:** `delegate_to_specialist_agent(agent_name='Weather Agent', query='What is the weather in Boston?')` is executed.

**Step 4: Secure A2A Delegation**
-   The `delegate_to_specialist_agent` function looks up the Weather Agent's URL.
-   **File:** `shared/auth_utils.py`
-   **Function:** It calls `get_auth_token()` to get a secure OIDC token for the request.
-   **File:** `shared/remote_connection.py`
-   **Function:** The `RemoteAgentConnection.send_message()` method uses the token to send a secure A2A request over HTTP to the Weather Agent.

**Step 5: Specialist Agent Execution**
-   The Weather Agent receives the request.
-   **File:** `specialized_agents/weather_agent/weather_agent_executor.py`
-   **Logic:** It executes its own LLM and tools (the MCP server) to get the weather, and returns a structured JSON response.

**Step 6: Second Tool Call (Cocktail)**
-   The orchestrator's LLM receives the weather data. Following its plan, it generates a second tool call.
-   **File:** `shared/a2a_tools.py`
-   **Function:** `delegate_to_specialist_agent(agent_name='Cocktail Agent', query='What is a good cocktail for a cold day?')` is executed. This follows the same secure delegation process as Step 4.

**Step 7: Final Synthesis**
-   The orchestrator's LLM now has the results from both specialist agents.
-   **File:** `shared/adk_orchestrator_agent.py`
-   **Logic:** Following the `ORCHESTRATOR_INSTRUCTION`, it synthesizes the two pieces of information into a single, user-friendly paragraph.
-   **File:** `orchestrator/orchestrator_executor.py`
-   **Function:** The final text is sent back to the user via the `event_queue.enqueue_event()`.

---

## 5. Three Layers of Persistent State

The agent's state is managed in three distinct layers, primarily using a single AlloyDB database.

### Layer 1: A2A Task Lifecycle
-   **Purpose:** Tracks the status of a single user request (`running`, `completed`, etc.).
-   **Implementation:** The `DatabaseTaskStore` from the `a2a-sdk` automatically manages a `tasks` table in AlloyDB.
-   **File:** `shared/dependencies.py` (where `get_database_task_store()` is defined).

### Layer 2: Conversational Context
-   **Purpose:** Preserves conversation history across multiple turns.
-   **Implementation:** Links the A2A `context_id` to the ADK `session_id`.
-   **File:** `shared/session_store.py` (implements `get_session_mapping` and `set_session_mapping` which read/write to a `session_mappings` table in AlloyDB).

### Layer 3: Long-Term Knowledge
-   **Purpose:** Allows the agent to learn and recall facts across many conversations.
-   **Implementation:** Uses Google ADK's `MemoryBank` feature, configured with `PersistentVertexAiMemoryBankService`.
-   **File:** `shared/adk_orchestrator_agent.py` (where the service is configured and the `PreloadMemoryTool` is attached to the agent).

---

## 6. Architectural Diagram

```mermaid
graph TD
    subgraph User Experience
        A[Frontend Web App<br/>Gradio] --> B(User Query)
    end

    subgraph Google Cloud Project
        subgraph Vertex AI Services
            subgraph Agent Engine
                C{Orchestrator Agent<br/>(Shell & Brain)}
                E[Weather Agent]
                F[Cocktail Agent]
            end
            O[Vertex AI MemoryBank]
        end

        subgraph Cloud Run
            G[Weather MCP Server]
            H[Cocktail MCP Server]
        end

        subgraph Persistence & Secrets
            I[AlloyDB Database<br/>(TaskStore & SessionStore)]
            J[Secret Manager]
        end

        %% Relationships
        B -- "HTTP/S Request" --> C;

        %% Orchestrator to Specialized Agent Flow
        C -- "Delegate Task (A2A)" --> E;
        C -- "Delegate Task (A2A)" --> F;

        %% Specialized Agent to MCP Flow
        E -- "HTTP/S Tool Call" --> G;
        F -- "HTTP/S Tool Call" --> H;

        %% State Management Flow
        C -- "Stores/Retrieves Task & Session State" --> I;
        J -- "Provides DB Credentials" --> C;

        %% Memory Flow
        C -- "R/W Long-Term Memory" --> O;
        E -- "R/W Long-Term Memory" --> O;
        F -- "R/W Long-Term Memory" --> O;
    end

    %% Styling
    style C fill:#f9f,stroke:#333,stroke-width:2px;
    style E fill:#cec,stroke:#333,stroke-width:2px;
    style F fill:#cec,stroke:#333,stroke-width:2px;
    style G fill:#dee,stroke:#333,stroke-width:2px;
    style H fill:#dee,stroke:#333,stroke-width:2px;
    style I fill:#fcc,stroke:#333,stroke-width:2px;
    style J fill:#fcf,stroke:#333,stroke-width:2px;
    style O fill:#ffc,stroke:#333,stroke-width:2px;
```

---

## Appendix: Anatomy of the `deploy_alloydb.sh` Script

The `deploy_alloydb.sh` script is a fully idempotent script responsible for provisioning the entire database backend. It handles API enablement, VPC peering, cluster/instance creation, IP authorization, and secure credential management in Secret Manager.
