# AgentMap Usage Documentation

This documentation provides detailed information about using AgentMap, a declarative orchestration framework for defining and executing LangGraph workflows.

## Table of Contents

### Core Concepts
- [Agentmap Features](agentmap_features.md) - Overview of AgentMap capabilities and features
- [AgentMap CSV Schema Documentation](agentmap_csv_schema_documentation.md) - Complete CSV schema reference
- [State Management and Data Flow](state_management_and_data_flow.md) - How data flows between agents

### Agent Development
- [Agent Development Contract](agent_contract.md) - Required interface and patterns for all agents
- [Service Injection](service_injection.md) - Protocol-based dependency injection system
- [Host Service Integration](host-service-integration.md) - Extend AgentMap with custom services and agents
- [AgentMap Agent Types](agentmap_agent_types.md) - Built-in agent types and basic usage
- [Advanced Agent Types](advanced_agent_types.md) - Advanced agents and comprehensive context configuration

### Workflow Management
- [Prompt Management in AgentMap](prompt_management_in_agentmap.md) - Template system and prompt resolution
- [Orchestration Agent](orchestration_agent.md) - Dynamic workflow routing and orchestration
- [AgentMap Example Workflows](agentmap_example_workflows.md) - Complete workflow examples

### Operations and Tools
- [AgentMap CLI Documentation](agentmap_cli_documentation.md) - Command-line interface and tools
- [AgentMap Execution Tracking](agentmap_execution_tracking.md) - Performance monitoring and debugging
- [AgentMap Cloud Storage](agentmap_cloud_storage.md) - Cloud storage integration
- [LangChain Memory in AgentMap](langchain_memory_in_agentmap.md) - Memory management patterns

## Getting Started Guide

For new developers, we recommend following this learning path:

1. **Start with Core Concepts**: Read [Agentmap Features](agentmap_features.md) and [CSV Schema](agentmap_csv_schema_documentation.md)
2. **Understand Agent Architecture**: Review [Agent Contract](agent_contract.md) and [Service Injection](service_injection.md)
3. **Explore Agent Types**: Study [Agent Types](agentmap_agent_types.md) and [Advanced Agent Types](advanced_agent_types.md)
4. **Build Workflows**: Practice with [Example Workflows](agentmap_example_workflows.md)
5. **Extend AgentMap**: Learn [Host Service Integration](host-service-integration.md) to inject custom services
6. **Advanced Topics**: Dive into orchestration, memory management, and cloud storage

## Key Architecture Concepts

### Clean Architecture Pattern
AgentMap follows clean architecture principles with:
- **Infrastructure Services**: Core services injected via constructor (logging, state management)
- **Business Services**: Specialized services configured via protocols (LLM, storage, vector)
- **Protocol-Based Injection**: Type-safe service configuration using Python protocols

### Service Injection System
The [Service Injection](service_injection.md) documentation covers:
- Dependency injection container architecture
- Protocol implementation patterns
- Service configuration examples
- Debugging and troubleshooting

### Host Service Integration
The [Host Service Integration](host-service-integration.md) documentation provides:
- Extending AgentMap with custom domain-specific services
- Protocol-based service injection for custom agents
- Configuration patterns for external service integration
- Best practices for maintaining clean architecture boundaries

### Agent Development Patterns
The [Agent Contract](agent_contract.md) defines:
- Modern constructor patterns with infrastructure service injection
- Protocol-based business service configuration
- Debugging hooks and service information methods
- Complete implementation examples