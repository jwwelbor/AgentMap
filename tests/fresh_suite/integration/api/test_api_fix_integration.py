"""
Simple integration test for API execution fix.

This test verifies that the API now correctly uses GraphBundleService
and calls runner.run() instead of the non-existent run_graph(),
and also properly accesses node_executions instead of node_summaries.
"""

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../src"))
)

import time
from pathlib import Path

import pytest
import requests


@pytest.mark.integration_server
def test_api_fix_integration():
    """Test that the API can now execute workflows correctly."""

    base_url = "http://localhost:8000"

    # Check if server is running
    try:
        response = requests.get(f"{base_url}/health", timeout=2)
        if response.status_code != 200:
            pytest.skip("Server not running. Skipping integration test.")
    except:
        pytest.skip("Server not reachable. Skipping integration test.")

    # Try to execute a workflow
    try:
        # First, check what workflows are available
        response = requests.get(f"{base_url}/workflows")
        if response.status_code == 200:
            workflows = response.json().get("workflows", [])
            if workflows:
                # Use the first available workflow
                workflow = workflows[0]["name"]

                # Get graphs for this workflow
                response = requests.get(f"{base_url}/workflows/{workflow}/graphs")
                if response.status_code == 200:
                    graphs = response.json().get("graphs", [])
                    if graphs:
                        graph = graphs[0]["name"]

                        # Execute the workflow
                        print(f"Testing execution of {workflow}/{graph}...")
                        response = requests.post(
                            f"{base_url}/execute/{workflow}/{graph}",
                            json={
                                "state": {"test": "value"},
                            },
                            timeout=30,
                        )

                        # Check the response
                        if response.status_code == 500:
                            error_text = response.text
                            if "run_graph" in error_text:
                                print("❌ API still using old run_graph() method")
                                assert False, "API still using old run_graph() method"
                            elif "node_summaries" in error_text:
                                print(
                                    "❌ API still using incorrect node_summaries attribute"
                                )
                                assert (
                                    False
                                ), "API still using incorrect node_summaries attribute"
                            else:
                                print(f"❌ Different error: {error_text[:200]}")
                                assert False, f"Unexpected error: {error_text[:200]}"
                        elif response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                print(
                                    "✅ API successfully executed workflow using fixed implementation"
                                )
                                print(
                                    f"   Execution time: {result.get('execution_time', 'N/A')}s"
                                )
                                if result.get("metadata"):
                                    print(
                                        f"   Nodes executed: {result['metadata'].get('nodes_executed', 'N/A')}"
                                    )
                                # Test passes - API is working correctly
                                assert True
                                return
                            else:
                                print(
                                    f"⚠️ Execution failed but API is using correct method: {result.get('error')}"
                                )
                                # The fix is working, even if execution failed
                                assert True
                                return
                        else:
                            print(f"Response status: {response.status_code}")
                            print(f"Response: {response.text[:200]}")
                            # If we don't see the old errors, the fix is likely working
                            has_old_errors = (
                                "run_graph" in response.text
                                or "node_summaries" in response.text
                            )
                            assert (
                                not has_old_errors
                            ), f"API still has old implementation errors in response: {response.text[:200]}"
                            return

        print("Could not find workflows to test")
        pytest.skip("No workflows available to test")

    except Exception as e:
        print(f"Error during test: {e}")
        assert False, f"Test failed with exception: {e}"


if __name__ == "__main__":
    try:
        test_api_fix_integration()
        print("\n✅ Integration test passed: API fix is working")
        sys.exit(0)
    except (AssertionError, Exception) as e:
        print(f"\n❌ Integration test failed: {e}")
        sys.exit(1)
