"""
Test fixtures and utilities for blob storage testing.

This module provides reusable test fixtures, mock factories, and utility functions
for blob storage testing across different cloud providers and scenarios.
"""

import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, Mock

from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.services.protocols import BlobStorageServiceProtocol
from agentmap.services.storage.blob_storage_service import BlobStorageService
from tests.utils.mock_service_factory import MockServiceFactory


class BlobStorageTestFixtures:
    """
    Centralized test fixtures for blob storage testing.

    Provides consistent test data, configurations, and scenarios
    across all blob storage tests.
    """

    # Standard test data
    TEST_STRING_DATA = "Hello, blob storage world! 🌍"
    TEST_JSON_DATA = {
        "message": "Test JSON data",
        "timestamp": "2024-01-01T00:00:00Z",
        "numbers": [1, 2, 3, 4, 5],
        "nested": {"key": "value", "flag": True},
        "unicode": "Testing unicode: ñáéíóú 中文 🚀",
    }
    TEST_BINARY_DATA = bytes(range(256))  # All possible byte values
    TEST_LARGE_DATA = b"x" * (1024 * 1024)  # 1MB of data
    TEST_EMPTY_DATA = b""

    # Test URIs for different providers
    AZURE_TEST_URI = "azure://testcontainer/test.blob"
    S3_TEST_URI = "s3://testbucket/test.blob"
    GCS_TEST_URI = "gs://testbucket/test.blob"
    LOCAL_TEST_URI = "/tmp/test.blob"

    # Provider configurations
    AZURE_CONFIG = {
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
    }

    S3_CONFIG = {
        "access_key": "AKIATEST",
        "secret_key": "testsecretkey",
        "region": "us-east-1",
    }

    GCS_CONFIG = {
        "credentials_path": "/path/to/service-account.json",
        "project_id": "test-project",
    }

    LOCAL_CONFIG = {"base_directory": "/tmp/blob_storage"}

    @classmethod
    def get_test_config_for_provider(cls, provider: str) -> Dict[str, Any]:
        """Get test configuration for specific provider."""
        configs = {
            "azure": cls.AZURE_CONFIG,
            "s3": cls.S3_CONFIG,
            "gs": cls.GCS_CONFIG,
            "file": cls.LOCAL_CONFIG,
            "local": cls.LOCAL_CONFIG,
        }
        return configs.get(provider, {})

    @classmethod
    def get_test_uri_for_provider(
        cls, provider: str, filename: str = "test.blob"
    ) -> str:
        """Get test URI for specific provider."""
        uri_patterns = {
            "azure": f"azure://testcontainer/{filename}",
            "s3": f"s3://testbucket/{filename}",
            "gs": f"gs://testbucket/{filename}",
            "file": f"/tmp/{filename}",
            "local": f"/tmp/{filename}",
        }
        return uri_patterns.get(provider, f"/tmp/{filename}")

    @classmethod
    def get_all_provider_configs(cls) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all providers."""
        return {
            "azure": cls.AZURE_CONFIG,
            "s3": cls.S3_CONFIG,
            "gs": cls.GCS_CONFIG,
            "file": cls.LOCAL_CONFIG,
            "local": cls.LOCAL_CONFIG,
        }


class MockBlobStorageServiceFactory:
    """
    Factory for creating mock blob storage services with realistic behavior.

    Creates mock services that simulate different cloud provider behaviors
    and error conditions for comprehensive testing.
    """

    @staticmethod
    def create_successful_service() -> Mock:
        """Create a mock service that always succeeds."""
        mock_service = Mock(spec=BlobStorageServiceProtocol)

        # Storage for written data
        _storage = {}

        # Mock successful read operations
        def mock_read_blob(uri: str) -> bytes:
            if "nonexistent" in uri:
                raise FileNotFoundError(f"Blob not found: {uri}")
            # Return stored data if available, otherwise return default string data
            return _storage.get(
                uri, BlobStorageTestFixtures.TEST_STRING_DATA.encode("utf-8")
            )

        mock_service.read_blob.side_effect = mock_read_blob

        # Mock successful write operations
        def mock_write_blob(
            uri: str, data: Union[str, bytes, Dict[str, Any]]
        ) -> Dict[str, Any]:
            # Convert data to bytes and store it
            if isinstance(data, str):
                stored_data = data.encode("utf-8")
            elif isinstance(data, (dict, list)):
                import json

                stored_data = json.dumps(data).encode("utf-8")
            elif isinstance(data, bytes):
                stored_data = data
            else:
                stored_data = str(data).encode("utf-8")

            _storage[uri] = stored_data

            return {
                "success": True,
                "uri": uri,
                "size": len(stored_data),
                "provider": "mock",
            }

        mock_service.write_blob.side_effect = mock_write_blob

        # Mock other operations
        mock_service.blob_exists.return_value = True
        mock_service.list_blobs.return_value = [
            "mock://container/blob1",
            "mock://container/blob2",
        ]
        mock_service.delete_blob.return_value = {"success": True}
        mock_service.get_available_providers.return_value = ["azure", "s3", "file"]
        mock_service.health_check.return_value = {"healthy": True, "providers": {}}

        return mock_service

    @staticmethod
    def create_failing_service() -> Mock:
        """Create a mock service that always fails."""
        mock_service = Mock(spec=BlobStorageServiceProtocol)

        # Mock all operations to fail
        from agentmap.exceptions import StorageOperationError

        mock_service.read_blob.side_effect = StorageOperationError("Mock read failure")
        mock_service.write_blob.side_effect = StorageOperationError(
            "Mock write failure"
        )
        mock_service.blob_exists.side_effect = StorageOperationError(
            "Mock exists check failure"
        )
        mock_service.list_blobs.side_effect = StorageOperationError("Mock list failure")
        mock_service.delete_blob.side_effect = StorageOperationError(
            "Mock delete failure"
        )
        mock_service.get_available_providers.return_value = []
        mock_service.health_check.return_value = {"healthy": False, "providers": {}}

        return mock_service

    @staticmethod
    def create_intermittent_service(failure_rate: float = 0.5) -> Mock:
        """Create a mock service that fails intermittently."""
        mock_service = Mock(spec=BlobStorageServiceProtocol)

        from agentmap.exceptions import StorageOperationError

        # Use a deterministic pattern for more predictable failure rates
        # For a 0.3 failure rate with 20 operations, we want exactly 6 failures
        call_count = {"count": 0}

        # Create a pattern that gives the exact failure rate
        # For 0.3 rate: fail on calls 3, 7, 10, 13, 17, 20 (6 out of 20 = 0.3)
        if failure_rate == 0.3:
            failure_calls = {3, 7, 10, 13, 17, 20}
        elif failure_rate == 0.5:
            failure_calls = {2, 4, 6, 8, 10, 12, 14, 16, 18, 20}  # 10 out of 20
        else:
            # Generic pattern for other rates
            total_calls = 20  # Assume 20 operations in test
            expected_failures = int(total_calls * failure_rate)
            failure_calls = set(
                range(1, total_calls + 1, total_calls // expected_failures)[
                    :expected_failures
                ]
            )

        def maybe_fail_read(uri: str) -> bytes:
            call_count["count"] += 1
            if call_count["count"] in failure_calls:
                raise StorageOperationError("Intermittent read failure")
            return BlobStorageTestFixtures.TEST_STRING_DATA.encode("utf-8")

        def maybe_fail_write(
            uri: str, data: Union[str, bytes, Dict[str, Any]]
        ) -> Dict[str, Any]:
            call_count["count"] += 1
            if call_count["count"] in failure_calls:
                raise StorageOperationError("Intermittent write failure")
            # Handle different data types like in create_successful_service
            if isinstance(data, (str, bytes, dict, list)):
                data_len = len(str(data))
            else:
                data_len = len(str(data))
            return {"success": True, "uri": uri, "size": data_len}

        mock_service.read_blob.side_effect = maybe_fail_read
        mock_service.write_blob.side_effect = maybe_fail_write
        mock_service.blob_exists.return_value = True
        mock_service.get_available_providers.return_value = ["mock"]

        return mock_service

    @staticmethod
    def create_slow_service(delay: float = 1.0) -> Mock:
        """Create a mock service that simulates slow operations."""
        mock_service = Mock(spec=BlobStorageServiceProtocol)

        import time

        def slow_read(uri: str) -> bytes:
            time.sleep(delay)
            return BlobStorageTestFixtures.TEST_STRING_DATA.encode("utf-8")

        def slow_write(uri: str, data: bytes) -> Dict[str, Any]:
            time.sleep(delay)
            return {"success": True, "uri": uri, "size": len(data)}

        mock_service.read_blob.side_effect = slow_read
        mock_service.write_blob.side_effect = slow_write
        mock_service.blob_exists.return_value = True
        mock_service.get_available_providers.return_value = ["mock"]

        return mock_service


class CloudProviderScenarios:
    """
    Scenarios for testing different cloud provider behaviors.

    Provides standardized test scenarios that can be used across
    different cloud providers to ensure consistent behavior.
    """

    @staticmethod
    def get_provider_availability_scenarios() -> List[Dict[str, Any]]:
        """Get scenarios for testing provider availability."""
        return [
            {
                "name": "all_providers_available",
                "azure_available": True,
                "s3_available": True,
                "gcs_available": True,
                "expected_providers": ["azure", "s3", "gs", "file", "local"],
            },
            {
                "name": "only_azure_available",
                "azure_available": True,
                "s3_available": False,
                "gcs_available": False,
                "expected_providers": ["azure", "file", "local"],
            },
            {
                "name": "only_local_available",
                "azure_available": False,
                "s3_available": False,
                "gcs_available": False,
                "expected_providers": ["file", "local"],
            },
            {
                "name": "mixed_availability",
                "azure_available": True,
                "s3_available": False,
                "gcs_available": True,
                "expected_providers": ["azure", "gs", "file", "local"],
            },
        ]

    @staticmethod
    def get_error_scenarios() -> List[Dict[str, Any]]:
        """Get scenarios for testing error handling."""
        return [
            {
                "name": "file_not_found",
                "error_type": FileNotFoundError,
                "error_message": "Blob not found",
                "operation": "read",
                "expected_behavior": "re_raise",
            },
            {
                "name": "storage_operation_error",
                "error_type": "StorageOperationError",
                "error_message": "Storage operation failed",
                "operation": "write",
                "expected_behavior": "re_raise",
            },
            {
                "name": "connection_error",
                "error_type": "StorageConnectionError",
                "error_message": "Connection failed",
                "operation": "read",
                "expected_behavior": "re_raise",
            },
            {
                "name": "permission_error",
                "error_type": PermissionError,
                "error_message": "Permission denied",
                "operation": "write",
                "expected_behavior": "re_raise",
            },
        ]

    @staticmethod
    def get_performance_scenarios() -> List[Dict[str, Any]]:
        """Get scenarios for testing performance characteristics."""
        return [
            {
                "name": "small_data",
                "data_size": 100,  # 100 bytes
                "expected_max_time": 1.0,
            },
            {
                "name": "medium_data",
                "data_size": 10 * 1024,  # 10KB
                "expected_max_time": 2.0,
            },
            {
                "name": "large_data",
                "data_size": 1024 * 1024,  # 1MB
                "expected_max_time": 10.0,
            },
        ]


class BlobStorageTestEnvironment:
    """
    Test environment manager for blob storage tests.

    Provides consistent test environment setup and teardown,
    including temporary directories, configurations, and cleanup.
    """

    def __init__(self):
        self.temp_dir = None
        self.config_path = None
        self.blob_data_path = None

    def __enter__(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix="blob_test_")
        self.blob_data_path = Path(self.temp_dir) / "blob_data"
        self.blob_data_path.mkdir(exist_ok=True)

        self.config_path = self._create_test_config()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up test environment."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_config(self) -> Path:
        """Create comprehensive test configuration."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"

        # Use forward slashes for YAML to avoid Windows backslash escaping
        storage_config_path_str = str(storage_config_path).replace("\\", "/")
        blob_data_path_str = str(self.blob_data_path).replace("\\", "/")

        config_content = f"""logging:
  version: 1
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

storage:
  blob:
    providers:
      azure:
        connection_string: "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
      s3:
        access_key: "AKIATEST"
        secret_key: "testsecretkey"
        region: "us-east-1"
      gs:
        credentials_path: "/path/to/credentials.json"
        project_id: "test-project"
      file:
        base_directory: "{blob_data_path_str}"
      local:
        base_directory: "{blob_data_path_str}"

storage_config_path: "{storage_config_path_str}"
"""

        # Use forward slashes for all paths to avoid Windows YAML escaping issues
        csv_data_path_str = f"{self.temp_dir}/csv_data".replace("\\", "/")

        storage_config_content = f"""csv:
  default_directory: "{csv_data_path_str}"
  collections: {{}}

vector:
  default_provider: "chroma"
  collections: {{}}

kv:
  default_provider: "local"
  collections: {{}}

blob:
  default_provider: "file"
  providers:
    azure:
      connection_string: "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
    s3:
      access_key: "AKIATEST"
      secret_key: "testsecretkey"
      region: "us-east-1"
    gs:
      credentials_path: "/path/to/credentials.json"
      project_id: "test-project" 
    file:
      base_directory: "{blob_data_path_str}"
    local:
      base_directory: "{blob_data_path_str}"
"""

        with open(config_path, "w") as f:
            f.write(config_content)

        with open(storage_config_path, "w") as f:
            f.write(storage_config_content)

        return config_path

    def get_test_blob_path(self, filename: str) -> Path:
        """Get path for test blob file."""
        return self.blob_data_path / filename

    def create_test_blob(self, filename: str, data: Union[str, bytes]) -> Path:
        """Create a test blob file with specified data."""
        blob_path = self.get_test_blob_path(filename)

        if isinstance(data, str):
            data = data.encode("utf-8")

        with open(blob_path, "wb") as f:
            f.write(data)

        return blob_path

    def get_blob_uri(self, filename: str, provider: str = "file") -> str:
        """Get blob URI for specified provider and filename."""
        if provider in ["file", "local"]:
            return str(self.get_test_blob_path(filename))
        else:
            return BlobStorageTestFixtures.get_test_uri_for_provider(provider, filename)


