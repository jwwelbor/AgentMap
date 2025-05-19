"""
Memory utilities for conversation history.

This module provides utilities for working with LangChain memory objects,
including serialization and deserialization for state persistence.
"""

from typing import Any, Dict, List, Optional, Union
from agentmap.logging import get_logger
logger = get_logger(__name__, False)

# Flag to indicate if LangChain is available
try:
    import langchain
    from langchain.memory import (
        ConversationBufferMemory,
        ConversationBufferWindowMemory,
        ConversationSummaryMemory,
        ConversationTokenBufferMemory
    )
    from langchain.schema import HumanMessage, AIMessage, SystemMessage
except ImportError:
    logger.warning("LangChain not installed. Memory functionality will be limited.")
    raise ImportError("LangChain is not installed. Please install it to use this module.")


def serialize_memory(memory: Any) -> Optional[Dict[str, Any]]:
    """
    Serialize LangChain memory objects for state persistence.
    
    Args:
        memory: LangChain memory object
        
    Returns:
        Serialized representation of memory or None
    """
    if not memory:
        return None
        
    if not hasattr(memory, "chat_memory"):
        return memory
    
    try:
        # Extract messages from memory
        messages = []
        for msg in memory.chat_memory.messages:
            messages.append({
                "type": msg.type,  # 'human' or 'ai' or 'system'
                "content": msg.content
            })
        
        # Determine memory type
        memory_type = "buffer"
        if isinstance(memory, ConversationBufferWindowMemory):
            memory_type = "buffer_window"
            k = getattr(memory, "k", 5)
            return {
                "_type": "langchain_memory",
                "memory_type": memory_type,
                "k": k,
                "messages": messages
            }
        elif isinstance(memory, ConversationSummaryMemory):
            memory_type = "summary"
        elif isinstance(memory, ConversationTokenBufferMemory):
            memory_type = "token_buffer"
            max_token_limit = getattr(memory, "max_token_limit", 2000)
            return {
                "_type": "langchain_memory",
                "memory_type": memory_type,
                "max_token_limit": max_token_limit,
                "messages": messages
            }
        
        # Create serialized representation
        return {
            "_type": "langchain_memory",
            "memory_type": memory_type,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error serializing memory: {str(e)}")
        return None


def deserialize_memory(memory_data: Dict[str, Any]) -> Any:
    """
    Recreate LangChain memory objects from serialized data.
    
    Args:
        memory_data: Serialized memory data
        
    Returns:
        LangChain memory object or original data if not valid
    """
    if not memory_data or not isinstance(memory_data, dict):
        return memory_data
        
    if memory_data.get("_type") != "langchain_memory":
        return memory_data
    
    try:
        # Create appropriate memory object
        memory_type = memory_data.get("memory_type", "buffer")
        
        if memory_type == "buffer_window":
            k = memory_data.get("k", 5)
            memory = ConversationBufferWindowMemory(
                k=k, 
                return_messages=True,
                memory_key="history"
            )
        elif memory_type == "summary":
            memory = ConversationSummaryMemory(
                return_messages=True,
                memory_key="history"
            )
        elif memory_type == "token_buffer":
            max_token_limit = memory_data.get("max_token_limit", 2000)
            memory = ConversationTokenBufferMemory(
                max_token_limit=max_token_limit,
                return_messages=True,
                memory_key="history"
            )
        else:
            # Default to buffer memory
            memory = ConversationBufferMemory(
                return_messages=True,
                memory_key="history"
            )
        
        # Restore messages
        for msg in memory_data.get("messages", []):
            msg_type = msg.get("type", "")
            content = msg.get("content", "")
            
            if msg_type == "human":
                memory.chat_memory.add_user_message(content)
            elif msg_type == "ai":
                memory.chat_memory.add_ai_message(content)
            elif msg_type == "system":
                # System messages need special handling
                memory.chat_memory.messages.append(SystemMessage(content=content))
        
        return memory
    except Exception as e:
        logger.error(f"Error deserializing memory: {str(e)}")
        return memory_data
