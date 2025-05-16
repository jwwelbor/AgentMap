# AgentMap Memory Tests

This directory contains test files for validating the conversation memory functionality in AgentMap graphs, particularly focusing on LLM agent memory persistence.

## Overview

These tests verify that conversation memory is properly maintained and passed between LLM nodes in AgentMap graphs. They cover:

1. Memory serialization and deserialization
2. Memory persistence across multiple agent invocations
3. Different memory types (buffer, window, summary, token)
4. State adapter memory handling
5. End-to-end graph memory functionality

## Test Files

- `test_memory.py` - Core tests for memory serialization and deserialization
- `test_memory_integration.py` - Tests for memory passing between agents
- `test_memory_e2e.py` - End-to-end tests with CSV-defined graphs
- `test_state_adapter.py` - Tests for the StateAdapter's memory handling
- `test_llm_agent.py` - Tests for the LLMAgent's memory functionality
- `test_memory_utils.py` - Helper utilities for memory testing

## Required Dependencies

These tests require additional dependencies beyond the core AgentMap package:

```
pip install langchain
pip install openai
pip install anthropic
pip install google-generativeai
```

You can install all required packages with:

```
pip install agentmap[llm]
```

## Running the Tests

You can run all memory tests with:

```bash
pytest tests/ -v
```

To run a specific test file:

```bash
pytest tests/test_memory.py -v
```

To run tests with specific markers (e.g., end-to-end tests):

```bash
pytest tests/ -m e2e -v
```

## Test Environment Variables

For tests that interact with real LLM APIs (not recommended), you can set the following environment variables:

- `OPENAI_API_KEY` - For OpenAI API tests
- `ANTHROPIC_API_KEY` - For Anthropic API tests
- `GOOGLE_API_KEY` - For Google API tests

However, most tests mock the API calls to avoid actual API usage.

## Test Markers

The tests use the following pytest markers:

- `skipif` - Skips tests when required dependencies aren't available
- `integration` - Marks integration tests between components
- `e2e` - Marks end-to-end tests
- `parametrize` - Tests different configurations

## Extending the Tests

When adding new memory functionality to AgentMap, consider adding tests to verify:

1. Memory consistency - Memory should maintain the same content through serialization/deserialization
2. Memory persistence - Memory should be correctly passed between agent nodes
3. Memory compatibility - Memory should work with different state formats (dict, Pydantic)
4. Memory error handling - Errors should be properly handled without losing memory

## Mocking Strategy

The tests use several mocking strategies to avoid actual API calls:

1. Patching `_call_api` methods to return mock responses
2. Creating mock LangChain clients
3. Using mock memory objects
4. Simulating graph execution with mock graphs

## Notes on LangChain Compatibility

These tests rely on LangChain's memory functionality. If LangChain's API changes, these tests may need to be updated. The current tests are compatible with:

- LangChain (>=0.0.267)
- LangChain Core (>=0.0.10)