@contextmanager
def blob_storage_test_environment():
    """Context manager for blob storage test environment."""
    with BlobStorageTestEnvironment() as env:
        yield env


class BlobAgentTestHelpers:
    """
    Helper functions for testing blob storage agents.

    Provides utilities for creating agents with various configurations
    and testing their behavior under different conditions.
    """

    @staticmethod
    def create_test_blob_reader(
        name: str = "test_reader", blob_service: Optional[Mock] = None, **kwargs
    ) -> BlobReaderAgent:
        """Create a blob reader agent for testing."""
        # Default services
        if "logger" not in kwargs:
            kwargs["logger"] = Mock()
        if "execution_tracking_service" not in kwargs:
            kwargs["execution_tracking_service"] = (
                MockServiceFactory.create_mock_execution_tracking_service()
            )
        if "state_adapter_service" not in kwargs:
            kwargs["state_adapter_service"] = (
                MockServiceFactory.create_mock_state_adapter_service()
            )

        agent = BlobReaderAgent(name=name, prompt="Test blob reader", **kwargs)

        if blob_service:
            agent.configure_blob_storage_service(blob_service)

        return agent

    @staticmethod
    def create_test_blob_writer(
        name: str = "test_writer", blob_service: Optional[Mock] = None, **kwargs
    ) -> BlobWriterAgent:
        """Create a blob writer agent for testing."""
        # Default services
        if "logger" not in kwargs:
            kwargs["logger"] = Mock()
        if "execution_tracking_service" not in kwargs:
            kwargs["execution_tracking_service"] = (
                MockServiceFactory.create_mock_execution_tracking_service()
            )
        if "state_adapter_service" not in kwargs:
            kwargs["state_adapter_service"] = (
                MockServiceFactory.create_mock_state_adapter_service()
            )

        agent = BlobWriterAgent(name=name, prompt="Test blob writer", **kwargs)

        if blob_service:
            agent.configure_blob_storage_service(blob_service)

        return agent

    @staticmethod
    def test_agent_workflow(
        writer: BlobWriterAgent,
        reader: BlobReaderAgent,
        test_data: Union[str, bytes, Dict[str, Any]],
        test_uri: str,
    ) -> bool:
        """Test complete write-read workflow with agents."""
        try:
            # Write data
            write_inputs = {"blob_uri": test_uri, "data": test_data}
            write_result = writer.process(write_inputs)

            # Read data back
            read_inputs = {"blob_uri": test_uri}
            read_result = reader.process(read_inputs)

            # Verify data integrity
            if isinstance(test_data, str):
                return read_result.decode("utf-8") == test_data
            elif isinstance(test_data, bytes):
                return read_result == test_data
            elif isinstance(test_data, (dict, list)):
                parsed_data = json.loads(read_result.decode("utf-8"))
                return parsed_data == test_data
            else:
                # For other types, convert to string and compare
                return read_result.decode("utf-8") == str(test_data)

        except Exception:
            return False


