Project: AgentMap

# Claude Code Sub Agent Configuration
## 🚨 CRITICAL: CONCURRENT EXECUTION FOR ALL ACTIONS

**ABSOLUTE RULE**: ALL operations MUST be concurrent/parallel in a single message:

### 🔴 MANDATORY CONCURRENT PATTERNS:
1. **TodoWrite**: ALWAYS batch ALL todos in ONE call (5-10+ todos minimum)
2. **Task tool**: ALWAYS spawn ALL agents in ONE message with full instructions
3. **File operations**: ALWAYS batch ALL reads/writes/edits in ONE message
4. **Bash commands**: ALWAYS batch ALL terminal operations in ONE message
5. **Memory operations**: ALWAYS batch ALL memory store/retrieve in ONE message

### ⚡ GOLDEN RULE: "1 MESSAGE = ALL RELATED OPERATIONS"

**Examples of CORRECT concurrent execution:**
```javascript
// ✅ CORRECT: Everything in ONE message
[Single Message]:
  - TodoWrite { todos: [10+ todos with all statuses/priorities] }
  - Task("Agent 1 with full instructions and hooks")
  - Task("Agent 2 with full instructions and hooks")
  - Task("Agent 3 with full instructions and hooks")
  - Read("file1.js")
  - Read("file2.js")
  - Write("output1.js", content)
  - Write("output2.js", content)
  - Bash("npm install")
  - Bash("npm test")
  - Bash("npm run build")
```

**Examples of WRONG sequential execution:**
```javascript
// ❌ WRONG: Multiple messages (NEVER DO THIS)
Message 1: TodoWrite { todos: [single todo] }
Message 2: Task("Agent 1")
Message 3: Task("Agent 2")
Message 4: Read("file1.js")
Message 5: Write("output1.js")
Message 6: Bash("npm install")
// This is 6x slower and breaks coordination!
```

### 🎯 CONCURRENT EXECUTION CHECKLIST:

Before sending ANY message, ask yourself:
- ✅ Are ALL related TodoWrite operations batched together?
- ✅ Are ALL Task spawning operations in ONE message?
- ✅ Are ALL file operations (Read/Write/Edit) batched together?
- ✅ Are ALL bash commands grouped in ONE message?
- ✅ Are ALL memory operations concurrent?

## 🤖 Claude Sub-Agents Integration

This project includes 15 specialized AI sub-agents for enhanced development.

### Available Agents

The following agents are installed in `.claude/agents/`:

- **project-planner**: Strategic planning and task decomposition specialist
- **api-developer**: Backend API development specialist with PRP awareness
- **frontend-developer**: Modern web interface implementation specialist
- **tdd-specialist**: Test-driven development and comprehensive testing expert
- **code-reviewer**: Code quality, security, and best practices analyst
- **debugger**: Error analysis and debugging specialist
- **refactor**: Code refactoring and improvement specialist
- **doc-writer**: Technical documentation specialist
- **security-scanner**: Security vulnerability detection specialist
- **devops-engineer**: CI/CD and deployment automation specialist
- **product-manager**: Product requirements and user story specialist
- **marketing-writer**: Technical marketing content specialist
- **api-documenter**: OpenAPI/Swagger documentation specialist
- **test-runner**: Automated test execution specialist
- **shadcn-ui-builder**: UI/UX implementation with ShadCN components

### Using Sub-Agents

Agents work alongside your existing PRPs and can be invoked in several ways:

1. **Direct execution**: `claude-agents run <agent> --task "description"`
2. **Task tool in Claude Code**: `Task("agent-name: task description")`
3. **Agent slash commands**: Located in `.claude/commands/agents/`

### Memory System

Agents share context and coordinate through:
- **Memory Store**: `.swarm/memory.json` for persistent agent memory
- **Context Sharing**: Agents can access shared project context
- **PRP Integration**: Agents are aware of and can work with your PRPs

### Best Practices

