"""
Memory management for AgentMap LLM agents.

This module provides utilities for managing conversation history in graph state,
following LangGraph's state-based memory approach.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Message:
    """Simple message representation for conversation history."""

    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format suitable for LLM APIs."""
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        role = data.get("role", "user")
        content = data.get("content", "")
        return cls(role=role, content=content)


def get_memory(
    state: Dict[str, Any], memory_key: str = "memory"
) -> List[Dict[str, str]]:
    """
    Get the message history from state, initializing if needed.

    Args:
        state: The graph state
        memory_key: Key to use for storing memory in state

    Returns:
        List of message dictionaries in format ready for LLM API
    """
    # Initialize memory in state if it doesn't exist
    if memory_key not in state:
        state[memory_key] = []

    # Get memory and ensure it's a list
    memory = state[memory_key]
    if not isinstance(memory, list):
        memory = []
        state[memory_key] = memory

    # Convert all entries to proper message dictionaries
    messages = []
    for msg in memory:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append(msg)
        elif isinstance(msg, Message):
            messages.append(msg.to_dict())
        elif isinstance(msg, str):
            # Assume it's user content if just a string
            messages.append({"role": "user", "content": msg})

    return messages


def add_message(
    state: Dict[str, Any], role: str, content: str, memory_key: str = "memory"
) -> Dict[str, Any]:
    """
    Add a message to the conversation history in state.

    Args:
        state: The graph state
        role: Message role ("user", "assistant", or "system")
        content: Message content
        memory_key: Key to use for storing memory in state

    Returns:
        Updated state
    """
    # Get current messages
    messages = get_memory(state, memory_key)

    # Add new message
    messages.append({"role": role, "content": content})

    # Update state
    state[memory_key] = messages

    return state


def add_user_message(
    state: Dict[str, Any], content: str, memory_key: str = "memory"
) -> Dict[str, Any]:
    """Add a user message to conversation history."""
    return add_message(state, "user", content, memory_key)


def add_assistant_message(
    state: Dict[str, Any], content: str, memory_key: str = "memory"
) -> Dict[str, Any]:
    """Add an assistant message to conversation history."""
    return add_message(state, "assistant", content, memory_key)


def add_system_message(
    state: Dict[str, Any], content: str, memory_key: str = "memory"
) -> Dict[str, Any]:
    """Add a system message to conversation history."""
    return add_message(state, "system", content, memory_key)


def clear_memory(state: Dict[str, Any], memory_key: str = "memory") -> Dict[str, Any]:
    """Clear conversation history from state."""
    state[memory_key] = []
    return state


def truncate_memory(
    state: Dict[str, Any], max_messages: int, memory_key: str = "memory"
) -> Dict[str, Any]:
    """
    Truncate conversation history to a maximum number of messages.

    Args:
        state: The graph state
        max_messages: Maximum number of messages to keep (excluding system)
        memory_key: Key to use for storing memory in state

    Returns:
        Updated state
    """
    messages = get_memory(state, memory_key)

    if len(messages) <= max_messages:
        return state

    # Separate system messages
    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    other_messages = [msg for msg in messages if msg.get("role") != "system"]

    # Keep the most recent non-system messages up to max_messages
    remaining_slots = max_messages - len(system_messages)
    if remaining_slots > 0:
        truncated = system_messages + other_messages[-remaining_slots:]
    else:
        # If max_messages is less than number of system messages, just keep system
        truncated = system_messages[:max_messages]

    state[memory_key] = truncated
    return state