class PerformanceTestHelpers:
    """
    Helper functions for performance testing of blob storage.

    Provides utilities for measuring and validating performance
    characteristics of blob storage operations.
    """

    @staticmethod
    def measure_operation_time(operation_func, *args, **kwargs) -> float:
        """Measure the time taken by an operation."""
        import time

        start_time = time.time()
        try:
            operation_func(*args, **kwargs)
            return time.time() - start_time
        except Exception:
            return time.time() - start_time  # Return time even if operation failed

    @staticmethod
    def generate_test_data(size_bytes: int) -> bytes:
        """Generate test data of specified size."""
        if size_bytes == 0:
            return b""
        elif size_bytes <= 1024:
            # For small data, use random bytes
            import random

            return bytes(random.randint(0, 255) for _ in range(size_bytes))
        else:
            # For large data, use repeating pattern for efficiency
            pattern = b"0123456789ABCDEF"
            repeats = size_bytes // len(pattern)
            remainder = size_bytes % len(pattern)
            return pattern * repeats + pattern[:remainder]

    @staticmethod
    def validate_performance(
        operation_time: float,
        data_size: int,
        max_time: float,
        operation_name: str = "operation",
    ) -> bool:
        """Validate that operation performance meets expectations."""
        if operation_time > max_time:
            print(
                f"WARNING: {operation_name} took {operation_time:.2f}s for {data_size} bytes "
                f"(max: {max_time:.2f}s)"
            )
            return False
        return True

    @staticmethod
    def calculate_throughput(data_size: int, operation_time: float) -> float:
        """Calculate throughput in bytes per second."""
        if operation_time > 0:
            return data_size / operation_time
        return 0.0


