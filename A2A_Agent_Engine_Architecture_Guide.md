# A2A on Agent Engine: Architecture & Best Practices Guide

This document outlines the architectural decisions, design patterns, and key lessons learned during the development of the Multi-Agent System using the **Agent-to-Agent (A2A)** protocol on Google Cloud's **Vertex AI Agent Engine**.

It serves as a reference for the engineering team to understand the "Why" behind the "How".

---

## 1. High-Level Architecture: Hub-and-Spoke

We implemented a **Stateful Orchestrator, Stateless Worker** pattern.

*   **Orchestrator Agent (The Hub):**
    *   **Role:** The central "brain" that manages conversation state, user sessions, and task delegation.
    *   **State:** Highly stateful. Persists full conversation history and task metadata to **AlloyDB** to support long-running, multi-turn interactions.
    *   **Logic:** Uses a strict "Reasoning Loop" to break down user queries into discrete steps.

*   **Specialized Agents (The Spokes):**
    *   **Role:** Domain experts (Cocktail Agent, Weather Agent) that perform specific functions.
    *   **State:** **Stateless**. They receive a query, process it (e.g., call an external API), and return a structured JSON response. They use an ephemeral `InMemoryTaskStore` because they don't need to remember history across different orchestrator requests.
    *   **Benefit:** This decoupling allows the workers to crash, restart, or scale independently without affecting the user's conversation context.

---

## 2. Key Technical Highlights

### A. The Sync/Async Bridge (Synchronous Builder Pattern)
**Context:** The `A2aAgent` framework requires a **synchronous** `task_store_builder` function during initialization. However, cloud-native dependencies (Secret Manager, AlloyDB connections) typically involve asynchronous calls.

**The Solution:**
We implemented a **Synchronous Builder with Blocking Initialization** in `shared/database/connection.py`.

*   **Mechanism:** The `build_database_task_store()` function is defined synchronously. Inside, it uses the synchronous `SecretManagerServiceClient` to fetch credentials, blocking the thread briefly only during the application's cold start.
*   **Integration:** It immediately constructs the `AsyncEngine` (which is a non-blocking operation) and returns the configured `DatabaseTaskStore`.
*   **Why it matters:** This approach drastically reduces code complexity compared to lazy-loading proxies. It satisfies the framework's strict synchronous contract while ensuring the runtime database operations remain fully asynchronous and non-blocking. The startup latency impact (~200ms) is negligible for the reliability gained.

### B. Session ID Translation Layer (Composite Keys)
**Context:** There is a fundamental mismatch between the **Agent-to-Agent (A2A) Protocol** and **Vertex AI Agent Engine**:
*   **A2A** uses a client-provided `context_id` (typically a UUID) to track a conversation.
*   **Vertex AI Agent Engine** generates its own long, opaque resource names for sessions (e.g., `projects/123/.../sessions/abc-789`).

**The Problem:** We cannot simply force the A2A `context_id` to be the Vertex `session_id`. When a user sends a follow-up message with the same A2A `context_id`, the Agent Engine has no native way to know which of its internal Session Resources to load. We need a bridge.

**The Solution:**
We created a dedicated **Translation Layer** in `shared/database/sessions.py` using a **Composite Primary Key**:

```python
session_mappings_table = sqlalchemy.Table(
    "session_mappings_v2",
    metadata,
    # The "Foreign" world (A2A context + User)
    sqlalchemy.Column("user_id", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("context_id", sqlalchemy.String(255), primary_key=True),
    # The "Native" world (Vertex AI Resource Name)
    sqlalchemy.Column("vertex_session_name", sqlalchemy.String(255), nullable=False),
)
```

**Why it matters:**
1.  **State Recovery:** This allows us to look up the correct Vertex Session Resource (`vertex_session_name`) instantly using the incoming A2A `context_id` and `user_id`. Without this, every message would start a blank conversation.
2.  **Composite Integrity:** Using `(user_id, context_id)` as the primary key prevents collisions and allows for efficient queries like "Retrieve all active sessions for User X".

### C. Structured JSON Routing (The "Reasoning Loop")
**Context:** LLMs can be unpredictable when asked to "think then act" in unstructured text. Parsing their intent from free-form paragraphs is error-prone.

**The Solution:**
We refactored the Orchestrator in `orchestrator/executor.py` to enforce a **Strict JSON Output Format**. The LLM must respond with one of two JSON schemas:

1.  **Tool Call:** `{"tool_name": "...", "tool_query": {...}}`
2.  **Final Answer:** `{"final_answer": "..."}`

**Mechanism:**
*   The `OrchestratorAgentExecutor` runs a `while` loop.
*   It parses the LLM's JSON response.
*   If it sees a `tool_name`, it executes the Python function (e.g., `delegate_to_specialist_agent`), appends the result to the chat history, and re-prompts the LLM.
*   This continues until the LLM outputs a `final_answer`.