- Use agents for specialized tasks that match their expertise
- Agents can read and understand your PRPs for context
- Multiple agents can work on different aspects of the same feature
- Memory system allows agents to build on each other's work
If ANY answer is "No", you MUST combine operations into a single message!
role: Lead Python dev/architect; enforce DRY,SOLID,YAGNI; ask before decisions.

context:
  projectName: AgentMap
  project_root: C:\Users\jwwel\Documents\code\AgentMap\
  source: src\agentmap\
  architecture: clean
  layers: [models, services, di_container, tests]
  principles:
    models: data-only
    services: all business logic  
    tests_di: real DI container
    tests_unit: MockServiceFactory
  docs:
    architecture: docs-docusaurus\docs\contributing
    project: docs-docusaurus\docs
    testing_approach: docs-docusaurus\docs\testing\testing-patterns.md
    documentation_guide: claude_documentation.md  # REQUIRED for all documentation tasks

structure:
  key_directories:
    services: src/agentmap/services/ (business logic)
    models: src/agentmap/models/ (data classes only)
    di: src/agentmap/di/ (dependency injection)
    agents: src/agentmap/agents/ (agent implementations)
    protocols: src/agentmap/services/protocols.py (service interfaces)
    storage: src/agentmap/services/storage/ (storage implementations)
    config: src/agentmap/services/config/ (configuration services)
    dev_artifacts: dev-artifacts/ (temporary development files)
  dev_workspace:
    location: dev-artifacts/{current-date-YYYY-MM-DD}-{task-name}/
    # DATE SOURCE: Look for "The current date is..." in your system context
    # This date is provided at the start of every conversation
    # Extract the date and format as YYYY-MM-DD
    # DO NOT USE FUTURE OR PAST DATES ONLY THE CURRENT DATE!
    structure:
      analysis: analysis/ (investigation and documentation)
      scripts: scripts/ (verification and test scripts)
      verification: verification/ (test results and validation)
      shared: shared/ (reusable development utilities)
    naming: YYYY-MM-DD-brief-task-description (use current date)
    lifecycle: Remove after task completion or keep if valuable
  critical_files:
    - src/agentmap/services/graph_runner_service.py (main orchestration)
    - src/agentmap/services/graph_execution_service.py (execution coordination)
    - src/agentmap/services/protocols.py (all service protocols)
    - src/agentmap/di/container.py (DI configuration)
    - src/agentmap/services/agent_factory_service.py (agent creation)
    - src/agentmap/services/host_protocol_configuration_service.py (host services)
  naming_patterns:
    services: "{Domain}Service" (e.g., GraphRunnerService)
    models: "{Domain}Model" or "{Domain}" (e.g., ExecutionResult)
    protocols: "{Service}Protocol" (e.g., LLMServiceProtocol)
    capabilities: "{Feature}CapableAgent" (e.g., LLMCapableAgent)
    tests: "test_{service_name}.py" (snake_case)

file_discovery:
  search_patterns:
    find_service: "grep -r 'class.*Service' src/agentmap/services/"
    find_protocol: "grep -r '@runtime_checkable' src/agentmap/services/protocols.py"
    find_di_registration: "grep -r 'register.*Service' src/agentmap/di/"
    find_agent_capability: "grep -r 'CapableAgent' src/agentmap/services/protocols.py"
  avoid_searching:
    use_protocols_file: Always check protocols.py first for capability interfaces
    use_existing_services: Search services/ directory before creating new ones
    check_di_container: Look at di/container.py for service relationships
    check_existing_patterns: Reference similar services for implementation patterns

service_patterns:
  new_service_checklist:
    - Check if functionality exists in existing services first
    - Use protocol-based dependency injection
    - Single responsibility (50 lines max per method)
    - Constructor dependency injection only
    - No direct container access
    - Follow logging_service.get_class_logger(self) pattern
  integration_points:
    graph_execution: GraphRunnerService, GraphExecutionService
    agent_creation: AgentFactoryService, GraphRunnerService._create_agent_instance
    service_injection: Check protocols.py for capability interfaces
    storage: StorageServiceManager (unified interface)
    configuration: AppConfigService (domain-specific), ConfigService (YAML only)
    host_services: HostProtocolConfigurationService (custom service injection)
  service_lifecycle:
    creation: Via DI container registration
    injection: Constructor parameters only
    configuration: Use builder pattern if complex
    testing: MockServiceFactory for unit tests, real DI for integration

