# Vertex AI Multi-Agent & Agent-to-Agent Examples

This repository contains a collection of sample projects demonstrating various approaches to building multi-agent systems on Google Cloud's Vertex AI platform. The projects explore different frameworks and architectures for enabling agents to collaborate and complete complex tasks.

## Overview

The central theme is an Agent-to-Agent (A2A) architecture where multiple specialized agents collaborate to fulfill a user's request. The primary use case involves a main "Hosting" agent that orchestrates a "Weather" agent and a "Cocktail" agent to provide travel and leisure recommendations.

## Project Structure

The repository is a monorepo organized into several self-contained sub-projects. Each directory represents a different architectural approach to the same multi-agent problem.

### Core Implementations

*   `a2a-on-ae-multiagent-memorybank/`
    A variation that focuses on a specific approach to managing agent memory and state persistence across turns.

### Supporting Directories

*   `mcp_servers/`
    Contains the backend tool servers (APIs) for the Cocktail and Weather agents. These are simple web servers that the agents can call to get information (e.g., "what is the weather in Paris?").


## Getting Started

Each sub-project in this repository is designed to be self-contained. To run a specific example:

1.  Choose an implementation directory that you are interested in (e.g., `a2a-on-ae-multiagent-memorybank/`).
2.  Navigate into that directory: `cd a2a-on-ae-multiagent-memorybank/`
3.  Follow the setup and execution instructions provided in that directory's own `README.md` file. You will typically find instructions for setting up a Python virtual environment, installing dependencies, and running the application.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.