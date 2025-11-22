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
from typing import Type, TypeVar
from pydantic import BaseModel, Field, ValidationError
import logging

# --- DATA MODELS ---

class WeatherForecastData(BaseModel):
    """Pydantic model for structured weather forecast data."""
    city: str = Field(..., description="The full city and state name (e.g., 'New York, NY').")
    country: str = Field("USA", description="The country where the city is located.")
    temperature_c: int = Field(..., description="The temperature in Celsius.")
    condition: str = Field(..., description="A brief description of the weather condition (e.g., 'Sunny', 'Cloudy').")
    forecast_summary: str = Field(..., description="A concise summary of the weather forecast.")

class CocktailData(BaseModel):
    """Pydantic model for structured cocktail data."""
    cocktail_name: str = Field(..., description="The name of the cocktail.")
    category: str = Field(..., description="The category of the cocktail (e.g., 'Ordinary Drink').")
    glass_type: str = Field(..., description="The recommended glass for the cocktail.")
    instructions: str = Field(..., description="The instructions for preparing the cocktail.")
    ingredients: list[str] = Field(..., description="A list of ingredients and their measurements.")
    history: str = Field(None, description="Optional history, origin, or fun facts about the cocktail.")

# --- VALIDATION LOGIC ---

T = TypeVar('T', bound=BaseModel)

def validate_and_parse(raw_text: str, model: Type[T]) -> dict:
    """
    Cleans raw LLM text output, validates it against a Pydantic model,
    and returns the validated data as a dictionary.

    Args:
        raw_text: The raw string output from the language model.
        model: The Pydantic model class to validate against.

    Returns:
        A dictionary of the validated data.

    Raises:
        ValidationError: If the text cannot be parsed into the model.
        JSONDecodeError: If the text is not valid JSON.
    """
    logging.info(f"Attempting to validate raw text against {model.__name__}:\n{raw_text}")

    # Clean the text: remove markdown backticks and "json" specifier
    cleaned_text = raw_text.strip().replace("```json", "").replace("```", "").strip()

    # Parse the cleaned text as JSON
    try:
        json_data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: Failed to decode text into JSON. Text: '{cleaned_text}'")
        raise e

    # Validate the JSON data against the Pydantic model
    try:
        validated_instance = model.model_validate(json_data)
        logging.info(f"Successfully validated data against {model.__name__}.")
        return validated_instance.model_dump()
    except ValidationError as e:
        logging.error(f"ValidationError: Pydantic model validation failed. Data: {json_data}")
        raise e