simplicity_first:
  core_principle: "Choose the simplest solution that works. This is NEW CODE - no backwards compatibility needed."
  avoid_over_engineering:
    no_unnecessary_wrappers: |
      # ❌ Don't create wrapper classes for new integrations
      class MyServiceAdapter(ExternalInterface):
          def __init__(self, my_service: MyService):
              self.my_service = my_service
          def method(self): return self.my_service.method()
      
      # ✅ Make your service implement the interface directly  
      class MyService(ExternalInterface):
          def method(self): # Direct implementation
    
    no_premature_abstraction: |
      # ❌ Don't create "flexible" abstractions for single use cases
      class ConfigurableCheckpointStrategy:
          def save(self, type: str, data: Any): # Complex dispatch logic
      
      # ✅ Implement what you need directly
      class GraphCheckpointService(BaseCheckpointSaver):
          def put(self, config, checkpoint): # Direct LangGraph implementation
    
    no_backwards_compatibility: |
      # This is NEW CODE - don't maintain old interfaces
      # ❌ Don't keep deprecated methods "just in case"
      # ❌ Don't create migration layers for new features
      # ❌ Don't worry about "breaking changes" in unreleased code
      # ✅ Change interfaces to be better, simpler, clearer
    
    choose_direct_solutions:
      adapter_pattern: "Only use when integrating with external code you can't modify"
      facade_pattern: "Only use when simplifying complex external APIs"
      wrapper_classes: "Only use when you need to add behavior to existing objects"
      inheritance: "Use when there's genuine IS-A relationship and shared behavior"
      composition: "Default choice - but don't over-compose with unnecessary layers"
  
  when_to_be_simple:
    single_responsibility: "If a class does one thing well, don't split it unnecessarily"
    new_integrations: "Implement external interfaces directly on your services"
    data_transformation: "Use simple functions, not transformation pipelines"
    configuration: "Use direct properties, not configuration builders (unless truly complex)"
    error_handling: "Use exceptions and logging, not error handling frameworks"
  
  when_patterns_are_worth_it:
    dependency_injection: "Yes - for testing and flexibility"
    protocol_interfaces: "Yes - for clean contracts between services"
    factory_pattern: "Yes - when object creation is complex or conditional"
    service_layer: "Yes - to separate business logic from infrastructure"
    single_responsibility: "Yes - each service should have one clear purpose"
  
  decision_framework:
    ask_yourself:
      - "Am I solving a problem that actually exists?"
      - "Is this the simplest solution that works?"
      - "Am I adding layers to avoid changing existing code I control?"
      - "Will this pattern be used by more than one client?"
      - "Does this add real value or just theoretical flexibility?"
    red_flags:
      - Creating wrappers around your own code
      - "Future-proofing" for requirements that don't exist
      - Multiple layers doing the same thing
      - Patterns used because they're "best practice" without clear benefit
      - Maintaining deprecated code paths in new features

