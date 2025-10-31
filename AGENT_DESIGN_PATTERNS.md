# Agent-Based System Design Patterns

> **Author's Note: A Guide for Future Innovation**
>
> This document is part of a larger initiative to build a library of software engineering best practices and design patterns. The goal is to capture the most insightful and reusable architectural decisions from various projects and distill them into a series of guides.
>
> These guides are intended to be used in educational settings, such as hackathons and workshops, to help engineers quickly understand and apply powerful architectural concepts.
>
> The process for creating this document involves an interactive session with an AI assistant (like Gemini) to:
> 1. Explore and understand a specific codebase.
> 2. Identify and discuss the key design patterns and decisions.
> 3. Generalize and abstract these patterns into a use-case-agnostic format.
>
> This document is a living artifact. It is expected to be refined and combined with insights from other projects to create a comprehensive guide to modern software architecture.

---

This document outlines key design patterns for building robust, modular, and scalable multi-agent systems. These principles are derived from a system using the Google Agent Development Kit (ADK) for agent structure and the Agent-to-Agent (A2A) protocol for communication.

## Core Principles

### 1. Decompose Logic into Specialized Agents

Instead of building a single, monolithic agent, decompose your system's logic into smaller, specialized agents, each with a single responsibility. Think of each agent as a microservice.

- **Benefit:** This promotes a clean separation of concerns, making each agent simpler to develop, test, and maintain.
- **Example:** In a workflow that requires generating a proposal and then validating it, create two distinct agents:
    - A `StrategyAgent` responsible only for analyzing data and generating a proposal.
    - A `ValidationAgent` responsible only for checking the proposal against a set of rules.

**Common Strategy: The Retriever/Formatter Workflow**

A powerful application of this pattern for data-intensive tasks is to create a `SequentialAgent` composed of two specialists:

1.  **The `RetrieverAgent`:** Its sole responsibility is to interact with tools to fetch all necessary raw data from various sources. It does no analysis or formatting; its only job is to gather information.
2.  **The `FormatterAgent`:** This agent receives the raw data from the Retriever. Its instructions are focused exclusively on analyzing, processing, and structuring that data into a final, schema-validated output.

This two-step approach cleanly separates the concern of **data gathering** from **data presentation**, which makes the overall workflow more robust, easier to debug, and more maintainable.

### 2. Standardize Communication with a Protocol (A2A)

Avoid creating custom, brittle API clients for each agent to talk to another. Instead, use a standardized communication protocol like A2A.

- **Benefit:** This decouples your agents. As long as they all speak the same protocol, you can swap out, update, or add new agents without breaking the existing ones.
- **How it Works:**
    - **Discovery:** Agents can discover each other's capabilities and endpoints by fetching a public **Agent Card** (`agent.json` file).
    - **Standard Messages:** Agents communicate using a standard message format, removing the need for custom request/response bodies for every interaction.

### 3. Define Strict, Explicit Data Contracts

The data exchanged between agents should be strictly defined and validated. Use a library like Pydantic to define data models for all payloads and results.

- **Benefit:** This acts as a form of documentation and prevents a whole class of runtime errors. If one agent sends data in the wrong format, the receiving agent will immediately reject it with a clear error, making debugging much easier.
- **Example:**
    ```python
    # In a shared `models.py` file
    class Proposal(BaseModel):
        action: str
        value: float

    class ValidationResult(BaseModel):
        is_approved: bool
        reason: str
    ```

### 4. Build "LLM-Ready" Components, Even for Deterministic Logic

An "agent" does not have to be powered by an LLM. You can use a framework like the ADK to structure purely programmatic, rule-based agents. The benefit is that the framework provides structure, state management, and a tool ecosystem out of the box.

- **Benefit:** This makes your components future-proof and versatile.
- **The "LLM-Ready" Pattern:** When creating a tool for an ADK agent, always implement the `_get_declaration()` method to define its schema.
    - **If called by a programmatic agent:** The agent calls the tool's `run_async` method directly.
    - **If called by an LLM-powered agent:** The LLM can use the function declaration to understand how to call the tool.
    - The tool's core logic remains the same in both cases. This separates the tool's *implementation* from its *invocation*.

### 5. Gateways and Tools as Protocol Bridges

Isolate all communication logic to create a clean separation between an application's core logic and the protocols used for communication.

