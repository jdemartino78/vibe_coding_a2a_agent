# A2A Streaming Implementation Plan via Cloud Run

This document outlines the technically-grounded plan for migrating the A2A hosting agent from Agent Engine to a containerized Cloud Run service to enable response streaming, conforming to the official A2A streaming protocol.

## 1. Conforming to the A2A Streaming Protocol

As detailed in the [official A2A documentation on Streaming & Async](https://a2a-protocol.org/latest/topics/streaming-and-async/), true A2A streaming is an asynchronous, two-step process. It is not a simple, single streaming HTTP response. Our architecture must reflect this.

The flow is as follows:

1.  **`POST /message:send`**: The client sends the initial request. The server **must not** hold this connection open. Instead, it immediately starts the agent execution in the background, and returns a `202 Accepted` status code. The body of this response contains a `Task` object with a unique `task_id`.

2.  **`GET /message:stream?task_id={task_id}`**: The client immediately uses the `task_id` from the first response to open a *new* long-lived connection to this streaming endpoint.

3.  **Event Stream**: The server holds the `stream` connection open and sends a stream of `Task` objects as the agent's status changes (e.g., `WORKING`, `ARTIFACT_ADDED`, `COMPLETED`). Partial LLM responses are sent as `ARTIFACT_ADDED` events.

## 2. Cloud Run Architecture

To implement this protocol, we will containerize the hosting agent and deploy it as a Cloud Run service.

1.  **FastAPI Application (`main.py`)**:
    *   A new `main.py` file will serve as the entrypoint for the service.
    *   It will run a Uvicorn server with a FastAPI application.
    *   It will expose the two required A2A endpoints: `message:send` and `message:stream`.

2.  **Dockerfile**:
    *   A `Dockerfile` will be created to package the FastAPI app, the agent executor code, and all dependencies.

3.  **Deployment (`deploy_hosting_agent.sh`)**:
    *   A new deployment script will use `gcloud run deploy` to build and deploy the container.
    *   It will be configured with **`--min-instances=1`** to eliminate cold starts, which is critical for a responsive, conversational agent.

## 3. Backend Implementation Details

1.  **`AdkBaseMcpAgentExecutor` (`.../common/adk_base_mcp_agent_executor.py`)**:
    *   The `execute` method will be refactored. Its primary job is to publish events to an `EventQueue`.
    *   Inside the `async for event in self.runner.run_async(...)` loop, we will add a check for `if event.is_llm_response():`.
    *   When an LLM chunk is available, we will call `updater.add_artifact([TextPart(text=chunk)], name="answer_chunk")`. This places an `ARTIFACT_ADDED` event on the queue for the streaming endpoint to pick up.
    *   When `event.is_final_response()` is true, we will call `updater.complete()`, which places the final `COMPLETED` event on the queue.

2.  **FastAPI Endpoints (`.../hosting_agent/main.py`)**:
    *   The `POST /message:send` endpoint will instantiate the `HostingAgentExecutor`, call its `execute` method in the background (e.g., using `asyncio.create_task`), and immediately return the `202 Accepted` response with the initial `Task` object.
    *   The `GET /message:stream` endpoint will be a FastAPI `StreamingResponse`. It will listen to the `EventQueue` for the specified `task_id` and `yield` each event to the client as it arrives.

## 4. Frontend Implementation Details

1.  **Client Logic (`.../frontend_option1/main.py`)**:
    *   The `get_response_from_agent` function will be rewritten to follow the two-step A2A flow.
    *   **Step 1:** It will first call `a2a_client.send_message(...)`. It will no longer loop over this response. It will simply get the `task` object.
    *   **Step 2:** It will then immediately call a new method, `a2a_client.stream_message(task_id=task.task_id)`.
    *   The function will then `async for event in ...` the result of the `stream_message` call, inspect each `Task` event for new artifacts, and `yield` the updated text to the Gradio UI.

This plan provides a robust, scalable, and protocol-compliant path to enabling a high-performance, streaming experience for the agent.