**Why it matters:** This turns the Orchestrator into a deterministic state machine. We no longer guess if the agent "meant" to call a tool; the JSON structure makes the intent explicit and machine-readable.

### D. Shared Utilities & A2A Interoperability
**Context:** Robust multi-agent systems require common mechanisms for inter-agent communication, context propagation, and secure authentication that are decoupled from individual agent logic.

**The Solution:**
We centralized these critical components in the `shared/` directory:

*   **`shared/tools.py` (Inter-Agent Communication & Context Propagation):**
    *   **`delegate_to_specialist_agent`:** This is the primary tool used by the Orchestrator to call specialized agents. It encapsulates the complexities of A2A client communication (e.g., handling non-streaming interactions, task polling).
    *   **`user_id_context` & `trace_id_context`:** These `contextvars` (context variables) are crucial for propagating user identity and distributed trace IDs across asynchronous calls and agent boundaries. This enables user-specific memory retrieval and end-to-end observability in logs.

*   **`shared/auth_utils.py` (A2A Client Authentication):**
    *   Provides the `GoogleAuth` class, which integrates with Google Cloud's authentication mechanisms. This ensures that when the Orchestrator (or any agent acting as a client) calls another agent, the communication is securely authenticated using appropriate service account credentials.

*   **`shared/base_executor.py` (The Generic Validating Executor):**
    *   We implemented a **Generic Base Class** that handles the boilerplate of initialization, token management, and execution.
    *   Crucially, it accepts an optional `output_schema` (Pydantic model). If provided, it automatically attempts to parse and validate the agent's output, retrying if the format is incorrect. This allowed us to delete ~40 lines of duplicate code from each specialized agent.

**Why it matters:**
This centralization promotes code reuse, reduces boilerplate, and ensures consistent implementation of fundamental cross-cutting concerns (like authentication, logging context, and inter-agent calls) across the entire multi-agent system. It makes the system more maintainable, scalable, and observable.

### E. ADK-Native Context Management
**Context:** Managing long conversations with Large Language Models (LLMs) can be expensive and slow due to increasing context window size.

**The Solution:**
We leveraged native ADK (Agent Development Kit) features by wrapping the `LlmAgent` in an `App` construct in `orchestrator/executor.py`.

*   **Context Caching (`ContextCacheConfig`):** We moved the massive `ORCHESTRATOR_INSTRUCTION` to `static_instruction`. This allows the Gemini model to cache the system prompt, significantly reducing latency and cost for all subsequent turns in a conversation.
*   **Event Compaction (`EventsCompactionConfig`):** We enabled a sliding-window summarizer. Every 5 turns, the ADK automatically compresses older conversation history into a concise summary while keeping recent messages raw. This prevents the context window from overflowing during long sessions.

**Why it matters:** This transforms the agent from a simple chatbot into a production-ready system capable of handling infinite-length conversations efficiently and cost-effectively.

---

## 5. Lessons Learned & Framework Specifics

### The `task_store_builder` Constraint
*   **Issue:** By default, `A2aAgent` uses `InMemoryTaskStore`. If you deploy without explicitly passing a `task_store_builder`, your data disappears on every container restart.
*   **Fix:** You *must* pass a callable builder to the `A2aAgent` constructor in `deploy.py`. This builder must return a configured `TaskStore` instance.

### Refactoring Pitfalls
*   **Method Signatures:** When moving logic from standalone functions to class methods, it is easy to forget adding `self` as the first argument. This leads to `TypeError: ... takes 0 positional arguments but 1 was given`. Always review method signatures during refactoring.
*   **Imports:** Renaming classes requires a meticulous search-and-replace across the entire codebase. A missed import in `deploy.py` can crash the deployment process even if the logic is sound.

### Telemetry Imports (`_default_instrumentor_builder`)
*   **Issue:** Configuring custom telemetry or logging within the ADK often requires internal utilities that aren't always exposed in the top-level API.
*   **Observation:** We had to import `_default_instrumentor_builder` from `vertexai.preview.reasoning_engines.templates.adk`.
*   **Lesson:** When working with Preview features (like Agent Engine), be prepared to look one level deeper into the SDK modules for configuration hooks.

### Dependency Injection
*   **Practice:** We centralized all shared resources (Database connections, Auth headers, Session Logic) in the `shared/` directory.
*   **Benefit:** The Orchestrator imports these as modules. This prevents circular dependencies and ensures that if we change the database provider (e.g., from AlloyDB to Cloud SQL), we only change code in *one place* (`shared/database/connection.py`).

---

## 6. Future Improvements / To-Do

*   **Linting Pipeline:** Integrate `flake8` or `ruff` into `deploy_agents.sh` to catch `NameError` (like the missing `logger`) before deployment starts.
*   **Parallel Execution:** Update the Orchestrator prompt to allow parallel tool calling (e.g., fetch weather AND cocktail recipes simultaneously) to further reduce latency.