- **For Agent-to-Agent Communication, Use Tools:** Encapsulate the complexity of inter-agent communication within a dedicated `Tool`. The agent's core logic should not be cluttered with HTTP clients or protocol details. The agent simply "uses a tool" to get what it needs.

- **For External-to-Agent Communication, Use an API Gateway:** When an external application (like a web frontend) needs to trigger an agent workflow, it should not communicate with the agent server directly. Instead, create a dedicated **API Gateway** layer (e.g., using Next.js API Routes, FastAPI, or Express). This gateway serves two critical functions:
    1.  **It exposes a simple, task-oriented API to the client.** The client makes a simple, clean HTTP request (e.g., `POST /api/get-analysis`).
    2.  **It translates that simple request into the complex agent protocol.** The gateway, running on the server-side, handles the entire lifecycle of agent interaction: creating a user session, constructing the detailed prompt, running the agent, and parsing the verbose, multi-step response to return a single, clean JSON object to the client.

- **Benefit:** This architecture completely decouples the client application from the agentic backend. The client doesn't need to know about agent session management, prompt engineering, or response parsing. This allows the agent system to evolve independently without breaking the client application. It also enhances security by keeping all agent communication logic on the server.

### 6. Employ an Orchestrator for Complex Workflows

For processes that involve multiple steps and agent interactions, use a dedicated orchestrator service. This service drives the workflow but delegates the actual "thinking" to the specialized agents.

- **Benefit:** Centralizes the control flow, making the overall process easier to understand and manage.
- **Example:** An `Orchestrator` service runs the main loop. In each iteration, it:
    1. Gathers data from the environment.
    2. Calls the `StrategyAgent` to get a proposal.
    3. Receives the proposal and, if one exists, calls the `ValidationAgent`.
    4. Receives the validation result and executes the final action.

## Example Generic Workflow

1.  The **Orchestrator** starts its process loop.
2.  It gathers the current state of the world and prepares a payload.
3.  It uses an A2A client to send a "get decision" task to **Agent A (Strategy)**.
4.  **Agent A** (an ADK agent) is invoked. It analyzes the data and decides to propose an action.
5.  Before returning, **Agent A** needs to validate the action. It calls its internal **Tool B** (an ADK `BaseTool` that is an A2A bridge).
6.  **Tool B** handles the A2A communication: it discovers **Agent B (Validation)**, creates a message with the proposed action, and sends the request.
7.  **Agent B** (another ADK agent) is invoked. It runs its internal rules and and returns an A2A message with an "approved" or "rejected" status.
8.  **Tool B** receives the response, parses it, and returns the clean result to **Agent A**.
9.  **Agent A** now knows the action was approved and returns its final decision in an A2A message to the **Orchestrator**.
10. The **Orchestrator** receives the final, validated decision and executes it.

### 7. The Coordinator-Specialist Pattern

For complex tasks, structure your agents into a hierarchy with a "coordinator" agent and one or more "specialist" agents.

- **How it Works:** The coordinator agent's primary role is to understand the user's intent and delegate the task to the appropriate specialist. The specialist agents are focused on executing a single, well-defined part of the task.
- **Benefit:** This creates a highly scalable and maintainable architecture. You can easily add new specialist agents to handle new tasks without modifying the coordinator. It also makes the system more robust by ensuring that each agent has a narrow and clearly defined responsibility.
- **Example:** This project's `root_agent` acts as a coordinator. It determines if the user wants to update the blog post or critique it, and then routes the request to either the `updater_agent` or the `critic_agent`.

### 8. The Static vs. Turn Instructions Prompting Pattern

Structure your prompts by separating the stable, long-term instructions from the variable, per-request instructions. This improves performance, reduces cost, and increases the predictability of your agents.

- **Static Instructions:** This is the part of the prompt that defines the agent's core persona, role, and capabilities. It is long-lived and does not change between requests. By keeping the static instructions consistent, you can leverage the LLM's context caching, which significantly reduces latency and token count.
    - **Example:** The `PROMPT` constants in the `updater_agent.py` and `critic_agent.py` files are perfect examples of static instructions. They define the role and objective of the agent.

- **Turn Instructions:** This is the part of the prompt that is generated for each specific user request. It contains the immediate context for the task at hand, such as the user's feedback or the specific data to be processed.
    - **Example:** In `agent_gateway.py`, the prompt is dynamically constructed with the user's feedback and the current blog post: `f'Apply this feedback: "{feedback}" to this blog post: "{blog_post_markdown}"'`. This is the turn instruction.

