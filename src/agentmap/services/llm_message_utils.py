"""
LLM Message Utilities for handling message conversion and extraction.

Provides utilities for converting messages between different formats and
extracting content for analysis.
"""

from typing import Any, Dict, List


class LLMMessageUtils:
    """Utilities for handling LLM messages."""

    @staticmethod
    def extract_prompt_from_messages(messages: List[Dict[str, str]]) -> str:
        """
        Extract the main prompt content from messages for complexity analysis.

        Args:
            messages: List of message dictionaries

        Returns:
            Combined prompt text
        """
        if not messages:
            return ""

        # Combine all user and system messages
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["user", "system"] and content:
                prompt_parts.append(content)

        return " ".join(prompt_parts)

    @staticmethod
    def convert_messages_to_langchain(messages: List[Dict[str, str]]) -> List[Any]:
        """
        Convert messages to LangChain message format.

        Args:
            messages: List of message dictionaries

        Returns:
            List of LangChain message objects
        """
        try:
            from langchain.schema import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            # Try newer imports
            try:
                from langchain_core.messages import (
                    AIMessage,
                    HumanMessage,
                    SystemMessage,
                )
            except ImportError:
                # Last resort - return as-is and hope the client handles it
                return messages

        langchain_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # default to user
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages
