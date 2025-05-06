import os

import google.generativeai as genai

from agentmap.agents.base_agent import BaseAgent
from agentmap.config import get_llm_config


class GoogleAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context: dict = None, model: str = None, temperature: float = None):
        super().__init__(name, prompt, context)
        # Get config with fallbacks
        config = get_llm_config("google")
        self.model = model or config.get("model", "gemini-1.0-pro")
        self.temperature = temperature or config.get("temperature", 0.7)
        
    def run(self, input_data: dict) -> dict:
        # Get API key with fallback to environment
        config = get_llm_config("google")
        api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            return {
                "error": "Google API key not found in config or environment",
                "last_action_success": False
            }
        
        # Configure the Gemini API client
        genai.configure(api_key=api_key)

        # Format prompt with input data
        try:
            formatted_prompt = self.prompt
            if input_data.get("input_fields"):
                formatted_prompt = self.prompt.format(**input_data["input_fields"])
            
            # Create a model instance
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": 1024,
                }
            )
            
            # Generate content
            response = model.generate_content(formatted_prompt)
            
            # Extract the response text
            if hasattr(response, 'text'):
                result = response.text.strip()
            else:
                # Handle alternative response formats
                result = str(response).strip()
            
            output_field = input_data.get("output_field", "output")
            
            return {
                output_field: result,
                "last_action_success": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "last_action_success": False
            }