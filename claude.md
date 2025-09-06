Project: AgentMap
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