# A2A ADK Training Guide

This guide provides a developer-focused walkthrough of the A2A Multi-Agent Sample Application. It's designed for those with a foundational understanding of agent concepts and the ADK, aiming to bridge the gap between high-level A2A knowledge and practical implementation.

We will explore the codebase to understand its structure, core components, and how different parts interact to form a cohesive multi-agent system.

## Core Concepts: The `common` Directory

The `common` directory is the heart of this project's architecture. It contains the foundational code that enables the multi-agent system to function, handling orchestration, agent communication, and core A2A protocol implementation. Understanding these components is key to understanding the entire system.

The architecture follows a common **Orchestrator-Specialist pattern**:

1.  **Orchestrator Agent (`hosting_agent`)**: A primary agent that receives user requests. It doesn't perform the tasks itself but instead analyzes the request and delegates it to the appropriate specialist agent.
2.  **Specialist Agents (`weather_agent`, `cocktail_agent`)**: These agents are experts in a specific domain. They expose a set of capabilities (tools) and are responsible for executing the tasks delegated by the orchestrator.

Let's break down the key files in the `common` directory.

### `adk_orchestrator_agent.py` & `adk_orchestrator_agent_executor.py`

These files define the **Orchestrator**.

*   `AdkOrchestratorAgent`: This is the "brain" of the orchestrator.
    *   **Discovery**: On startup, it discovers the specialist agents by fetching their `AgentCard` over the network. An `AgentCard` is a public document that describes an agent's capabilities, name, and how to communicate with it.
    *   **Delegation**: Its core logic is defined in the `root_instruction` prompt, which instructs the underlying LLM (Gemini) to act as an expert delegator.
    *   **Tools**: It uses two primary tools to interact with specialist agents:
        *   `list_remote_agents`: To see which specialists are available.
        *   `send_message`: To delegate a task to a specific agent.

*   `AdkOrchestratorAgentExecutor`: This class is the bridge between the A2A protocol and the ADK-based orchestrator agent. It handles the server-side logic for receiving requests, managing the task lifecycle (e.g., `submitted`, `working`, `completed`), and maintaining conversation state.

### `adk_base_mcp_agent_executor.py`

This is the abstract base class for all **Specialist Agents** (Weather, Cocktail). It provides the common functionality needed to connect any ADK agent to an external tool or service via the **Multi-Controller Protocol (MCP)**.

Key responsibilities include:

*   **A2A to ADK Bridge**: Translates incoming A2A protocol messages into a format the ADK agent can understand and vice-versa.
*   **MCP Tool Integration**: It configures the `McpToolset`, which allows the ADK agent to call external tools. The URL for these tools (the MCP servers) is specified in each agent's configuration.
*   **Session Management**: It maintains a map of conversation IDs to ADK sessions (`CONTEXT_ID_TO_SESSION_MAP`). This ensures that multi-turn conversations are handled correctly. The code includes a note that for a production system, a distributed cache like Redis would be preferable to a simple in-memory dictionary.
*   **Authentication**: It uses a `TokenManager` to securely communicate with the MCP servers by automatically fetching and refreshing OIDC tokens.
*   **Persistent Memory**: It uses a custom `PersistentVertexAiMemoryBankService` to save conversation history. This is a great example of real-world engineering, as it fixes a potential issue with the standard library's implementation where HTTP clients could be prematurely closed.

Each specialist agent will subclass `AdkBaseMcpAgentExecutor` and implement the `get_agent_config` method to provide its specific details (name, description, prompt, and MCP server URL).

### Utility Modules

*   **`agent_configs.py`**: A centralized file to store the configuration for each specialist agent. This is a good practice that keeps configuration separate from logic.
*   **`auth_utils.py`**: Provides a reusable `GoogleAuth` class for `httpx`, simplifying authentication with Google Cloud services using Application Default Credentials (ADC).
*   **`remote_connection.py`**: Contains the `RemoteAgentConnections` class, which handles the low-level details of sending messages to a remote A2A agent. The orchestrator uses this to communicate with the specialists.

## Implementing Specialist Agents: A Comparative Look

The power of the architecture lies in how easily new specialist agents can be created. Both the `WeatherAgent` and `CocktailAgent` follow the same simple pattern of inheriting from the base classes and providing domain-specific configuration.

**The Pattern:**

