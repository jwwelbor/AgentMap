"""
LLM-based matching utilities for OrchestratorService.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from agentmap.services.llm_service import LLMService
from agentmap.services.prompt_manager_service import PromptManagerService


class LLMMatcher:
    def __init__(
        self,
        logger: logging.Logger,
        prompt_manager: PromptManagerService,
        llm_service: LLMService,
        keyword_parser: Callable[[Dict[str, Any]], List[str]],
    ):
        self.logger = logger
        self.prompt_manager = prompt_manager
        self.llm_service = llm_service
        self._parse_keywords = keyword_parser

    def llm_match(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        llm_config: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        if not self.llm_service:
            raise ValueError("LLM service not configured")
        nodes_text = self._format_node_descriptions(available_nodes)
        additional_context = (
            f"\n\nAdditional context: {context['routing_context']}"
            if context and context.get("routing_context")
            else ""
        )
        formatted_prompt = self.prompt_manager.format_prompt(
            "file:orchestrator/intent_matching_v1.txt",
            {
                "nodes_text": nodes_text,
                "input_text": input_text,
                "additional_context": additional_context,
            },
        )
        if additional_context:
            formatted_prompt += additional_context
        llm_config = llm_config or {}
        llm_response = self.llm_service.call_llm(
            provider=llm_config.get("provider", "openai"),
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=llm_config.get("temperature", 0.2),
        )
        return self._extract_node_from_response(llm_response, available_nodes)

    def _format_node_descriptions(self, nodes: Dict[str, Dict[str, Any]]) -> str:
        if not nodes:
            return "No nodes available"
        descriptions = []
        for node_name, node_info in nodes.items():
            if not isinstance(node_info, dict):
                descriptions.append(f"- Node: {node_name}\n  Status: Invalid format")
                continue
            keywords = self._parse_keywords(node_info)
            keywords_text = (
                f" (Keywords: {', '.join(keywords[:5])})" if keywords else ""
            )
            descriptions.append(
                f"- Node: {node_name}\n  Description: {node_info.get('description', '')}\n  Prompt: {node_info.get('prompt', '')}\n  Type: {node_info.get('type', '')}{keywords_text}"
            )
        return "\n".join(descriptions)

    def _extract_node_from_response(
        self, llm_response: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> str:
        try:
            if isinstance(llm_response, str) and llm_response.strip().startswith("{"):
                parsed = json.loads(llm_response.strip())
                if (
                    "selectedNode" in parsed
                    and parsed["selectedNode"] in available_nodes
                ):
                    return parsed["selectedNode"]
        except json.JSONDecodeError as e:
            self.logger.debug(f"LLM response was not valid JSON: {e}")
        llm_response_str = str(llm_response).strip()
        if llm_response_str in available_nodes:
            return llm_response_str
        matches = [name for name in available_nodes.keys() if name in llm_response_str]
        if matches:
            return max(matches, key=len)
        self.logger.warning(
            "Couldn't extract node from LLM response. Using first available."
        )
        return next(iter(available_nodes.keys()))
