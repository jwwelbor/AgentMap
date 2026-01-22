"""
Unit tests for RuntimeManager class.

Tests thread-safety, idempotent initialization behavior, reset functionality
for test isolation, and error handling scenarios. Ensures proper test fixtures
use RuntimeManager.reset() for test isolation.
"""

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager


class TestRuntimeManager(unittest.TestCase):
    """Test RuntimeManager class functionality."""

    def setUp(self):
        """Set up test environment - reset RuntimeManager before each test."""
        RuntimeManager.reset()

    def tearDown(self):
        """Clean up test environment - reset RuntimeManager after each test."""
        RuntimeManager.reset()

    def test_initial_state(self):
        """Test RuntimeManager initial state before initialization."""
        self.assertFalse(RuntimeManager.is_initialized())

        with self.assertRaises(AgentMapNotInitialized) as context:
            RuntimeManager.get_container()

        self.assertIn("Runtime not initialized", str(context.exception))

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_basic_initialization(self, mock_initialize_di):
        """Test basic RuntimeManager initialization without config file."""
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container

        # Initial state
        self.assertFalse(RuntimeManager.is_initialized())

        # Initialize
        RuntimeManager.initialize()

        # Verify state
        self.assertTrue(RuntimeManager.is_initialized())
        container = RuntimeManager.get_container()
        self.assertEqual(container, mock_container)

        # Verify initialize_di was called correctly
        mock_initialize_di.assert_called_once_with(None)

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_initialization_with_config_file(self, mock_initialize_di):
        """Test RuntimeManager initialization with custom config file."""
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        config_file = "/path/to/config.yaml"

        RuntimeManager.initialize(config_file=config_file)

        self.assertTrue(RuntimeManager.is_initialized())
        container = RuntimeManager.get_container()
        self.assertEqual(container, mock_container)

        # Verify initialize_di was called with config file
        mock_initialize_di.assert_called_once_with(config_file)

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_idempotent_behavior(self, mock_initialize_di):
        """Test that multiple initialize calls don't fail or reinitialize."""
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container

        # First initialization
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())
        first_container = RuntimeManager.get_container()

        # Second initialization (should be idempotent)
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())
        second_container = RuntimeManager.get_container()

        # Should be the same container instance
        self.assertEqual(first_container, second_container)

        # initialize_di should only be called once
        mock_initialize_di.assert_called_once()

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_initialization_with_refresh(self, mock_initialize_di):
        """Test initialization with refresh=True forces reinitialization."""
        mock_container1 = MagicMock(name="container1")
        mock_container2 = MagicMock(name="container2")
        mock_initialize_di.side_effect = [mock_container1, mock_container2]

        # First initialization
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())
        first_container = RuntimeManager.get_container()
        self.assertEqual(first_container, mock_container1)

        # Second initialization with refresh=True
        RuntimeManager.initialize(refresh=True)
        self.assertTrue(RuntimeManager.is_initialized())
        second_container = RuntimeManager.get_container()
        self.assertEqual(second_container, mock_container2)

        # initialize_di should be called twice
        self.assertEqual(mock_initialize_di.call_count, 2)

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_initialization_failure(self, mock_initialize_di):
        """Test error handling when initialize_di fails."""
        mock_initialize_di.side_effect = Exception("DI initialization failed")

        # Initialization should raise AgentMapNotInitialized
        with self.assertRaises(AgentMapNotInitialized) as context:
            RuntimeManager.initialize()

        self.assertIn("Initialization failed", str(context.exception))
        self.assertIn("DI initialization failed", str(context.exception))

        # State should remain uninitialized
        self.assertFalse(RuntimeManager.is_initialized())

        with self.assertRaises(AgentMapNotInitialized):
            RuntimeManager.get_container()

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_initialization_failure_with_refresh(self, mock_initialize_di):
        """Test error handling when refresh initialization fails."""
        mock_container = MagicMock()
        mock_initialize_di.side_effect = [mock_container, Exception("Refresh failed")]

        # First successful initialization
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())

        # Second initialization with refresh=True that fails
        with self.assertRaises(AgentMapNotInitialized) as context:
            RuntimeManager.initialize(refresh=True)

        self.assertIn("Initialization failed", str(context.exception))
        self.assertIn("Refresh failed", str(context.exception))

        # State should be reset to uninitialized
        self.assertFalse(RuntimeManager.is_initialized())

        with self.assertRaises(AgentMapNotInitialized):
            RuntimeManager.get_container()

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_reset_functionality(self, mock_initialize_di):
        """Test reset() clears state and allows reinitialization."""
        mock_container1 = MagicMock(name="container1")
        mock_container2 = MagicMock(name="container2")
        mock_initialize_di.side_effect = [mock_container1, mock_container2]

        # Initialize
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())
        first_container = RuntimeManager.get_container()

        # Reset
        RuntimeManager.reset()
        self.assertFalse(RuntimeManager.is_initialized())

        with self.assertRaises(AgentMapNotInitialized):
            RuntimeManager.get_container()

        # Initialize again
        RuntimeManager.initialize()
        self.assertTrue(RuntimeManager.is_initialized())
        second_container = RuntimeManager.get_container()

        # Should get a new container
        self.assertEqual(second_container, mock_container2)
        self.assertNotEqual(first_container, second_container)

    @patch("agentmap.runtime.runtime_manager.initialize_di")
    def test_get_container_when_uninitialized(self, mock_initialize_di):
        """Test get_container() raises appropriate exception when uninitialized."""
        with self.assertRaises(AgentMapNotInitialized) as context:
            RuntimeManager.get_container()

        error_message = str(context.exception)
        self.assertIn("Runtime not initialized", error_message)
        self.assertIn("Call RuntimeManager.initialize() first", error_message)

    def test_thread_safety_concurrent_initialization(self):
        """Test thread-safety with concurrent initialization attempts."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container = MagicMock()
            mock_initialize_di.return_value = mock_container

            num_threads = 10
            results = []
            exceptions = []

            def initialize_worker():
                try:
                    RuntimeManager.initialize()
                    container = RuntimeManager.get_container()
                    results.append(container)
                    return True
                except Exception as e:
                    exceptions.append(e)
                    return False

            # Run concurrent initializations
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(initialize_worker) for _ in range(num_threads)
                ]

                # Wait for all threads to complete
                for future in as_completed(futures):
                    future.result()

            # Verify results
            self.assertEqual(len(exceptions), 0, f"Unexpected exceptions: {exceptions}")
            self.assertEqual(len(results), num_threads)

            # All threads should get the same container instance
            for container in results:
                self.assertEqual(container, mock_container)

            # initialize_di should only be called once despite concurrent calls
            mock_initialize_di.assert_called_once()
            self.assertTrue(RuntimeManager.is_initialized())

    def test_thread_safety_concurrent_access_after_init(self):
        """Test thread-safety with concurrent access to initialized RuntimeManager."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container = MagicMock()
            mock_initialize_di.return_value = mock_container

            # Initialize first
            RuntimeManager.initialize()

            num_threads = 10
            results = []
            exceptions = []

            def access_worker():
                try:
                    # Mix of is_initialized() and get_container() calls
                    if RuntimeManager.is_initialized():
                        container = RuntimeManager.get_container()
                        results.append(container)
                    return True
                except Exception as e:
                    exceptions.append(e)
                    return False

            # Run concurrent access
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(access_worker) for _ in range(num_threads)]

                # Wait for all threads to complete
                for future in as_completed(futures):
                    future.result()

            # Verify results
            self.assertEqual(len(exceptions), 0, f"Unexpected exceptions: {exceptions}")
            self.assertEqual(len(results), num_threads)

            # All threads should get the same container instance
            for container in results:
                self.assertEqual(container, mock_container)

    def test_thread_safety_concurrent_reset(self):
        """Test thread-safety with concurrent reset operations."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container = MagicMock()
            mock_initialize_di.return_value = mock_container

            # Initialize first
            RuntimeManager.initialize()
            self.assertTrue(RuntimeManager.is_initialized())

            num_threads = 5
            results = []

            def reset_worker():
                RuntimeManager.reset()
                return RuntimeManager.is_initialized()

            # Run concurrent resets
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(reset_worker) for _ in range(num_threads)]

                # Collect results
                for future in as_completed(futures):
                    results.append(future.result())

            # After reset operations, should be uninitialized
            self.assertFalse(RuntimeManager.is_initialized())

            # All reset operations should have seen uninitialized state
            for result in results:
                self.assertFalse(result)

    def test_thread_safety_mixed_operations(self):
        """Test thread-safety with mixed initialize/reset/access operations."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container = MagicMock()
            mock_initialize_di.return_value = mock_container

            num_threads = 12
            init_count = 0
            reset_count = 0
            access_count = 0
            exceptions = []

            def mixed_worker(operation):
                nonlocal init_count, reset_count, access_count
                try:
                    if operation == "init":
                        RuntimeManager.initialize()
                        init_count += 1
                    elif operation == "reset":
                        RuntimeManager.reset()
                        reset_count += 1
                    elif operation == "access":
                        if RuntimeManager.is_initialized():
                            RuntimeManager.get_container()
                        access_count += 1
                    return True
                except Exception as e:
                    exceptions.append(e)
                    return False

            # Create mixed operations
            operations = ["init"] * 4 + ["reset"] * 4 + ["access"] * 4

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(mixed_worker, op) for op in operations]

                # Wait for all threads to complete
                for future in as_completed(futures):
                    future.result()

            # Should not have any exceptions from thread safety issues
            if exceptions:
                # Filter out expected AgentMapNotInitialized exceptions from access operations
                unexpected_exceptions = [
                    e for e in exceptions if not isinstance(e, AgentMapNotInitialized)
                ]
                self.assertEqual(
                    len(unexpected_exceptions),
                    0,
                    f"Unexpected exceptions: {unexpected_exceptions}",
                )

    def test_error_handling_scenarios(self):
        """Test various error handling scenarios."""
        # Test get_container when container is None but is_initialized is True
        # This should not happen in normal operation but tests robustness
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_initialize_di.return_value = MagicMock()

            RuntimeManager.initialize()

            # Manually corrupt the state (for testing edge case)
            RuntimeManager._container = None

            with self.assertRaises(AgentMapNotInitialized) as context:
                RuntimeManager.get_container()

            self.assertIn("Runtime not initialized", str(context.exception))

    def test_multiple_config_files(self):
        """Test initialization with different config files."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container1 = MagicMock(name="container1")
            mock_container2 = MagicMock(name="container2")
            mock_initialize_di.side_effect = [mock_container1, mock_container2]

            # Initialize with first config
            config_file1 = "/path/to/config1.yaml"
            RuntimeManager.initialize(config_file=config_file1)

            # Verify first initialization
            mock_initialize_di.assert_called_with(config_file1)
            self.assertEqual(RuntimeManager.get_container(), mock_container1)

            # Initialize with second config (using refresh)
            config_file2 = "/path/to/config2.yaml"
            RuntimeManager.initialize(config_file=config_file2, refresh=True)

            # Verify second initialization
            self.assertEqual(mock_initialize_di.call_count, 2)
            mock_initialize_di.assert_called_with(config_file2)
            self.assertEqual(RuntimeManager.get_container(), mock_container2)

    def test_stress_test_rapid_operations(self):
        """Stress test with rapid operations to verify thread safety."""
        with patch(
            "agentmap.runtime.runtime_manager.initialize_di"
        ) as mock_initialize_di:
            mock_container = MagicMock()
            mock_initialize_di.return_value = mock_container

            def rapid_operations():
                for _ in range(50):
                    RuntimeManager.initialize()
                    if RuntimeManager.is_initialized():
                        try:
                            RuntimeManager.get_container()
                        except AgentMapNotInitialized:
                            pass  # Expected if reset happened concurrently

                    # Occasional reset
                    if _ % 10 == 0:
                        RuntimeManager.reset()

            # Run rapid operations in multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=rapid_operations)
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Should complete without deadlocks or crashes
            # Final state may be initialized or not, depending on timing


if __name__ == "__main__":
    unittest.main()