1.  **Define the Public Card (`*_agent_card.py`)**: Create an `AgentCard` that describes the agent's skills, providing examples and a clear description. This card is how the orchestrator discovers the agent and learns what it can do.
2.  **Implement the Executor (`*_agent_executor.py`)**:
    *   Create a class that inherits from `AdkBaseMcpAgentExecutor`.
    *   Implement the `get_agent_config()` method to return a configuration dictionary from `agent_configs.py`. This injects the agent's name, description, prompt, and the crucial URL for its backend tool (MCP server).
    *   (Optional but recommended) Implement `get_agent_engine()` to define custom memory topics for Vertex AI Memory Bank. This allows the agent to develop a more nuanced, domain-specific memory.

**Comparison:**

| Feature | `WeatherAgentExecutor` | `CocktailAgentExecutor` |
| :--- | :--- | :--- |
| **Inherits From** | `AdkBaseMcpAgentExecutor` | `AdkBaseMcpAgentExecutor` |
| **Configuration** | Returns `WEATHER_AGENT_CONFIG` | Returns `COCKTAIL_AGENT_CONFIG` |
| **MCP Server URL** | `WEA_MCP_SERVER_URL` | `CT_MCP_SERVER_URL` |
| **Custom Memory** | Topics like `location`, `weather_forecast` | Topics like `cocktail_id`, `cocktail_recipe` |

This design is highly extensible. To add a new "Movie Agent," you would simply:
1.  Create `movie_agent_card.py`.
2.  Add a `MOVIE_AGENT_CONFIG` to `agent_configs.py`.
3.  Create `movie_agent_executor.py` that inherits the base class and provides the new config.
4.  Deploy the new agent and its corresponding MCP server.

The orchestrator would automatically discover and be able to use it with no changes to its own code.

## End-to-End Request Flow: From UI to Specialist

Understanding the flow of a single user request clarifies how all the components work together. Let's trace a request for a cocktail recipe.

1.  **User Interaction (Frontend)**: The user types "What are the ingredients for a Margarita?" into the Gradio web UI. The `frontend/main.py` application is managing this session.

2.  **Client-Side A2A Call**:
    *   The frontend has already discovered the `HostingAgent` (the orchestrator) by fetching its `AgentCard`.
    *   It creates an A2A client and sends the user's query in an A2A message to the `HostingAgent`. This is a secure, authenticated API call over HTTP.

3.  **Orchestrator Receives Request (`HostingAgent`)**:
    *   The `HostingAgentExecutor` receives the A2A message.
    *   It passes the query to its underlying ADK agent (`AdkOrchestratorAgent`).
    *   The agent's LLM, guided by its prompt ("You are an expert delegator..."), analyzes the query. It consults its available tools, which are `list_remote_agents` and `send_message`.

4.  **Delegation Decision**:
    *   The orchestrator sees that the query is about cocktails. By looking at the `AgentCard`s it discovered at startup, it knows the `CocktailAgent` has a skill for `"cocktail_cocktail"`.
    *   It decides to delegate the task.

5.  **Orchestrator-to-Specialist A2A Call**:
    *   The `HostingAgent` uses its `send_message` tool, which under the hood makes another A2A client call.
    *   This time, the call is directed to the `CocktailAgent`, forwarding the user's query.

6.  **Specialist Agent Execution (`CocktailAgent`)**:
    *   The `CocktailAgentExecutor` receives the request.
    *   It passes the query to its ADK agent. The agent's prompt ("You are a specialized cocktail expert...") instructs it to use its tools to answer.
    *   The agent activates its `McpToolset`, which makes a final API call to the `cocktail_mcp_server` (the actual backend tool that has the recipe data).

7.  **Response Journey**:
    *   The `cocktail_mcp_server` returns the recipe data.
    *   The `CocktailAgent` formats this data into a user-friendly response and sends it back to the `HostingAgent` as the result of the A2A call.
    *   The `HostingAgent` receives the specialist's response. It may do some final formatting, but in this case, it simply forwards the answer back to the original caller.
    *   The response is sent back to the `frontend/main.py` application.

8.  **Streaming to UI**: The frontend receives the final answer (or intermediate chunks) and streams it to the Gradio chatbot interface, where the user sees the recipe appear.

This entire process, involving multiple services and LLM calls, happens seamlessly in a few seconds, providing a powerful and scalable way to build complex, multi-capability agent systems.