- **Benefit: Cache, Speed, and Cost Savings:** This pattern is crucial for building efficient and cost-effective agentic systems. By caching the large, static part of the prompt, the LLM only needs to process the small, dynamic "turn instruction" for each new request. This dramatically reduces the number of tokens processed per turn, leading directly to:
    - **Lower Latency (Speed):** Faster response times because the model has less to read.
    - **Reduced Costs:** Significant cost savings, as you are not paying to re-process the same static instructions over and over again.
    - **Improved Predictability:** More consistent and predictable behavior from the agent.

### 9. Efficient Context and File Management with ADK Artifacts

ADK Artifacts provide a robust mechanism for managing data that is either too large to fit in the context window or needs to be persisted across turns. They are ideal for handling file uploads and downloads.

- **Managing Context with Artifacts:** When a user uploads a large file (e.g., a video), sending it to the LLM in every turn is inefficient and costly. Artifacts solve this by storing the file once and allowing the agent to selectively load it into the context when needed.
    - **`SaveFilesAsArtifactsPlugin`:** This plugin automatically saves uploaded files as artifacts.
    - **`load_artifacts` Tool:** This tool allows the agent to dynamically load artifacts into the context based on the user's query. This means the large file is only processed when it is relevant to the current turn.
    - **Benefit:** This dramatically reduces latency and cost by avoiding the need to send large files to the model repeatedly.

- **Generating File Downloads with Artifacts:** Agents can also generate files (e.g., PDFs, CSVs) and make them available for download.
    - **`create_download_file` Tool:** This tool takes the generated content, converts it to bytes, and saves it as an artifact using `tool_context.save_artifact`.
    - **ADK Web Interface:** The ADK web interface automatically detects when a download artifact has been created and provides a download link to the user.
    - **Best Practices:**
        - Always use `types.Part` to structure the artifact data.
        - Ensure the file content is converted to `bytes`.
        - Specify the correct `mime_type` for the file.
        - Use `async/await` when calling `save_artifact`.

### 10. State and Event Management with `DatabaseSessionService`

The `DatabaseSessionService` is a core component of the ADK that manages the entire lifecycle of a conversation. It is responsible for creating, retrieving, and persisting the session state, which is composed of a series of events.

- **Events as the Source of Truth:** Events are the fundamental units of information in an ADK session. They represent every significant occurrence, such as user messages, agent responses, tool calls, and state changes. The complete history of events provides a reproducible and auditable record of the conversation.

- **Event Injection Patterns:**
    - **Direct Injection with `append_event()`:** For system notifications and background process updates.
    - **State Management with `state_delta`:** To store metadata and user context.
    - **Chat Service Integration:** For user-facing notifications.

- **Event Extraction Patterns:**
    - **Direct Session Access:** To retrieve the complete conversation history.
    - **Intelligent Text Extraction:** To extract specific information from agent responses.
    - **Specialized Extraction:** To create tools for specific event types (e.g., payment or error events).

- **Real-World Implementation Examples:**
    - **Session Migration:** To transfer session data for anonymous users.
    - **Real-time Event Processing:** To process events as they occur for immediate feedback or action.

- **Best Practices and Performance:**
    - **Session Validation:** Always validate sessions to ensure integrity.
    - **Error Handling:** Implement robust error handling for all session operations.
    - **Unique Invocation IDs:** Use unique IDs for each invocation to prevent race conditions.
    - **Event Ordering:** Maintain proper event ordering to ensure a consistent state.
    - **Batch Operations:** Use batch operations for event processing to improve performance.
    - **Filtering and Pagination:** Use filtering and pagination to manage memory and reduce latency with large session histories.

### 11. The Hybrid AI System

Not all tasks require the complexity of a multi-agent system. For straightforward, single-turn tasks, using a generative AI model directly can be more efficient.

- **How it Works:** Use a standard generative AI SDK for tasks like generating an image from a prompt or summarizing a document. Reserve the agent-based system for more complex, multi-turn, or stateful interactions.
- **Benefit:** This approach allows you to use the right tool for the job. It avoids the overhead of the agent framework for simple tasks, while still providing the structure and power of agents for more complex workflows.
- **Example:** In this project, `app.py` uses the `google-generativeai` library directly to generate the initial blog post and the header image. The more complex task of refining the blog post is then handed off to the agent system.

