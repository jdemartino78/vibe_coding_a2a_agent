# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Dict, Optional
from dotenv import load_dotenv

from shared.base_executor import BaseMcpAgentExecutor
from shared.models import WeatherForecastData

# Load environment variables
load_dotenv()

# --- AGENT CONFIGURATION ---

UPDATED_WEATHER_AGENT_INSTRUCTION = """
You are a specialized weather data retrieval and processing agent. Your purpose is to fetch weather forecasts for a given location using your tools and then convert that data into a structured JSON object.

**CRITICAL RULES:**

1.  **Fetch Data:** When a user asks for the weather (e.g., "weather in NYC"), you MUST first call the `weather_search` tool to retrieve the forecast. Do not ask the user for data; fetch it yourself.
2.  **Extract & Transform:** From the tool's output, you MUST:
    a.  Infer the full city and country name.
    b.  If the user provides a city without a state, use the user's location to infer the state.
    c.  If there are multiple cities with the same name, default to the most populated city.
    d.  If you are unable to infer the location, ask the user for clarification.
    e.  Extract the primary temperature value.
    f.  **Convert the temperature from Fahrenheit to Celsius.** Round to the nearest whole number.
    g.  Read all the forecast details and synthesize them into a single, concise `forecast_summary` string.
3.  **Format Output:** Your final output MUST be a single JSON object that strictly conforms to the `WeatherForecastData` schema. **Do not add any other text, greetings, or explanations.**

**EXAMPLE:**
- **Tool Output:** "Forecast for New York, NY: Today, sunny, with a high near 88. Tonight, mostly clear, with a low around 72."
- **Your Output (JSON):**
  ```json
  {
    "city": "New York, NY",
    "country": "USA",
    "temperature_c": 31,
    "condition": "Sunny",
    "forecast_summary": "Today will be sunny with a high of 88°F. Tonight will be mostly clear with a low of 72°F."
  }
  ```
"""

WEATHER_AGENT_CONFIG: Dict = {
    "name": "weather_agent",
    "description": "An agent that can help questions about weather",
    "instruction": UPDATED_WEATHER_AGENT_INSTRUCTION,
    "model": "gemini-2.5-flash",
    "mcp_url_env_var": "WEA_MCP_SERVER_URL",
}


class WeatherAgentExecutor(BaseMcpAgentExecutor):
    """Agent Executor for weather-related queries that returns structured JSON."""

    def __init__(self, agent_engine_id: Optional[str] = None) -> None:
        super().__init__(agent_engine_id=agent_engine_id, output_schema=WeatherForecastData)

    def get_agent_config(self) -> Dict:
        """Return weather agent configuration."""
        return WEATHER_AGENT_CONFIG