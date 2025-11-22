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

### A. The Sync/Async Bridge (Lazy Initialization Pattern)
**Context:** The `A2aAgent` framework requires a **synchronous** `task_store_builder` function during initialization. However, cloud-native dependencies (Secret Manager, AlloyDB connections) typically require **asynchronous** initialization.

**The Solution:**
We implemented a **Synchronous Builder with Blocking Init** in `shared/database/connection.py`.
*   We initially tried a complex `GlobalTaskStoreProxy` for lazy async loading.
*   **Simplification:** We refactored to a simpler synchronous builder that blocks the thread briefly to fetch secrets.
*   **Outcome:** This reduced code complexity significantly while satisfying the framework's contract with negligible impact on cold-start performance (~200ms).

### B. Database Normalization & Composite Keys
**Context:** Mapping a User ID and a Context ID to a Vertex AI Session ID is crucial for state recovery. A naive approach often involves concatenating strings (e.g., `user-context`).

**The Solution:**
In `shared/database/sessions.py`, we utilized a **Composite Primary Key**:
```python
session_mappings_table = sqlalchemy.Table(
    "session_mappings",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.String(255), primary_key=True),
    sqlalchemy.Column("context_id", sqlalchemy.String(255), primary_key=True),
    # ...
)
```
**Why it matters:** This ensures data integrity and allows for efficient querying by `user_id` alone (e.g., "find all sessions for this user") without complex string parsing.

### C. Deterministic Tool Routing
**Context:** LLMs can be unpredictable. We needed the Orchestrator to act as a reliable router, not just a chatbot.

**The Solution:**
We engineered the `ORCHESTRATOR_INSTRUCTION` in `orchestrator/logic.py` to enforce a strict protocol:
1.  **Capability Check:** Reject impossible requests immediately.
2.  **Sequential Execution:** Force the model to call one tool, wait for the result, and *then* call the next.
3.  **Synthesis:** Only generate the final natural language response after all data is collected.

---

## 3. Performance Optimization

### Model Selection: Pro vs. Flash
*   **Initial State:** The Orchestrator used `gemini-2.5-pro`.
*   **Optimization:** We switched to `gemini-2.5-flash` for the `OrchestratorLogic`.
*   **Rationale:** The Orchestrator's primary job is **routing** and **synthesis**, which requires high speed and low latency but not the deep reasoning capabilities of the "Pro" model.
*   **Result:** Significant reduction in "Time to First Byte" (TTFB) and overall request latency, making the agent feel much snappier.

---

## 4. Lessons Learned & Framework Specifics

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

## 5. Future Improvements / To-Do

*   **Linting Pipeline:** Integrate `flake8` or `ruff` into `deploy_agents.sh` to catch `NameError` (like the missing `logger`) before deployment starts.
*   **Parallel Execution:** Update the Orchestrator prompt to allow parallel tool calling (e.g., fetch weather AND cocktail recipes simultaneously) to further reduce latency.