patterns:
  development_artifacts:
    workspace: dev-artifacts/{YYYY-MM-DD}-{task-name}/
    script_types:
      verification: Quick tests to validate assumptions
      analysis: Code inspection and pattern discovery
      debugging: Troubleshooting and investigation tools
      prototyping: Experimental implementations
    commit_guidelines: Commit useful artifacts, delete experimental ones
    cleanup: Remove task folders after completion unless valuable for reference
  debugging-troubleshooting:
    filename_for_documentation: DebugInfo-{timestamp}-{5 word bug description}.md
    file_contents:
      identified_problem_description: yes
      relevant_file_paths: yes
      proposed_solution: yes
  migration_or_refactoring:
    - update the code to follow guidelines
    - DO NOT create migration scripts or artifacts unless requested
    - DO NOT leave deprecated methods around unless requested
    - adjust tests to work with the newly refactored code
  testing:
    - unittest.TestCase classes
    - real DI in container tests
    - MockServiceFactory for service tests
    - focus on testing business logic and contracts
    - protocol-based mocking for external dependencies
  configuration:
    ConfigService: Only loads YAML
    AppConfigService: domain specific loaders
    StorageConfigService: domain specific loaders for storage settings
  error_handling:
    - Use specific exception types from exceptions/ directory
    - Log errors with context using logging_service
    - Graceful degradation where possible
    - Include troubleshooting info in error messages
  anti_patterns:
    - no new modules to pass tests
    - no business logic in model tests
    - no DI mocks in container tests
    - no business logic in ConfigService
    - no ad-hoc fix scripts
    - no files over 350 lines
    - no methods over 50 lines
    - no direct container access from services
    - no wrapper classes around your own code
    - no adapters for new integrations (implement interfaces directly)
    - no abstract base classes with single implementations
    - no "flexible" frameworks for single use cases

quick_reference:
  service_injection_pattern: |
    # Protocol definition in protocols.py
    @runtime_checkable
    class MyServiceProtocol(Protocol):
        def my_method(self) -> str: ...
    
    # Agent capability protocol  
    @runtime_checkable
    class MyCapableAgent(Protocol):
        def configure_my_service(self, service: MyServiceProtocol) -> None: ...
    
    # Usage in service
    if isinstance(agent, MyCapableAgent):
        agent.configure_my_service(self.my_service)
        configured_count += 1
  
  di_registration_pattern: |
    # In di/container.py
    container.register(MyService, MyService, dependencies=[
        'dependency1', 'dependency2', 'logging_service'
    ])
  
  service_template: |
    class MyService:
        def __init__(self, dependency1: Dep1Protocol, logging_service: LoggingService):
            self.dependency1 = dependency1
            self.logger = logging_service.get_class_logger(self)
        
        def my_method(self) -> ResultType:
            self.logger.debug("Starting my_method")
            # Implementation here
            return result
  
  test_patterns:
    unit_service: Use MockServiceFactory for dependencies
    integration: Use real DI container
    agent_test: Focus on business logic, mock external services
    protocol_mock: Mock protocols, not concrete classes

decisions:
  new_service_when:
    - Distinct business domain (user management, graph execution, etc.)
    - 3+ classes would use the functionality
    - Complex logic that deserves isolated testing
    - Cross-cutting concern (logging, configuration, etc.)
  extend_existing_when:
    - Adding method to existing domain
    - Simple helper functionality
    - Single use case
    - Related to existing service responsibility
  refactor_when:
    - Service exceeds 350 lines
    - Method exceeds 50 lines
    - Multiple responsibilities detected
    - Code duplication across services
  common_questions:
    "Where does X logic go?": Check domain - models=data, services=logic
    "How to inject Y?": Create protocol, use isinstance() pattern
    "Should I create new service?": Follow service_patterns.new_service_checklist
    "How to test X?": Unit tests with MockServiceFactory, integration with DI
    "Where to configure Y?": AppConfigService for domain logic, ConfigService for YAML

communication_style:
  decisions_require_involvement: true
  provide_complete_code: true
  require_plan_before_code: true
  confirm_approach: true
  max_function_lines: 50
  max_file_lines: 350
  follow_clean_architecture_patterns: true
  ask_if_tests_pass: true
  on_logic_test_fail: ask for direction
  efficiency_preferences:
    prefer_existing_patterns: Always reference existing service implementations
    minimize_file_exploration: Use structure guide instead of directory listings
    quick_decisions: Use decision framework for service creation choices
    no_redundant_searches: Check quick_reference before asking implementation questions
    reference_similar_code: Point to existing services with similar patterns
    validate_assumptions: Confirm understanding before implementing
    use_dev_workspace: Create scripts and analysis files in dev-artifacts/{date}-{task}/