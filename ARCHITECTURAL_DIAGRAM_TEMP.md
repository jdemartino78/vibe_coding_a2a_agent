# Architectural Diagram Overview (Temporary)

```mermaid
graph TD
    subgraph User Experience
        A[Frontend Web App (Gradio)] --> B(User Query);
    end

    subgraph Google Cloud Project
        subgraph Vertex AI Agent Engine
            subgraph Orchestrator Agent (Shell)
                C{OrchestratorAgentExecutor}
                C --> D[AdkOrchestratorAgentExecutor (Brain)];
            end
            subgraph Specialized Agents
                E[Weather Agent]
                F[Cocktail Agent]
            end
        end

        subgraph Cloud Run
            G[Weather MCP Server]
            H[Cocktail MCP Server]
        end

        subgraph Persistence Layer
            I[AlloyDB Database]
            J[Secret Manager]
        end

        subgraph Authentication & Tools
             K[a2a_tools.py]
             L[remote_connection.py]
             M[auth_utils.py]
             N[custom_context_builder.py]
        end


        B -- HTTP/S Request --> C;

        C -- Delegate Task (Tool Call) --> K;
        K -- Remote Connection --> L;
        L -- Authenticated HTTP/S --> E;
        L -- Authenticated HTTP/S --> F;
        L -- Uses OIDC Token --> M;
        N -- Passes user_id --> K;

        E -- HTTP/S (Tool Call) --> G;
        F -- HTTP/S (Tool Call) --> H;

        C -- Stores/Retrieves Task State --> I;
        C -- Stores/Retrieves Session Mapping --> I;
        J -- Provides DB Credentials --> C;

        C -- Stores/Retrieves Long-Term Memory --> Vertex AI Agent Engine;
        E -- Stores/Retrieves Long-Term Memory --> Vertex AI Agent Engine;
        F -- Stores/Retrieves Long-Term Memory --> Vertex AI Agent Engine;
    end

    style C fill:#f9f,stroke:#333,stroke-width:2px;
    style D fill:#ccf,stroke:#333,stroke-width:2px;
    style E fill:#cec,stroke:#333,stroke-width:2px;
    style F fill:#cec,stroke:#333,stroke-width:2px;
    style G fill:#dee,stroke:#333,stroke-width:2px;
    style H fill:#dee,stroke:#333,stroke-width:2px;
    style I fill:#fcc,stroke:#333,stroke-width:2px;
    style J fill:#fcf,stroke:#333,stroke-width:2px;
    style K fill:#ddf,stroke:#333,stroke-width:2px;
    style L fill:#ddf,stroke:#333,stroke-width:2px;
    style M fill:#ddf,stroke:#333,stroke-width:2px;
    style N fill:#ddf,stroke:#333,stroke-width:2px;

    linkStyle 0 stroke-width:2px,fill:none,stroke:lightgray;
    linkStyle 1 stroke-width:2px,fill:none,stroke:lightgray;
    linkStyle 2 stroke-width:2px,fill:none,stroke:lightgray;
    linkStyle 3 stroke-width:2px,fill:none,stroke:lightgray;
    linkStyle 4 stroke-width:2px,fill:none,stroke:lightgray;
    linkStyle 5 stroke-width:2px,fill:none,stroke:blue;
    linkStyle 6 stroke-width:2px,fill:none,stroke:blue;
    linkStyle 7 stroke-width:2px,fill:none,stroke:green;
    linkStyle 8 stroke-width:2px,fill:none,stroke:green;
    linkStyle 9 stroke-width:2px,fill:none,stroke:purple;
    linkStyle 10 stroke-width:2px,fill:none,stroke:purple;
    linkStyle 11 stroke-width:2px,fill:none,stroke:darkred;
    linkStyle 12 stroke-width:2px,fill:none,stroke:orange;
    linkStyle 13 stroke-width:2px,fill:none,stroke:black;
    linkStyle 14 stroke-width:2px,fill:none,stroke:black;
    linkStyle 15 stroke-width:2px,fill:none,stroke:darkgreen;
    linkStyle 16 stroke-width:2px,fill:none,stroke:darkgreen;
    linkStyle 17 stroke-width:2px,fill:none,stroke:darkgreen;

    click B "https://example.com/user-interaction-details" _blank
    click C "https://example.com/orchestrator-details" _blank
    click I "https://cloud.google.com/alloydb/docs" _blank
```