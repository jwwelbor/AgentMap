#!/usr/bin/env python3
"""
AgentMap Host Application Integration Example

This script demonstrates how to integrate a host application with AgentMap's
extended service injection system. It shows the complete workflow from
service registration to graph execution with host services.

Run this script to see host service integration in action:
    python examples/host_integration/integration_example.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add AgentMap to path for this example
# In a real application, AgentMap would be installed as a package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# AgentMap imports
from agentmap.di.containers import ApplicationContainer
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.config.config_service import ConfigService

# Host application imports
from .host_services import (
    DatabaseService, EmailService, NotificationService, FileService,
    create_database_service, create_email_service, 
    create_notification_service, create_file_service
)
from .host_protocols import (
    DatabaseServiceProtocol, EmailServiceProtocol, 
    NotificationServiceProtocol, FileServiceProtocol
)
from .custom_agents import (
    DatabaseAgent, EmailAgent, NotificationAgent, 
    FileAgent, MultiServiceAgent, RobustHostServiceAgent
)


class HostApplicationIntegrationExample:
    """
    Example class demonstrating complete host application integration.
    
    This class shows how to:
    1. Configure AgentMap with host application settings
    2. Register host services with the DI container
    3. Register custom agents with host service protocols
    4. Execute graphs that use host services
    5. Handle errors and edge cases
    """
    
    def __init__(self, config_path: Path = None):
        """
        Initialize the host application integration example.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path or Path(__file__).parent / "agentmap_config.yaml"
        self.container = None
        self.logger = None
        self.setup_complete = False
        
    def setup(self) -> None:
        """Set up the complete integration environment."""
        print("🚀 Starting AgentMap Host Application Integration Example")
        print("=" * 60)
        
        try:
            # Step 1: Create and configure container
            print("1. Creating and configuring DI container...")
            self._setup_container()
            
            # Step 2: Register host services
            print("2. Registering host services...")
            self._register_host_services()
            
            # Step 3: Register custom agents
            print("3. Registering custom agents...")
            self._register_custom_agents()
            
            # Step 4: Bootstrap application
            print("4. Bootstrapping AgentMap application...")
            self._bootstrap_application()
            
            # Step 5: Verify setup
            print("5. Verifying integration setup...")
            self._verify_setup()
            
            self.setup_complete = True
            print("✅ Host application integration setup complete!")
            print()
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            raise
    
    def _setup_container(self) -> None:
        """Create and configure the DI container."""
        # Override config path if using custom config
        self.container = ApplicationContainer()
        if self.config_path.exists():
            self.container.config_path.override(str(self.config_path))
        
        # Initialize logging service
        app_config = self.container.app_config_service()
        logging_service = self.container.logging_service()
        self.logger = logging_service.get_logger("host_integration_example")
        
        self.logger.info("DI container configured successfully")
    
    def _register_host_services(self) -> None:
        """Register host services with the container."""
        # Get configuration for services
        app_config = self.container.app_config_service()
        host_config = app_config.get_host_application_config()
        logging_service = self.container.logging_service()
        
        if not host_config.get("enabled", True):
            self.logger.warning("Host application support is disabled in configuration")
            return
        
        services_config = host_config.get("services", {})
        
        # Register database service
        if services_config.get("database_service", {}).get("enabled", True):
            self.container.register_host_factory(
                service_name="database_service",
                factory_function=create_database_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[DatabaseServiceProtocol],
                metadata={"description": "Host database service", "version": "1.0"}
            )
            self.logger.info("✅ Database service registered")
        
        # Register email service
        if services_config.get("email_service", {}).get("enabled", True):
            self.container.register_host_factory(
                service_name="email_service",
                factory_function=create_email_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[EmailServiceProtocol],
                metadata={"description": "Host email service", "version": "1.0"}
            )
            self.logger.info("✅ Email service registered")
        
        # Register notification service
        if services_config.get("notification_service", {}).get("enabled", True):
            self.container.register_host_factory(
                service_name="notification_service",
                factory_function=create_notification_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[NotificationServiceProtocol],
                metadata={"description": "Host notification service", "version": "1.0"}
            )
            self.logger.info("✅ Notification service registered")
        
        # Register file service
        if services_config.get("file_service", {}).get("enabled", True):
            self.container.register_host_factory(
                service_name="file_service",
                factory_function=create_file_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[FileServiceProtocol],
                metadata={"description": "Host file service", "version": "1.0"}
            )
            self.logger.info("✅ File service registered")
        
        # Log summary of registered services
        host_services = self.container.get_host_services()
        self.logger.info(f"Total host services registered: {len(host_services)}")
    
    def _register_custom_agents(self) -> None:
        """Register custom agents with AgentMap's agent registry."""
        agent_registry = self.container.agent_registry_service()
        
        # Register host service agents
        agent_registry.register_agent("database_agent", DatabaseAgent)
        agent_registry.register_agent("email_agent", EmailAgent)
        agent_registry.register_agent("notification_agent", NotificationAgent)
        agent_registry.register_agent("file_agent", FileAgent)
        agent_registry.register_agent("multi_service_agent", MultiServiceAgent)
        agent_registry.register_agent("robust_agent", RobustHostServiceAgent)
        
        self.logger.info("✅ Custom agents registered with AgentMap")
    
    def _bootstrap_application(self) -> None:
        """Bootstrap the AgentMap application with all services."""
        bootstrap_service = self.container.application_bootstrap_service()
        bootstrap_service.bootstrap_application()
        
        # Get bootstrap summary
        summary = bootstrap_service.get_bootstrap_summary()
        self.logger.info(f"AgentMap bootstrap completed: {summary['total_agents_registered']} agents available")
        
        if summary.get('host_application', {}).get('enabled'):
            self.logger.info("✅ Host application integration active")
    
    def _verify_setup(self) -> None:
        """Verify that the integration setup is working correctly."""
        # Check host services
        host_services = self.container.get_host_services()
        if not host_services:
            raise ValueError("No host services registered")
        
        # Check protocol implementations
        protocol_implementations = self.container.get_protocol_implementations()
        if not protocol_implementations:
            raise ValueError("No protocol implementations found")
        
        # Check agent registry
        agent_registry = self.container.agent_registry_service()
        agent_types = agent_registry.get_registered_agent_types()
        
        host_agent_types = [
            "database_agent", "email_agent", "notification_agent", 
            "file_agent", "multi_service_agent", "robust_agent"
        ]
        
        for agent_type in host_agent_types:
            if agent_type not in agent_types:
                raise ValueError(f"Agent type '{agent_type}' not registered")
        
        self.logger.info("✅ Integration setup verification passed")
    
    def run_database_example(self) -> Dict[str, Any]:
        """
        Run database service integration example.
        
        Returns:
            Example execution results
        """
        print("📊 Running Database Service Example")
        print("-" * 40)
        
        try:
            # Get services
            graph_runner = self.container.graph_runner_service()
            
            # Create a simple state for database operations
            initial_state = {
                "operation": "get_users",
                "graph_name": "database_example"
            }
            
            # Create a database agent manually for demonstration
            database_agent = DatabaseAgent(
                name="example_db_agent",
                context={"operation": "get_users"},
                logger=self.logger
            )
            
            # Configure the agent with services (simulating graph runner behavior)
            self.container.configure_host_protocols(database_agent)
            
            # Run the agent
            result = database_agent.run(initial_state)
            
            print(f"✅ Database example completed successfully")
            print(f"   Users found: {result.get('database_result', {}).get('count', 0)}")
            
            return result
            
        except Exception as e:
            print(f"❌ Database example failed: {e}")
            self.logger.error(f"Database example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_email_example(self) -> Dict[str, Any]:
        """
        Run email service integration example.
        
        Returns:
            Example execution results
        """
        print("📧 Running Email Service Example")
        print("-" * 40)
        
        try:
            # Create an email agent
            email_agent = EmailAgent(
                name="example_email_agent",
                context={"operation": "send_notification"},
                logger=self.logger
            )
            
            # Configure with services
            self.container.configure_host_protocols(email_agent)
            
            # Create state for email operation
            email_state = {
                "operation": "send_notification",
                "to_email": "test@example.com",
                "operation_name": "Host Integration Example",
                "operation_result": "Email service working correctly"
            }
            
            # Run the agent
            result = email_agent.run(email_state)
            
            print(f"✅ Email example completed successfully")
            print(f"   Notification sent: {result.get('email_result', {}).get('notification_sent', False)}")
            
            return result
            
        except Exception as e:
            print(f"❌ Email example failed: {e}")
            self.logger.error(f"Email example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_notification_example(self) -> Dict[str, Any]:
        """
        Run notification service integration example.
        
        Returns:
            Example execution results
        """
        print("🔔 Running Notification Service Example")
        print("-" * 40)
        
        try:
            # Create a notification agent
            notification_agent = NotificationAgent(
                name="example_notification_agent",
                context={"operation": "send_agent_notification"},
                logger=self.logger
            )
            
            # Configure with services
            self.container.configure_host_protocols(notification_agent)
            
            # Create state for notification operation
            notification_state = {
                "operation": "send_agent_notification",
                "operation_name": "Host Integration Test",
                "operation_result": "All services working correctly",
                "channels": ["console", "slack"]
            }
            
            # Run the agent
            result = notification_agent.run(notification_state)
            
            print(f"✅ Notification example completed successfully")
            notification_results = result.get('notification_result', {}).get('notifications_sent', {})
            print(f"   Channels notified: {list(notification_results.keys())}")
            
            return result
            
        except Exception as e:
            print(f"❌ Notification example failed: {e}")
            self.logger.error(f"Notification example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_multi_service_example(self) -> Dict[str, Any]:
        """
        Run multi-service integration example.
        
        Returns:
            Example execution results
        """
        print("🎯 Running Multi-Service Integration Example")
        print("-" * 40)
        
        try:
            # Create a multi-service agent
            multi_agent = MultiServiceAgent(
                name="example_multi_agent",
                context={"operation": "process_user_request"},
                logger=self.logger
            )
            
            # Configure with all available host services
            self.container.configure_host_protocols(multi_agent)
            
            # Create state for multi-service operation
            multi_state = {
                "operation": "process_user_request",
                "user_id": 1,
                "graph_name": "multi_service_example"
            }
            
            # Run the agent
            result = multi_agent.run(multi_state)
            
            print(f"✅ Multi-service example completed successfully")
            multi_result = result.get('multi_service_result', {})
            if 'user' in multi_result:
                print(f"   Processed user: {multi_result['user']['name']}")
                print(f"   Tasks found: {len(multi_result.get('tasks', []))}")
            
            return result
            
        except Exception as e:
            print(f"❌ Multi-service example failed: {e}")
            self.logger.error(f"Multi-service example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_error_handling_example(self) -> Dict[str, Any]:
        """
        Run error handling and graceful degradation example.
        
        Returns:
            Example execution results
        """
        print("🛡️ Running Error Handling Example")
        print("-" * 40)
        
        try:
            # Create a robust agent
            robust_agent = RobustHostServiceAgent(
                name="example_robust_agent",
                context={"operation": "graceful_degradation_test"},
                logger=self.logger
            )
            
            # Configure with services (some may fail)
            configured_count = self.container.configure_host_protocols(robust_agent)
            
            # Create state for robust operation
            robust_state = {
                "send_notification": True,
                "email": "test@example.com"
            }
            
            # Run the agent
            result = robust_agent.run(robust_state)
            
            print(f"✅ Error handling example completed")
            robust_result = result.get('robust_agent_result', {})
            print(f"   Services configured: {configured_count}")
            print(f"   Operations completed: {len(robust_result.get('operations_completed', []))}")
            print(f"   Operations failed: {len(robust_result.get('operations_failed', []))}")
            print(f"   Status: {robust_result.get('status', 'unknown')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error handling example failed: {e}")
            self.logger.error(f"Error handling example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_service_status_example(self) -> Dict[str, Any]:
        """
        Run service status and monitoring example.
        
        Returns:
            Service status information
        """
        print("📈 Running Service Status Example")
        print("-" * 40)
        
        try:
            # Get container status
            host_services = self.container.get_host_services()
            protocol_implementations = self.container.get_protocol_implementations()
            
            # Get bootstrap status
            bootstrap_service = self.container.application_bootstrap_service()
            bootstrap_summary = bootstrap_service.get_bootstrap_summary()
            
            # Get graph runner status
            graph_runner = self.container.graph_runner_service()
            service_info = graph_runner.get_service_info()
            
            status_info = {
                "host_services": {
                    "count": len(host_services),
                    "services": list(host_services.keys())
                },
                "protocol_implementations": {
                    "count": len(protocol_implementations),
                    "protocols": list(protocol_implementations.keys())
                },
                "bootstrap_summary": {
                    "total_agents": bootstrap_summary.get("total_agents_registered", 0),
                    "host_application_enabled": bootstrap_summary.get("host_application", {}).get("enabled", False)
                },
                "graph_runner_capabilities": {
                    "host_service_injection": service_info.get("capabilities", {}).get("host_service_injection", False),
                    "dynamic_protocol_discovery": service_info.get("capabilities", {}).get("dynamic_protocol_discovery", False)
                }
            }
            
            print(f"✅ Service status retrieved successfully")
            print(f"   Host services: {status_info['host_services']['count']}")
            print(f"   Protocol implementations: {status_info['protocol_implementations']['count']}")
            print(f"   Total agents: {status_info['bootstrap_summary']['total_agents']}")
            print(f"   Host injection enabled: {status_info['graph_runner_capabilities']['host_service_injection']}")
            
            return status_info
            
        except Exception as e:
            print(f"❌ Service status example failed: {e}")
            self.logger.error(f"Service status example error: {e}")
            return {"error": str(e), "status": "failed"}
    
    def run_all_examples(self) -> Dict[str, Any]:
        """
        Run all integration examples.
        
        Returns:
            Combined results from all examples
        """
        if not self.setup_complete:
            raise ValueError("Setup must be completed before running examples")
        
        print("\n🎬 Running All Host Integration Examples")
        print("=" * 60)
        
        results = {}
        
        # Run each example
        examples = [
            ("database", self.run_database_example),
            ("email", self.run_email_example),
            ("notification", self.run_notification_example),
            ("multi_service", self.run_multi_service_example),
            ("error_handling", self.run_error_handling_example),
            ("service_status", self.run_service_status_example)
        ]
        
        for example_name, example_func in examples:
            print()
            try:
                results[example_name] = example_func()
            except Exception as e:
                print(f"❌ Example '{example_name}' failed: {e}")
                results[example_name] = {"error": str(e), "status": "failed"}
        
        print("\n" + "=" * 60)
        print("🏁 All Examples Complete")
        
        # Summary
        successful = sum(1 for r in results.values() if r.get("status") != "failed")
        total = len(results)
        print(f"📊 Summary: {successful}/{total} examples completed successfully")
        
        return results


def main():
    """Main function to run the host integration example."""
    try:
        # Create and run the integration example
        example = HostApplicationIntegrationExample()
        
        # Setup the integration
        example.setup()
        
        # Run all examples
        results = example.run_all_examples()
        
        # Print final summary
        print("\n🎯 Host Application Integration Example Complete!")
        print("This example demonstrated:")
        print("  ✓ Host service registration with AgentMap's DI container")
        print("  ✓ Protocol-based service injection into agents")
        print("  ✓ Multi-service coordination and operations")
        print("  ✓ Error handling and graceful degradation")
        print("  ✓ Service status monitoring and debugging")
        print()
        print("Next steps for your host application:")
        print("  1. Define your own service protocols in a protocols.py file")
        print("  2. Implement your services following the example patterns")
        print("  3. Create agents that implement your protocols")
        print("  4. Configure AgentMap with your host application settings")
        print("  5. Register your services with the ApplicationContainer")
        print("  6. Use AgentMap's graph execution with your enhanced agents")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️ Example interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
