import os

from anthropic import Anthropic

from agentmap.agents.base_agent import BaseAgent
from agentmap.config import get_llm_config


class AnthropicAgent(BaseAgent):
    def __init__(self, name: str, prompt: str, context: dict = None, model: str = None, temperature: float = None):
        super().__init__(name, prompt, context)
        # Get config with fallbacks
        config = get_llm_config("anthropic")
        self.model = model or config.get("model", "claude-3-sonnet-20240229")
        self.temperature = temperature or config.get("temperature", 0.7)
        
    def run(self, input_data: dict) -> dict:
        # Get API key with fallback to environment
        config = get_llm_config("anthropic")
        api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            return {
                "error": "Anthropic API key not found in config or environment",
                "last_action_success": False
            }
        
        client = Anthropic(api_key=api_key)

        # Format prompt with input data
        try:
            formatted_prompt = self.prompt
            if input_data.get("input_fields"):
                formatted_prompt = self.prompt.format(**input_data["input_fields"])
                
            completion = client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=self.temperature,
                messages=[{"role": "user", "content": formatted_prompt}]
            )
            
            result = completion.content[0].text.strip()
            
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