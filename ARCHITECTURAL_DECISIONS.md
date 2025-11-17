# Backend Architecture Guide

This document explains the backend architecture of the A2A multi-agent system. It covers the codebase structure, core design patterns, state management, and the agent-to-agent communication protocol.

## Guiding Principle: Separating Logic from Infrastructure

The architecture's primary goal is to separate the agent's "brain" from its "shell."

-   **Agent Logic (Brain):** This is the agent's reasoning core. It includes the LLM prompts, tool definitions, and the decision-making process for a single turn of a conversation.
-   **Infrastructure (Shell):** This is the surrounding system that handles state persistence, database connections, authentication, and the low-level details of the A2A communication protocol.

This separation makes the system more flexible, easier to test, and simpler to maintain.

---

## 1. Codebase Structure

The code within `a2a-on-ae-multiagent-memorybank/a2a_agents/` is organized by function to enforce the separation of concerns.

-   `orchestrator/`: Contains the central **Orchestrator Agent**. This is the user-facing component that manages the overall task.
-   `specialized_agents/`: Contains the simple, stateless "worker" agents (`cocktail_agent`, `weather_agent`). These agents act as tools that the orchestrator can call to perform specific tasks.
-   `shared/`: Contains code used by all agents. This is where the infrastructure, state management, communication clients, and core patterns are implemented.

---

## 2. Core Design Patterns

### Composition over Inheritance

The system strongly prefers Composition (a class *has a* dependency) over Inheritance (a class *is a* dependency).

-   **Implementation:** The `OrchestratorAgentExecutor` (the Shell) holds an instance of `AdkOrchestratorAgentExecutor` (the Brain). The Shell's responsibility is infrastructure: it manages the asynchronous setup of the database and the A2A task lifecycle. The Brain is responsible only for the agent's reasoning during a single turn and has no knowledge of the database.
-   **Benefit:** This pattern allows the Brain's complex reasoning to be unit-tested in isolation, without needing to create or mock a database connection. It also allows the entire infrastructure Shell to be replaced or modified without impacting the core agent logic.

### Inheritance

Inheritance is used pragmatically and only when required to conform to the A2A framework's interface. `OrchestratorAgentExecutor` *is an* `a2a.server.agent_execution.AgentExecutor` because the framework requires this specific class structure to correctly serve the agent.

### Dependency Injection and Lazy Initialization

The system creates dependencies once at startup and injects them where needed.

-   **Implementation:** The `shared/dependencies.py` module is responsible for creating a single, shared connection pool (`AsyncEngine`) to the AlloyDB database. This connection is initialized "lazily" on the first incoming request via the `OrchestratorAgentExecutor._ensure_setup` method. This method then passes, or "injects," the database engine into the other components that require it, such as the session store.
-   **Benefit:** This solves a critical challenge: database connections are `async`, but class constructors (`__init__`) are `sync`. By delaying initialization until the first `async` request, we handle the async lifecycle correctly and ensure a single, efficient connection pool is shared across the application.

---

## 3. Agent Communication & Security

The `shared/` directory contains a set of modules that work together to enable secure communication between the orchestrator and the specialized agents.

### `a2a_tools.py`: The High-Level Interface

-   **Purpose:** This module defines the `delegate_to_specialist_agent` function. This function is exposed as a "tool" to the orchestrator's LLM.
-   **Mechanism:** When the orchestrator's LLM decides to delegate a task, it generates a tool call with the target agent's name and a query. This function receives that call and acts as the entry point for agent-to-agent communication. It uses the `RemoteAgentConnection` to handle the actual network request.

### `remote_connection.py`: The A2A Client

-   **Purpose:** This module provides the `RemoteAgentConnection` class, a low-level client for making A2A protocol calls.
-   **Mechanism:** This class abstracts the details of the A2A protocol. It knows how to fetch an agent's "card" (a manifest of its capabilities), construct a valid A2A message, send the request over HTTP, and poll for the final result of the task. It uses `auth_utils.py` to get the necessary authentication tokens for its requests.

### `auth_utils.py`: Secure Authentication

-   **Purpose:** This module handles the authentication required for one Google Cloud service (the orchestrator's Cloud Run instance) to securely call another (the specialized agent's Cloud Run instance).
-   **Mechanism:** It contains the `get_auth_token` function, which programmatically requests a Google-signed OIDC identity token for the specialized agent's URL. This token is then attached as a `Bearer` token in the `Authorization` header of the HTTP request made by the `RemoteAgentConnection`. This is a standard and secure way to handle service-to-service authentication on Google Cloud.

### `custom_context_builder.py`: Passing User Identity

-   **Purpose:** The A2A protocol does not have a built-in field for the end-user's identity. This module provides a mechanism to pass the `user_id` from the orchestrator to the specialized agents.
-   **Mechanism:** It uses Python's `contextvars` to create a request-scoped context. The `AdkOrchestratorAgentExecutor` sets the `user_id` in this context at the beginning of a request. The `delegate_to_specialist_agent` tool then reads the `user_id` from this context and includes it in the A2A message's metadata field, ensuring the specialized agents know which user the request belongs to.

---

## 4. Three Layers of Persistent State

The agent's state is managed in three distinct layers, all persisting to a single AlloyDB database to ensure data integrity and resilience to server restarts.

### Layer 1: A2A Task Lifecycle (`DatabaseTaskStore`)

This layer tracks the status of a single user request according to the A2A protocol. The `DatabaseTaskStore` from the `a2a-sdk` automatically creates and manages a `tasks` table in AlloyDB. The orchestrator updates the task's status (`running`, `completed`, `failed`) throughout its execution. This allows a user to query the status of any job, especially long-running ones.

### Layer 2: Conversational Context (`SessionStore`)

This layer preserves the history of a conversation across multiple turns, preventing agent amnesia. The A2A protocol uses a `context_id` to track a conversation, while the underlying Google ADK framework uses a `session_id`. Our custom `session_store.py` module creates a `session_mappings` table to link these two IDs. When a request arrives, the agent looks up the `context_id` to find the corresponding ADK `session_id`, which allows it to retrieve the full conversation history.

### Layer 3: Long-Term Knowledge (`MemoryBank`)

This layer allows the agent to learn and recall facts across many conversations. We use the Google ADK's `MemoryBank` feature, configured with the `PersistentVertexAiMemoryBankService` to ensure memories are stored durably. The `PreloadMemoryTool` automatically retrieves relevant memories and injects them into the agent's context at the start of each turn, providing it with long-term knowledge.
