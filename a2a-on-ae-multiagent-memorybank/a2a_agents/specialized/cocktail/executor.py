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

from shared.base_executor import BaseMcpAgentExecutor
from shared.models import CocktailData, validate_and_parse

# Set logging
logging.getLogger().setLevel(logging.INFO)
load_dotenv()

# --- AGENT CONFIGURATION ---

UPDATED_COCKTAIL_AGENT_INSTRUCTION = """
You are a specialized cocktail data processing agent. Your single purpose is to take raw, text-based cocktail information and convert it into a structured JSON object.

**CRITICAL RULES:**

1.  **Analyze Input:** The user will provide raw text from a cocktail database.
2.  **Extract & Transform:** From this text, you MUST extract the following fields:
    a.  `cocktail_name`
    b.  `category`
    c.  `glass_type`
    d.  `instructions`
    e.  `ingredients` (This must be a JSON array of strings, where each string is an ingredient and its measurement).
3.  **Format Output:** Your final output MUST be a single JSON object that strictly conforms to the `CocktailData` schema. **Do not add any other text, greetings, or explanations.**

**EXAMPLE:**
- **User Input:** "ID: 11007\nName: Margarita\nCategory: Ordinary Drink\nGlass: Cocktail glass\nInstructions: Rub the rim of the glass with the lime slice... Shake the tequila, Cointreau, and lime juice with ice...\nIngredients:\n- 1 1/2 oz Tequila\n- 1/2 oz Triple sec\n- 1 oz Lime juice\n- Salt"
- **Your Output (JSON):**
  ```json
  {
    "cocktail_name": "Margarita",
    "category": "Ordinary Drink",
    "glass_type": "Cocktail glass",
    "instructions": "Rub the rim of the glass with the lime slice... Shake the tequila, Cointreau, and lime juice with ice...",
    "ingredients": [
      "1 1/2 oz Tequila",
      "1/2 oz Triple sec",
      "1 oz Lime juice",
      "Salt"
    ]
  }
  ```
"""

COCKTAIL_AGENT_CONFIG: Dict = {
    "name": "cocktail_agent",
    "description": "An agent that can help questions about cocktail",
    "instruction": UPDATED_COCKTAIL_AGENT_INSTRUCTION,
    "model": "gemini-2.5-flash",
    "mcp_url_env_var": "CT_MCP_SERVER_URL",
}


class CocktailAgentExecutor(BaseMcpAgentExecutor):
    """Agent Executor for cocktail-related queries that returns structured JSON."""

    def get_agent_config(self) -> Dict:
        """Return cocktail agent configuration."""
        return COCKTAIL_AGENT_CONFIG

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Overrides the base execute method to perform an extra validation step.
        It runs the standard MCP agent logic, then validates the raw text output
        against the CocktailData Pydantic schema and returns the validated
        JSON as the final response.
        """
        # 1. Run the base executor to get the raw text output from the LLM
        raw_text_output = await super().execute_and_get_text_output(context, event_queue)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        # 2. Validate and parse the raw output into structured JSON
        logging.info(f"Raw LLM output for validation: {raw_text_output}")
        try:
            validated_data = validate_and_parse(raw_text_output, CocktailData)
            final_json_output = json.dumps(validated_data, indent=2)

            # 3. Return the validated JSON as an artifact
            await updater.add_artifact(
                [TextPart(text=final_json_output)],
                name="answer",
            )
            await updater.complete()
            logging.info("Successfully returned validated JSON for Cocktail Agent.")

        except (JSONDecodeError, ValidationError) as e:
            # Assumed to be a clarifying question, pass it back to the user
            logging.info("Output is not JSON, treating as a clarifying question and setting task to input_required.")
            await updater.update_status(
                TaskState.input_required, message=new_agent_text_message(raw_text_output)
            )
