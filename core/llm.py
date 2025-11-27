# core/llm.py

import json
import os
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv is optional

T = TypeVar("T", bound=BaseModel)


def _extract_json_from_response(text: str) -> str:
    """
    Extract JSON from response text, handling markdown code blocks.

    Args:
        text: Raw response text that may contain JSON in code blocks

    Returns:
        Extracted JSON string
    """
    text = text.strip()

    # Check if wrapped in markdown code blocks
    if text.startswith("```"):
        # Find the closing ```
        lines = text.split("\n")
        # Skip first line (```json or ```)
        json_lines = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            json_lines.append(line)
        return "\n".join(json_lines)
    return text


class LLMClient:
    """
    Minimal wrapper around Google Gemini LLM provider using the latest API.
    
    Defaults are chosen to encourage deterministic, reproducible outputs:
    - temperature=0.0 (fully deterministic)
    - top_p=1.0 (no nucleus sampling)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ):
        """
        Initialize the LLM client using the latest Google GenAI SDK.

        Args:
            api_key: API key for Google Gemini. If None, reads from GEMINI_API_KEY env var.
            model_name: Model name to use. If None, reads from GEMINI_MODEL env var or defaults to "gemini-2.5-flash".
            temperature: Sampling temperature (0.0-2.0). Default 0.0 for deterministic outputs.
            top_p: Nucleus sampling parameter (0.0-1.0). Default 1.0 for deterministic outputs.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.temperature = temperature
        self.top_p = top_p

        if not self.api_key:
            raise ValueError(
                "API key not provided. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Use the latest Google GenAI SDK
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.genai = genai
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Install with: pip install google-genai"
            )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """
        Call Google Gemini and coerce its JSON output into `response_model`.

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            response_model: Pydantic model class to validate the response against

        Returns:
            Validated instance of response_model

        Raises:
            RuntimeError: If JSON parsing fails or validation fails, includes raw response
        """
        try:
            from google.genai import types
            
            # Add JSON format instruction to user prompt
            json_instruction = "\n\nIMPORTANT: You must respond with ONLY valid JSON. Do not include any markdown code blocks, explanations, or text outside the JSON."
            full_prompt = f"{user_prompt}{json_instruction}"
            
            # Use the latest API with proper system_instruction support
            # Use instance configuration for deterministic outputs
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    candidate_count=1,  # Explicitly request one response
                )
            )

            # Extract content
            raw_response = response.text
            if not raw_response:
                raise RuntimeError("Model returned empty response")

        except Exception as e:
            raise RuntimeError(
                f"Failed to call Gemini API: {e}"
            ) from e

        # Extract JSON (handles markdown code blocks)
        json_text = _extract_json_from_response(raw_response)

        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Model returned invalid JSON: {e}\n\nRaw response:\n{raw_response}\n\nExtracted JSON text:\n{json_text}"
            ) from e

        # Validate against Pydantic model
        try:
            return response_model.model_validate(data)
        except ValidationError as e:
            raise RuntimeError(
                f"Model JSON didn't match schema: {e}\n\nRaw response:\n{raw_response}"
            ) from e
