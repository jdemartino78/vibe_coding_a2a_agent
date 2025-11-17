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
# Author: Gemini

import json
import logging
from typing import Dict
from json import JSONDecodeError
from dotenv import load_dotenv
from pydantic import ValidationError

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart
from a2a.utils import new_agent_text_message


from shared.adk_base_mcp_agent_executor import AdkBaseMcpAgentExecutor
from shared.data_models import WeatherForecastData, validate_and_parse

# Set logging
logging.getLogger().setLevel(logging.INFO)
load_dotenv()

# --- AGENT CONFIGURATION ---

UPDATED_WEATHER_AGENT_INSTRUCTION = """
You are a specialized weather data processing agent. Your single purpose is to take raw, text-based weather forecast data and convert it into a structured JSON object.

**CRITICAL RULES:**

1.  **Analyze Input:** The user will provide raw text from a weather service.
2.  **Extract & Transform:** From this text, you MUST:
    a.  Infer the full city and country name.
    b.  If the user provides a city without a state, use the user's location to infer the state.
    c.  If there are multiple cities with the same name, default to the most populated city.
    d.  If you are unable to infer the location, ask the user for clarification.
    e.  Extract the primary temperature value.
    f.  **Convert the temperature from Fahrenheit to Celsius.** Round to the nearest whole number.
    g.  Read all the forecast details and synthesize them into a single, concise `forecast_summary` string.
3.  **Format Output:** Your final output MUST be a single JSON object that strictly conforms to the `WeatherForecastData` schema. **Do not add any other text, greetings, or explanations.**

**EXAMPLE:**
- **User Input:** "Forecast for New York, NY: Today, sunny, with a high near 88. Tonight, mostly clear, with a low around 72."
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


class WeatherAgentExecutor(AdkBaseMcpAgentExecutor):
    """Agent Executor for weather-related queries that returns structured JSON."""

    def get_agent_config(self) -> Dict:
        """Return weather agent configuration."""
        return WEATHER_AGENT_CONFIG

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Overrides the base execute method to perform an extra validation step.
        It runs the standard MCP agent logic, then validates the raw text output
        against the WeatherForecastData Pydantic schema and returns the validated
        JSON as the final response.
        """
        # 1. Run the base executor to get the raw text output from the LLM
        raw_text_output = await super().execute_and_get_text_output(context, event_queue)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        # 2. Validate and parse the raw output into structured JSON
        logging.info(f"Raw LLM output for validation: {raw_text_output}")
        try:
            validated_data = validate_and_parse(raw_text_output, WeatherForecastData)
            final_json_output = json.dumps(validated_data, indent=2)

            # 3. Return the validated JSON as an artifact
            await updater.add_artifact(
                [TextPart(text=final_json_output)],
                name="answer",
            )
            await updater.complete()
            logging.info("Successfully returned validated JSON for Weather Agent.")

        except (JSONDecodeError, ValidationError) as e:
            # Assumed to be a clarifying question, pass it back to the user
            logging.info("Output is not JSON, treating as a clarifying question and setting task to input_required.")
            await updater.update_status(
                TaskState.input_required, message=new_agent_text_message(raw_text_output)
            )
