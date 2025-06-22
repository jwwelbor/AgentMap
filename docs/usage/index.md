# AgentMap Usage Documentation

This documentation provides detailed information about using AgentMap, a declarative orchestration framework for defining and executing LangGraph workflows.

## Table of Contents

### Core Concepts
- [Agentmap Features](./usage/agentmap_features.md) - Overview of AgentMap capabilities and features
- [AgentMap CSV Schema Documentation](./usage/agentmap_csv_schema_documentation.md) - Complete CSV schema reference
- [State Management and Data Flow](./usage/state_management_and_data_flow.md) - How data flows between agents

### Agent Development
- [Agent Development Contract](./usage/agent_contract.md) - Required interface and patterns for all agents
- [Service Injection](./usage/service_injection.md) - Protocol-based dependency injection system
- [Host Service Integration](./usage/host-service-integration.md) - Extend AgentMap with custom services and agents
- [AgentMap Agent Types](./usage/agentmap_agent_types.md) - Built-in agent types and basic usage
- [Advanced Agent Types](./usage/advanced_agent_types.md) - Advanced agents and comprehensive context configuration

### Workflow Management
- [Prompt Management in AgentMap](./usage/prompt_management_in_agentmap.md) - Template system and prompt resolution
- [Orchestration Agent](./usage/orchestration_agent.md) - Dynamic workflow routing and orchestration
- [AgentMap Example Workflows](./usage/agentmap_example_workflows.md) - Complete workflow examples

### Operations and Tools
- [AgentMap CLI Documentation](./usage/agentmap_cli_documentation.md) - Command-line interface and tools
- [AgentMap Execution Tracking](./usage/agentmap_execution_tracking.md) - Performance monitoring and debugging
- [Storage Services](./usage/storage_services.md) - Unified storage operations for CSV, files, and data
- [AgentMap Cloud Storage](./usage/agentmap_cloud_storage.md) - Cloud storage integration
- [LangChain Memory in AgentMap](./usage/langchain_memory_in_agentmap.md) - Memory management patterns

## Getting Started Guide

For new developers, we recommend following this learning path:

1. **Start with Core Concepts**: Read [Agentmap Features](./usage/agentmap_features.md) and [CSV Schema](./usage/agentmap_csv_schema_documentation.md)
2. **Understand Agent Architecture**: Review [Agent Contract](./usage/agent_contract.md) and [Service Injection](./usage/service_injection.md)
3. **Learn Data Operations**: Study [Storage Services](./usage/storage_services.md) for file and data management
4. **Explore Agent Types**: Study [Agent Types](./usage/agentmap_agent_types.md) and [Advanced Agent Types](./usage/advanced_agent_types.md)
5. **Build Workflows**: Practice with [Example Workflows](./usage/agentmap_example_workflows.md)
6. **Extend AgentMap**: Learn [Host Service Integration](./usage/host-service-integration.md) to inject custom services
7. **Advanced Topics**: Dive into orchestration, memory management, and cloud storage

## Key Architecture Concepts

### Clean Architecture Pattern
AgentMap follows clean architecture principles with:
- **Infrastructure Services**: Core services injected via constructor (logging, state management)
- **Business Services**: Specialized services configured via protocols (LLM, storage, vector)
- **Protocol-Based Injection**: Type-safe service configuration using Python protocols

### Service Injection System
The [Service Injection](./usage/service_injection.md) documentation covers:
- Dependency injection container architecture
- Protocol implementation patterns
- Service configuration examples
- Debugging and troubleshooting

### Host Service Integration
The [Host Service Integration](./usage/host-service-integration.md) documentation provides:
- Extending AgentMap with custom domain-specific services
- Protocol-based service injection for custom agents
- Configuration patterns for external service integration
- Best practices for maintaining clean architecture boundaries

### Agent Development Patterns
The [Agent Contract](./usage/agent_contract.md) defines:
- Modern constructor patterns with infrastructure service injection
- Protocol-based business service configuration
- Debugging hooks and service information methods
- Complete implementation examples