class MockCloudProviderHelpers:
    """
    Helper functions for mocking cloud provider behavior.

    Provides utilities for simulating different cloud provider
    responses and error conditions.
    """

    @staticmethod
    def mock_azure_behavior(mock_service: Mock, scenario: str = "success"):
        """Configure mock service to behave like Azure Blob Storage."""
        from agentmap.exceptions import StorageConnectionError, StorageOperationError

        if scenario == "success":
            mock_service.read_blob.return_value = (
                BlobStorageTestFixtures.TEST_STRING_DATA.encode()
            )
            mock_service.write_blob.return_value = {
                "success": True,
                "etag": "mock-etag",
            }
            mock_service.blob_exists.return_value = True
        elif scenario == "not_found":
            # Use standard Python exceptions, not Azure SDK exceptions
            mock_service.read_blob.side_effect = FileNotFoundError("Blob not found")
            mock_service.blob_exists.return_value = False
        elif scenario == "auth_error":
            mock_service.read_blob.side_effect = StorageConnectionError(
                "Authentication failed"
            )

    @staticmethod
    def mock_s3_behavior(mock_service: Mock, scenario: str = "success"):
        """Configure mock service to behave like AWS S3."""
        if scenario == "success":
            mock_service.read_blob.return_value = (
                BlobStorageTestFixtures.TEST_STRING_DATA.encode()
            )
            mock_service.write_blob.return_value = {
                "success": True,
                "version_id": "mock-version",
            }
            mock_service.blob_exists.return_value = True
        elif scenario == "not_found":
            mock_service.read_blob.side_effect = FileNotFoundError("Object not found")
            mock_service.blob_exists.return_value = False
        elif scenario == "access_denied":
            from agentmap.exceptions import StorageOperationError

            mock_service.read_blob.side_effect = StorageOperationError("Access denied")

    @staticmethod
    def mock_gcs_behavior(mock_service: Mock, scenario: str = "success"):
        """Configure mock service to behave like Google Cloud Storage."""
        if scenario == "success":
            mock_service.read_blob.return_value = (
                BlobStorageTestFixtures.TEST_STRING_DATA.encode()
            )
            mock_service.write_blob.return_value = {
                "success": True,
                "generation": "mock-generation",
            }
            mock_service.blob_exists.return_value = True
        elif scenario == "not_found":
            mock_service.read_blob.side_effect = FileNotFoundError("Object not found")
            mock_service.blob_exists.return_value = False
        elif scenario == "quota_exceeded":
            from agentmap.exceptions import StorageOperationError

            mock_service.write_blob.side_effect = StorageOperationError(
                "Quota exceeded"
            )