### 12. Centralized Prompt Engineering

For maintainability and consistency, centralize all your prompts in a dedicated file or module.

- **How it Works:** Instead of embedding prompt strings directly in your agent code, store them in a file like `prompts.py`. Your agent code can then import the prompts from this central location.
- **Benefit:** This makes it much easier to manage and update your prompts. It also ensures that all your agents are working from the same set of instructions, which improves consistency and predictability.
- **Example:** This project uses a `prompts.py` file to store the prompts for the initial blog post generation and the image generation.

### 13. The State-Driven UI Enabler Pattern

**Problem:**
In an agentic user interface, interactive components (like a chat window) often depend on data or context that must first be loaded by another component or agent. Allowing user interaction before this context is available can lead to a poor user experience, errors, or agents that hallucinate due to a lack of information.

**Solution:**
The user interface should be explicitly state-driven. An interactive agentic component should be disabled by default and only "enabled" once its required data context has been successfully loaded and passed to it.

**How it Works:**
1.  A "data-loading" component is responsible for fetching the initial context (e.g., a user's financial summary, a document to be discussed).
2.  While this data is loading, any interactive agent components (like a chat input) that depend on it are rendered in a disabled state.
3.  Once the data is successfully fetched, the parent component's state is updated.
4.  The application re-renders, passing the loaded data as a prop to the interactive agent component. The component now also receives a prop that enables it (e.g., `isEnabled={true}`).
5.  The user can now interact with the chat agent, which is guaranteed to have the necessary context to function correctly.

**Benefits:**
*   **Contextual Integrity:** Guarantees that the agent has the required context *before* it can be used, eliminating a whole class of potential state-related bugs and improving response quality.
*   **Guided User Experience:** Naturally guides the user through the intended workflow, preventing them from interacting with elements that are not yet ready and implicitly teaching them how the system works.
*   **Robust State Management:** Creates a clear, predictable, and one-way data flow that makes the application's state easy to reason about and debug.

### 14. The AI-Powered Guardrail Pattern

When building a system that relies on a knowledge base, it's crucial to ensure the quality of the information being added. The AI-Powered Guardrail pattern uses an LLM to act as a "content curator," evaluating new information before it's added to the knowledge base.

- **How it Works:**
    1.  Before new content is added to the knowledge base (e.g., a RAG corpus), it is first passed to an LLM-powered "curator" agent.
    2.  The curator agent is given a specific prompt that instructs it to evaluate the content based on a set of criteria (e.g., relevance, coherence, appropriateness).
    3.  The curator agent returns a score and a recommendation (e.g., "accept," "reject," "accept with modifications").
    4.  Based on the curator's recommendation, the system either adds the content to the knowledge base, rejects it, or flags it for human review.

- **Benefit:**
    - **Improved Knowledge Base Quality:** Prevents irrelevant, low-quality, or inappropriate content from polluting the knowledge base.
    - **Increased Agent Reliability:** A higher-quality knowledge base leads to more accurate and reliable agent responses.
    - **Automation of Content Curation:** Automates the process of content curation, which would otherwise be a manual and time-consuming task.

- **Example Prompt for the Curator Agent:**
    ```
    You are a content curator for a company knowledge base. Your goal is to be inclusive and helpful - if content could be useful to someone in the organization, it should generally be accepted.

    Evaluate content based on these criteria:
    1. **Could this help someone?** - Even niche technical docs, reference materials, or process notes can be valuable
    2. **Is it work-related?** - Broadly interpreted: tools, frameworks, configurations, troubleshooting, processes, etc.
    3. **Is it appropriate?** - Not spam, offensive, or completely personal content
    4. **Is it coherent?** - Readable and makes basic sense (doesn't need to be perfect)

    **Default to ACCEPTING content unless it's clearly:**
    - Spam or gibberish
    - Inappropriate/offensive
    - Completely personal/unrelated to work
    - Duplicate of existing content

    Content to evaluate: {content}
    Proposed title: {title}
    Proposed category: {category}

    Respond with a JSON object:
    - "relevant": true/false (be generous - when in doubt, say true)
    - "score": 0-100 (aim for 60+ for most work-related content)
    - "reason": brief explanation
    - "suggested_title": improved title if needed (optional)
    - "suggested_category": improved category if needed (optional)
    ```
