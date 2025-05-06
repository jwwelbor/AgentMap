# agent_loader.py

import importlib

from agentmap.agents.base_agent import BaseAgent

class AgentLoader:
    def __init__(self, context: dict):
        self.context = context
        # Import agents here to avoid circular imports
        from agentmap.agents.builtins.default_agent import DefaultAgent
        from agentmap.agents.builtins.branching_agent import BranchingAgent
        from agentmap.agents.builtins.success_agent import SuccessAgent
        from agentmap.agents.builtins.failure_agent import FailureAgent
        from agentmap.agents.builtins.echo_agent import EchoAgent
        
        # Optional imports
        try:
            from agentmap.agents.builtins.openai_agent import OpenAIAgent
        except ImportError:
            OpenAIAgent = None
            
        try:
            from agentmap.agents.builtins.anthropic_agent import AnthropicAgent
        except ImportError:
            AnthropicAgent = None
            
        try:
            from agentmap.agents.builtins.google_agent import GoogleAgent
        except ImportError:
            GoogleAgent = None
            
        self.agent_mapping = {
            "default": DefaultAgent,
            "branching": BranchingAgent,
            "success": SuccessAgent,
            "failure": FailureAgent,
            "echo": EchoAgent,
        }
        
        # Add optional agents if available
        if OpenAIAgent:
            self.agent_mapping.update({
                "openai": OpenAIAgent,
                "chatgpt": OpenAIAgent,
                "gpt": OpenAIAgent
            })
            
        if AnthropicAgent:
            self.agent_mapping.update({
                "anthropic": AnthropicAgent,
                "claude": AnthropicAgent
            })
            
        if GoogleAgent:
            self.agent_mapping.update({
                "google": GoogleAgent,
                "gemini": GoogleAgent
            })

    def get_agent(self, agent_type: str, name: str, prompt: str):
        agent_class = self.agent_mapping.get(agent_type.lower() if agent_type else "default")
        if not agent_class:
            raise ValueError(f"Agent type '{agent_type}' not found.")
        return agent_class(name=name, prompt=prompt, context=self.context)


def create_agent(agent_type: str, name: str, prompt: str, context: dict):
    loader = AgentLoader(context)
    return loader.get_agent(agent_type, name, prompt)