class BlobStorageTestRunner:
    """
    Test runner for executing standardized blob storage test suites.

    Provides methods for running comprehensive test suites across
    different providers and scenarios.
    """

    def __init__(self, test_environment: BlobStorageTestEnvironment):
        self.env = test_environment
        self.results = []

    def run_provider_compatibility_tests(self, providers: List[str]) -> Dict[str, bool]:
        """Run compatibility tests across multiple providers."""
        results = {}

        for provider in providers:
            try:
                # Test basic operations
                test_uri = self.env.get_blob_uri(
                    f"compat_test_{provider}.blob", provider
                )
                test_data = BlobStorageTestFixtures.TEST_STRING_DATA

                # Create mock service for provider
                mock_service = MockBlobStorageServiceFactory.create_successful_service()

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test workflow
                success = BlobAgentTestHelpers.test_agent_workflow(
                    writer, reader, test_data, test_uri
                )

                results[provider] = success

            except Exception as e:
                results[provider] = False
                print(f"Provider {provider} compatibility test failed: {e}")

        return results

    def run_error_resilience_tests(
        self, error_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """Run error resilience tests for various failure scenarios."""
        results = {}

        for scenario in error_scenarios:
            try:
                scenario_name = scenario["name"]

                # Create failing service
                mock_service = MockBlobStorageServiceFactory.create_failing_service()

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                # Test that errors are properly handled
                test_uri = self.env.get_blob_uri(f"error_test_{scenario_name}.blob")

                # Should raise appropriate exceptions
                error_caught = False
                try:
                    reader.process({"blob_uri": test_uri})
                except Exception:
                    error_caught = True

                results[scenario_name] = error_caught

            except Exception as e:
                results[scenario_name] = False
                print(f"Error scenario {scenario['name']} test failed: {e}")

        return results

    def run_performance_tests(
        self, performance_scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """Run performance tests for various data sizes."""
        results = {}

        for scenario in performance_scenarios:
            try:
                scenario_name = scenario["name"]
                data_size = scenario["data_size"]

                # Generate test data
                test_data = PerformanceTestHelpers.generate_test_data(data_size)

                # Create fast mock service
                mock_service = MockBlobStorageServiceFactory.create_successful_service()

                # Create agents
                writer = BlobAgentTestHelpers.create_test_blob_writer(
                    blob_service=mock_service
                )
                reader = BlobAgentTestHelpers.create_test_blob_reader(
                    blob_service=mock_service
                )

                test_uri = self.env.get_blob_uri(f"perf_test_{scenario_name}.blob")

                # Measure write performance
                write_time = PerformanceTestHelpers.measure_operation_time(
                    writer.process, {"blob_uri": test_uri, "data": test_data}
                )

                # Measure read performance
                read_time = PerformanceTestHelpers.measure_operation_time(
                    reader.process, {"blob_uri": test_uri}
                )

                # Calculate throughput
                write_throughput = PerformanceTestHelpers.calculate_throughput(
                    data_size, write_time
                )
                read_throughput = PerformanceTestHelpers.calculate_throughput(
                    data_size, read_time
                )

                results[scenario_name] = {
                    "write_time": write_time,
                    "read_time": read_time,
                    "write_throughput": write_throughput,
                    "read_throughput": read_throughput,
                    "data_size": data_size,
                }

            except Exception as e:
                results[scenario_name] = {"error": str(e)}
                print(f"Performance scenario {scenario['name']} test failed: {e}")

        return results
