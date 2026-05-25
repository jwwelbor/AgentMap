---
title: Token and Resource Limits
sidebar_position: 7
description: Overview of token limit enforcement and resource constraints in AgentMap LLM and storage services.
keywords: [token limits, max_tokens, memory management, resource constraints]
---

# Token and Resource Limits

AgentMap has several layers of token and resource limit enforcement, though they differ significantly in their implementation status and configurability.

## 1. LLM Response Token Limit (`max_tokens`)
This is the most strictly enforced token limit in the project. It controls the maximum length of the AI's response.

*   **Enforcement**: **Yes**. It is enforced by passing the value directly to LangChain's model classes (e.g., `ChatOpenAI`, `ChatAnthropic`), which then transmit it to the provider's API.
*   **Configurability**: Highly configurable at three levels of priority:
    1.  **Node Context**: Directly in the workflow CSV's `context` column (e.g., `"{max_tokens: 2048}"`).
    2.  **Routing Activity/Tier**: In `agentmap_config.yaml` under `routing.activities.{activity}.{tier}.max_tokens`.
    3.  **Global Provider Default**: In `agentmap_config.yaml` under `llm.providers.{provider}.max_tokens`.

## 2. Conversation Memory Token Limit (`max_token_limit`)
This is intended to manage the "context window" by pruning or summarizing conversation history.

*   **Enforcement**: **No**. While the configuration field exists, the current `LLMAgent` implementation only enforces **message-count based limits** via `buffer_window_size`.
*   **Configurability**: **Yes**. It can be configured in the `memory` section of `agentmap_config.yaml`.
*   **LangChain Context**: This is intended for `token_buffer` memory types, but the core logic for actual token-based truncation is not currently active in the builtin agents.

## 3. Complexity Analysis "Token" Approximation
The routing system uses length thresholds to decide which model to use (e.g., routing complex tasks to Claude Opus vs. simple ones to Haiku).

*   **Enforcement**: Uses character count thresholds as a proxy for tokens.
*   **Configurability**: Configurable in `agentmap_config.yaml` under `routing.complexity_analysis.prompt_length_thresholds`.

## 4. Storage Structural Limits
The `MemoryStorageService` (used for in-memory data persistence, not LLM memory) enforces hard limits:

*   `max_collections`: Default 100.
*   `max_documents_per_collection`: Default 10,000.
*   `max_document_size`: Default 1MB (in bytes).

## Summary Table

| Limit Type | Configurable? | Enforced? | Implementation |
| :--- | :--- | :--- | :--- |
| **Response Tokens** | Yes (YAML/CSV) | **Yes** | `LLMService` -> LangChain |
| **Memory Messages** | Yes (YAML) | **Yes** | `LLMAgent` message truncation |
| **Memory Tokens** | Yes (YAML) | **No** | (Config-only) |
| **Routing Length** | Yes (YAML) | **Yes** | `ComplexityAnalyzer` thresholds |
| **Storage Size** | Yes (YAML) | **Yes** | `MemoryStorageService` checks |
