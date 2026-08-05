"""
Data-only structured tool-call model for LLM responses.

Introduced by E05-F06. ``LLMToolCall`` mirrors the ``LLMResponse`` family
convention (frozen dataclass, no business logic) and carries exactly what a
caller-owned tool loop needs to execute a tool and reply — no raw provider
payload is retained.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class LLMToolCall:
    """
    A single normalized tool call requested by the model.

    Populated from the provider response's normalized tool-call channel
    (LangChain's ``AIMessage.tool_calls``), which already reconciles the
    incompatible Anthropic / OpenAI / Google shapes.

    ``id`` is the provider-assigned tool-call identifier — the value the
    caller must echo back as ``tool_call_id`` on the tool-result message.
    ``arguments`` is already a parsed dict at the normalized LangChain layer;
    AgentMap does not re-parse a JSON string.
    """

    id: str
    name: str
    arguments: Dict[str, Any]
