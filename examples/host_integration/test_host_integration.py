#!/usr/bin/env python3
"""
Test script for host application integration with AgentMap.

This script verifies that host services can be registered and configured
properly with AgentMap's dependency injection system.

Run this test to verify host integration:
    python examples/host_integration/test_host_integration.py
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from typing import Dict, Any

# Add AgentMap to path for this test
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# AgentMap imports
from agentmap.di.containers import ApplicationContainer
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService

# Host application imports
from host_services import (
    DatabaseService, EmailService, NotificationService,
    create_database_service, create_email_service, create_notification_service
)
from host_protocols import (
    DatabaseServiceProtocol, EmailServiceProtocol, NotificationServiceProtocol
)
from custom_agents import DatabaseAgent, EmailAgent, NotificationAgent, MultiServiceAgent


class HostIntegrationTester:
    """
    Test class for verifying host application integration.
    
    This class performs comprehensive testing of:
    - Service registration
    - Protocol configuration
    - Agent functionality with host services
    - Error handling and graceful degradation
    """
    
    def __init__(self):
        """Initialize the tester with temporary resources."""
        self.temp_dir = None
        self.container = None
        self.test_results = {}
        
    def setup(self) -> None:
        """Set up test environment with temporary resources."""
        print("🔧 Setting up test environment...")
        
        # Create temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp(prefix="agentmap_host_test_"))
        print(f"   Test directory: {self.temp_dir}")
        
        # Create minimal test configuration
        test_config = {
            "logging": {"level": "INFO"},
            "host_application": {
                "enabled": True,
                "services": {
                    "database_service": {
                        "enabled": True,
                        "configuration": {"database_path": str(self.temp_dir / "test.db")}
                    },
                    "email_service": {
                        "enabled": True,
                        "configuration": {"demo_mode": True}
                    },
                    "notification_service": {
                        "enabled": True,
                        "configuration": {"default_channels": ["console"]}
                    }
                }
            }
        }
        
        # Write test configuration
        import yaml
        config_path = self.temp_dir / "test_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Create container with test configuration
        self.container = ApplicationContainer()
        self.container.config.path.from_value(str(config_path))
        
        print("✅ Test environment setup complete")
    
    def test_service_registration(self) -> bool:
        """Test that host services can be registered with the container."""
        print("\n📝 Testing service registration...")
        
        try:
            # Register database service
            self.container.register_host_factory(
                service_name="test_database_service",
                factory_function=create_database_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[DatabaseServiceProtocol],
                metadata={"description": "Test database service", "version": "1.0"}
            )
            
            # Register email service
            self.container.register_host_factory(
                service_name="test_email_service",
                factory_function=create_email_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[EmailServiceProtocol],
                metadata={"description": "Test email service", "version": "1.0"}
            )
            
            # Register notification service
            self.container.register_host_factory(
                service_name="test_notification_service",
                factory_function=create_notification_service,
                dependencies=["app_config_service", "logging_service"],
                protocols=[NotificationServiceProtocol],
                metadata={"description": "Test notification service", "version": "1.0"}
            )
            
            # Verify services are registered
            host_services = self.container.get_host_services()
            expected_services = ["test_database_service", "test_email_service", "test_notification_service"]
            
            for service_name in expected_services:
                if service_name not in host_services:
                    raise AssertionError(f"Service {service_name} not registered")
                print(f"   ✅ {service_name} registered")
            
            # Verify protocol implementations
            protocol_implementations = self.container.get_protocol_implementations()
            expected_protocols = ["DatabaseServiceProtocol", "EmailServiceProtocol", "NotificationServiceProtocol"]
            
            for protocol_name in expected_protocols:
                if protocol_name not in protocol_implementations:
                    raise AssertionError(f"Protocol {protocol_name} not implemented")
                print(f"   ✅ {protocol_name} implemented")
            
            print("✅ Service registration test passed")
            return True
            
        except Exception as e:
            print(f"❌ Service registration test failed: {e}")
            return False
    
    def test_service_instantiation(self) -> bool:
        """Test that registered services can be instantiated correctly."""
        print("\n🏗️ Testing service instantiation...")
        
        try:
            # Test database service
            db_service = self.container.get_host_service_instance("test_database_service")
            if not db_service or not isinstance(db_service, DatabaseService):
                raise AssertionError("Database service instantiation failed")
            print("   ✅ Database service instantiated")
            
            # Test email service
            email_service = self.container.get_host_service_instance("test_email_service")
            if not email_service or not isinstance(email_service, EmailService):
                raise AssertionError("Email service instantiation failed")
            print("   ✅ Email service instantiated")
            
            # Test notification service
            notification_service = self.container.get_host_service_instance("test_notification_service")
            if not notification_service or not isinstance(notification_service, NotificationService):
                raise AssertionError("Notification service instantiation failed")
            print("   ✅ Notification service instantiated")
            
            print("✅ Service instantiation test passed")
            return True
            
        except Exception as e:
            print(f"❌ Service instantiation test failed: {e}")
            return False
    
    def test_agent_configuration(self) -> bool:
        """Test that agents can be configured with host services."""
        print("\n⚙️ Testing agent configuration...")
        
        try:
            logging_service = self.container.logging_service()
            logger = logging_service.get_logger("test")
            
            # Test database agent configuration
            db_agent = DatabaseAgent("test_db_agent", logger=logger)
            configured_count = self.container.configure_host_protocols(db_agent)
            
            if configured_count == 0:
                raise AssertionError("Database agent configuration failed")
            if not db_agent.database_service:
                raise AssertionError("Database service not configured on agent")
            print(f"   ✅ Database agent configured ({configured_count} services)")
            
            # Test email agent configuration
            email_agent = EmailAgent("test_email_agent", logger=logger)
            configured_count = self.container.configure_host_protocols(email_agent)
            
            if configured_count == 0:
                raise AssertionError("Email agent configuration failed")
            if not email_agent.email_service:
                raise AssertionError("Email service not configured on agent")
            print(f"   ✅ Email agent configured ({configured_count} services)")
            
            # Test notification agent configuration
            notification_agent = NotificationAgent("test_notification_agent", logger=logger)
            configured_count = self.container.configure_host_protocols(notification_agent)
            
            if configured_count == 0:
                raise AssertionError("Notification agent configuration failed")
            if not notification_agent.notification_service:
                raise AssertionError("Notification service not configured on agent")
            print(f"   ✅ Notification agent configured ({configured_count} services)")
            
            # Test multi-service agent configuration
            multi_agent = MultiServiceAgent("test_multi_agent", logger=logger)
            configured_count = self.container.configure_host_protocols(multi_agent)
            
            if configured_count < 3:  # Should have all 3 services
                raise AssertionError(f"Multi-service agent only configured {configured_count}/3 services")
            print(f"   ✅ Multi-service agent configured ({configured_count} services)")
            
            print("✅ Agent configuration test passed")
            return True
            
        except Exception as e:
            print(f"❌ Agent configuration test failed: {e}")
            return False
    
    def test_agent_functionality(self) -> bool:
        """Test that agents work correctly with host services."""
        print("\n🚀 Testing agent functionality...")
        
        try:
            logging_service = self.container.logging_service()
            logger = logging_service.get_logger("test")
            
            # Test database agent functionality
            db_agent = DatabaseAgent("test_db_agent", logger=logger)
            self.container.configure_host_protocols(db_agent)
            
            # Test getting users
            result = db_agent.run({"operation": "get_users"})
            if result.get("status") != "success":
                raise AssertionError(f"Database agent failed: {result.get('error')}")
            
            users = result.get("database_result", {}).get("users", [])
            if len(users) == 0:
                raise AssertionError("No users returned from database")
            print(f"   ✅ Database agent returned {len(users)} users")
            
            # Test email agent functionality
            email_agent = EmailAgent("test_email_agent", logger=logger)
            self.container.configure_host_protocols(email_agent)
            
            result = email_agent.run({
                "operation": "send_notification",
                "to_email": "test@example.com",
                "operation_name": "Test Operation",
                "operation_result": "Success"
            })
            if result.get("status") != "success":
                raise AssertionError(f"Email agent failed: {result.get('error')}")
            print("   ✅ Email agent sent notification")
            
            # Test notification agent functionality
            notification_agent = NotificationAgent("test_notification_agent", logger=logger)
            self.container.configure_host_protocols(notification_agent)
            
            result = notification_agent.run({
                "operation": "send_notification",
                "channel": "console",
                "message": "Test notification"
            })
            if result.get("status") != "success":
                raise AssertionError(f"Notification agent failed: {result.get('error')}")
            print("   ✅ Notification agent sent notification")
            
            # Test multi-service agent functionality
            multi_agent = MultiServiceAgent("test_multi_agent", logger=logger)
            self.container.configure_host_protocols(multi_agent)
            
            result = multi_agent.run({
                "operation": "process_user_request",
                "user_id": 1
            })
            if result.get("status") != "success":
                raise AssertionError(f"Multi-service agent failed: {result.get('error')}")
            
            multi_result = result.get("multi_service_result", {})
            if not multi_result.get("user"):
                raise AssertionError("Multi-service agent did not process user")
            print(f"   ✅ Multi-service agent processed user: {multi_result['user']['name']}")
            
            print("✅ Agent functionality test passed")
            return True
            
        except Exception as e:
            print(f"❌ Agent functionality test failed: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling and graceful degradation."""
        print("\n🛡️ Testing error handling...")
        
        try:
            logging_service = self.container.logging_service()
            logger = logging_service.get_logger("test")
            
            # Test agent with no services configured
            db_agent = DatabaseAgent("unconfigured_agent", logger=logger)
            # Don't configure services
            
            result = db_agent.run({"operation": "get_users"})
            if result.get("status") != "error":
                raise AssertionError("Agent should have failed without services")
            print("   ✅ Agent properly handles missing services")
            
            # Test invalid operation
            db_agent_configured = DatabaseAgent("configured_agent", logger=logger)
            self.container.configure_host_protocols(db_agent_configured)
            
            result = db_agent_configured.run({"operation": "invalid_operation"})
            if result.get("status") != "error":
                raise AssertionError("Agent should have failed with invalid operation")
            print("   ✅ Agent properly handles invalid operations")
            
            # Test service registration conflicts
            try:
                # Try to register a service with same name as AgentMap service
                self.container.register_host_service(
                    service_name="logging_service",  # This should conflict
                    service_class_path="host_services.DatabaseService",
                    protocols=[DatabaseServiceProtocol]
                )
                raise AssertionError("Should not allow conflicting service names")
            except ValueError as e:
                if "conflicts with existing AgentMap service" in str(e):
                    print("   ✅ Service name conflicts properly detected")
                else:
                    raise
            
            print("✅ Error handling test passed")
            return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results."""
        tests = [
            ("service_registration", self.test_service_registration),
            ("service_instantiation", self.test_service_instantiation),
            ("agent_configuration", self.test_agent_configuration),
            ("agent_functionality", self.test_agent_functionality),
            ("error_handling", self.test_error_handling)
        ]
        
        results = {}
        
        print("🧪 Running Host Integration Tests")
        print("=" * 50)
        
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"❌ Test '{test_name}' crashed: {e}")
                results[test_name] = False
        
        return results
    
    def cleanup(self) -> None:
        """Clean up test resources."""
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
            print(f"\n🧹 Cleaned up test directory: {self.temp_dir}")


def main():
    """Main function to run host integration tests."""
    tester = None
    
    try:
        print("🚀 AgentMap Host Integration Test Suite")
        print("=" * 60)
        
        # Setup
        tester = HostIntegrationTester()
        tester.setup()
        
        # Run tests
        results = tester.run_all_tests()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("-" * 30)
        
        passed = 0
        total = len(results)
        
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {test_name:<20} {status}")
            if success:
                passed += 1
        
        print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Host integration is working correctly.")
            return 0
        else:
            print("⚠️ Some tests failed. Please check the output above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if tester:
            tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())
