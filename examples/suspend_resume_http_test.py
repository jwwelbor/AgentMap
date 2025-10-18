#!/usr/bin/env python3
"""
AgentMap Suspend/Resume HTTP Test Script

This script tests the suspend/resume functionality of AgentMap via HTTP API calls.
It demonstrates the full workflow: execution -> suspension -> resumption.

Usage:
    python suspend_resume_http_test.py [--config agentmap_local_config.yaml]

Requirements:
    - AgentMap server running on http://127.0.0.1:8000
    - Authentication enabled with valid API keys
    - A workflow with human-interaction or suspend agents

Author: AgentMap Testing
Date: October 2025
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests
    import yaml
except ImportError:
    print("ERROR: Required libraries not installed")
    print("Install with: pip install requests pyyaml")
    sys.exit(1)


class Colors:
    """ANSI color codes for console output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class SuspendResumeHTTPTester:
    """HTTP-based tester for AgentMap suspend/resume functionality."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        config_file: str = "agentmap_local_config.yaml"
    ):
        self.base_url = base_url
        self.config_file = config_file
        self.api_key = None
        self.session = requests.Session()

    def load_config(self) -> bool:
        """Load configuration and extract API key."""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                print(f"{Colors.RED}❌ Config file not found: {config_path}{Colors.END}")
                return False

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Extract API key (prefer executor key for execution permissions)
            auth_config = config.get('authentication', {})
            api_keys = auth_config.get('api_keys', {})

            # Try to get executor key first, then admin
            if 'executor' in api_keys:
                self.api_key = api_keys['executor']['key']
                key_name = "executor"
            elif 'admin' in api_keys:
                self.api_key = api_keys['admin']['key']
                key_name = "admin"
            else:
                print(f"{Colors.RED}❌ No suitable API key found in config{Colors.END}")
                return False

            print(f"{Colors.GREEN}✅ Loaded config from {config_path}{Colors.END}")
            print(f"{Colors.CYAN}🔑 Using '{key_name}' API key{Colors.END}")
            return True

        except Exception as e:
            print(f"{Colors.RED}❌ Error loading config: {e}{Colors.END}")
            return False

    def check_server(self) -> bool:
        """Check if server is running."""
        print(f"\n{Colors.BOLD}🔌 Checking Server Connectivity{Colors.END}")
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✅ Server is running at {self.base_url}{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}❌ Server returned status {response.status_code}{Colors.END}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"{Colors.RED}❌ Cannot connect to {self.base_url}{Colors.END}")
            print(f"{Colors.YELLOW}💡 Make sure AgentMap server is running{Colors.END}")
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ Connection error: {e}{Colors.END}")
            return False

    def list_workflows(self) -> Optional[list]:
        """List available workflows."""
        print(f"\n{Colors.BOLD}📋 Listing Available Workflows{Colors.END}")
        try:
            headers = {"X-API-Key": self.api_key}
            response = self.session.get(
                f"{self.base_url}/workflows",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                workflows = data.get("workflows", [])
                print(f"{Colors.GREEN}✅ Found {len(workflows)} workflow(s){Colors.END}")

                for wf in workflows[:5]:  # Show first 5
                    print(f"   • {wf['name']} ({wf['graph_count']} graphs)")

                return workflows
            else:
                print(f"{Colors.YELLOW}⚠️  Could not list workflows: {response.status_code}{Colors.END}")
                return None

        except Exception as e:
            print(f"{Colors.RED}❌ Error listing workflows: {e}{Colors.END}")
            return None

    def execute_workflow(
        self,
        workflow: str,
        graph: str,
        state: Dict[str, Any],
        auth_method: str = "x-api-key"
    ) -> Optional[Dict]:
        """
        Execute a workflow and return the result.

        Args:
            workflow: Workflow name
            graph: Graph name
            state: Initial state
            auth_method: "x-api-key" or "bearer"

        Returns:
            Response data or None if failed
        """
        print(f"\n{Colors.BOLD}▶️  Executing Workflow{Colors.END}")
        print(f"{Colors.CYAN}Workflow: {workflow}{Colors.END}")
        print(f"{Colors.CYAN}Graph: {graph}{Colors.END}")
        print(f"{Colors.CYAN}Auth Method: {auth_method}{Colors.END}")

        try:
            # Set authentication header
            if auth_method == "bearer":
                headers = {"Authorization": f"Bearer {self.api_key}"}
            else:
                headers = {"X-API-Key": self.api_key}

            headers["Content-Type"] = "application/json"

            # Prepare request
            url = f"{self.base_url}/execute/{workflow}/{graph}"
            payload = {
                "inputs": state,
                "force_create": False,
                "execution_id": f"suspend_test_{int(time.time())}"
            }

            print(f"{Colors.CYAN}Request URL: {url}{Colors.END}")
            print(f"{Colors.CYAN}Request State: {json.dumps(state, indent=2)}{Colors.END}")

            # Execute
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            print(f"{Colors.CYAN}Response Status: {response.status_code}{Colors.END}")

            if response.status_code == 200:
                result = response.json()

                # Check execution status
                status = result.get("status")
                success = result.get("success")

                if status == "suspended":
                    thread_id = result.get("thread_id")
                    print(f"{Colors.YELLOW}⏸️  Workflow SUSPENDED{Colors.END}")
                    print(f"{Colors.CYAN}Thread ID: {thread_id}{Colors.END}")
                    print(f"{Colors.CYAN}Message: {result.get('message')}{Colors.END}")

                    # Display interruption details
                    interrupt_info = result.get("interrupt_info", {})
                    if interrupt_info:
                        if "reason" in interrupt_info:
                            print(f"{Colors.CYAN}Reason: {interrupt_info['reason']}{Colors.END}")
                        if "prompt" in interrupt_info:
                            print(f"{Colors.CYAN}Prompt: {interrupt_info['prompt']}{Colors.END}")

                    return result
                elif status == "completed" and success:
                    print(f"{Colors.GREEN}✅ Workflow completed successfully{Colors.END}")
                    return result
                else:
                    error = result.get("error", "Unknown error")
                    print(f"{Colors.RED}❌ Execution failed: {error}{Colors.END}")
                    return None
            else:
                print(f"{Colors.RED}❌ Request failed with status {response.status_code}{Colors.END}")
                print(f"{Colors.RED}Response: {response.text[:500]}{Colors.END}")
                return None

        except Exception as e:
            print(f"{Colors.RED}❌ Execution error: {e}{Colors.END}")
            return None

    def resume_workflow(
        self,
        thread_id: str,
        response_action: str,
        response_data: Optional[Dict[str, Any]] = None,
        auth_method: str = "x-api-key"
    ) -> Optional[Dict]:
        """
        Resume a suspended workflow.

        Args:
            thread_id: Thread ID from suspended workflow
            response_action: Action to take (approve, reject, respond, etc.)
            response_data: Additional data for the response
            auth_method: "x-api-key" or "bearer"

        Returns:
            Response data or None if failed
        """
        print(f"\n{Colors.BOLD}🔄 Resuming Workflow{Colors.END}")
        print(f"{Colors.CYAN}Thread ID: {thread_id}{Colors.END}")
        print(f"{Colors.CYAN}Response Action: {response_action}{Colors.END}")
        print(f"{Colors.CYAN}Auth Method: {auth_method}{Colors.END}")

        try:
            # Set authentication header
            if auth_method == "bearer":
                headers = {"Authorization": f"Bearer {self.api_key}"}
            else:
                headers = {"X-API-Key": self.api_key}

            headers["Content-Type"] = "application/json"

            # Prepare request
            url = f"{self.base_url}/resume/{thread_id}"
            payload = {
                "action": response_action,
                "data": response_data or {}
            }

            print(f"{Colors.CYAN}Request URL: {url}{Colors.END}")
            print(f"{Colors.CYAN}Request Payload: {json.dumps(payload, indent=2)}{Colors.END}")

            # Resume
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            print(f"{Colors.CYAN}Response Status: {response.status_code}{Colors.END}")

            if response.status_code == 200:
                result = response.json()

                if result.get("success"):
                    print(f"{Colors.GREEN}✅ Workflow resumed successfully{Colors.END}")
                    print(f"{Colors.CYAN}Message: {result.get('message')}{Colors.END}")
                    return result
                else:
                    error = result.get("error", "Unknown error")
                    print(f"{Colors.RED}❌ Resume failed: {error}{Colors.END}")
                    return None
            else:
                print(f"{Colors.RED}❌ Request failed with status {response.status_code}{Colors.END}")
                print(f"{Colors.RED}Response: {response.text[:500]}{Colors.END}")
                return None

        except Exception as e:
            print(f"{Colors.RED}❌ Resume error: {e}{Colors.END}")
            return None

    def test_suspend_resume_cycle(
        self,
        workflow: str,
        graph: str,
        initial_state: Dict[str, Any],
        response_action: str = "approve",
        response_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Test a complete suspend/resume cycle.

        Args:
            workflow: Workflow name
            graph: Graph name
            initial_state: Initial state for workflow
            response_action: Action for resumption
            response_data: Data for resumption

        Returns:
            True if test passed, False otherwise
        """
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}Testing Suspend/Resume Cycle{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

        # Test with both authentication methods
        auth_methods = ["x-api-key", "bearer"]

        for auth_method in auth_methods:
            print(f"\n{Colors.BOLD}🔐 Testing with {auth_method.upper()} authentication{Colors.END}")

            # Step 1: Execute workflow (should suspend)
            exec_result = self.execute_workflow(
                workflow=workflow,
                graph=graph,
                state=initial_state,
                auth_method=auth_method
            )

            if not exec_result:
                print(f"{Colors.RED}❌ Execution failed with {auth_method}{Colors.END}")
                continue

            # Check if workflow was suspended
            status = exec_result.get("status")
            if status != "suspended":
                print(f"{Colors.YELLOW}⚠️  Workflow did not suspend (status: {status}){Colors.END}")
                print(f"{Colors.YELLOW}   This might be expected if the workflow doesn't have suspend agents{Colors.END}")
                continue

            thread_id = exec_result.get("thread_id")
            if not thread_id:
                print(f"{Colors.RED}❌ No thread_id in suspended workflow{Colors.END}")
                continue

            # Step 2: Resume workflow
            print(f"\n{Colors.CYAN}Waiting 2 seconds before resuming...{Colors.END}")
            time.sleep(2)

            resume_result = self.resume_workflow(
                thread_id=thread_id,
                response_action=response_action,
                response_data=response_data,
                auth_method=auth_method
            )

            if resume_result and resume_result.get("success"):
                print(f"{Colors.GREEN}✅ Suspend/Resume cycle successful with {auth_method}!{Colors.END}")
            else:
                print(f"{Colors.RED}❌ Resume failed with {auth_method}{Colors.END}")

        return True

    def run_interactive_test(self):
        """Run an interactive test where user can specify workflow details."""
        print(f"\n{Colors.BOLD}{Colors.PURPLE}🎯 Interactive Suspend/Resume Test{Colors.END}")

        # List workflows
        workflows = self.list_workflows()

        if not workflows:
            print(f"\n{Colors.YELLOW}No workflows found or unable to list them.{Colors.END}")
            print(f"{Colors.YELLOW}You can still test with a known workflow name.{Colors.END}")

        # Get workflow name
        print(f"\n{Colors.BOLD}Enter workflow details:{Colors.END}")
        workflow_name = input(f"{Colors.CYAN}Workflow name (e.g., 'HelloWorld'): {Colors.END}").strip()

        if not workflow_name:
            print(f"{Colors.RED}❌ Workflow name is required{Colors.END}")
            return False

        # Get graph name
        graph_name = input(f"{Colors.CYAN}Graph name (or press Enter for default): {Colors.END}").strip()

        # Get initial state
        print(f"{Colors.CYAN}Initial state (JSON, or press Enter for empty state): {Colors.END}")
        state_input = input().strip()

        if state_input:
            try:
                initial_state = json.loads(state_input)
            except json.JSONDecodeError:
                print(f"{Colors.YELLOW}⚠️  Invalid JSON, using empty state{Colors.END}")
                initial_state = {}
        else:
            initial_state = {"test": "suspend_resume", "timestamp": time.time()}

        # Get response action
        response_action = input(
            f"{Colors.CYAN}Response action for resume (default 'approve'): {Colors.END}"
        ).strip() or "approve"

        # Run test
        return self.test_suspend_resume_cycle(
            workflow=workflow_name,
            graph=graph_name if graph_name else None,
            initial_state=initial_state,
            response_action=response_action
        )

    def run_predefined_test(self):
        """Run a test with predefined workflow (if available)."""
        print(f"\n{Colors.BOLD}{Colors.PURPLE}🎯 Running Predefined Test{Colors.END}")

        # Try common workflow names that might have suspend functionality
        test_workflows = [
            ("HelloWorld", None, {"message": "test suspend/resume"}),
            ("hello_world", None, {"input": "test"}),
        ]

        for workflow, graph, state in test_workflows:
            print(f"\n{Colors.CYAN}Attempting to test with workflow: {workflow}{Colors.END}")

            result = self.execute_workflow(
                workflow=workflow,
                graph=graph or workflow,
                state=state,
                auth_method="x-api-key"
            )

            if result:
                status = result.get("status")
                if status == "suspended":
                    # Found a workflow that suspends!
                    thread_id = result.get("thread_id")
                    print(f"\n{Colors.GREEN}✅ Found workflow that suspends!{Colors.END}")

                    time.sleep(2)

                    self.resume_workflow(
                        thread_id=thread_id,
                        response_action="approve",
                        auth_method="x-api-key"
                    )
                    return True

        print(f"\n{Colors.YELLOW}⚠️  No predefined workflows suspended{Colors.END}")
        print(f"{Colors.YELLOW}   Try the interactive test to specify a workflow with suspend agents{Colors.END}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test AgentMap suspend/resume functionality via HTTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python suspend_resume_http_test.py

  # Run with custom config
  python suspend_resume_http_test.py --config my_config.yaml

  # Interactive mode
  python suspend_resume_http_test.py --interactive

  # Custom server URL
  python suspend_resume_http_test.py --url http://localhost:8000
        """
    )

    parser.add_argument(
        "--config",
        default="agentmap_local_config.yaml",
        help="Path to AgentMap config file"
    )

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="AgentMap server URL"
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )

    args = parser.parse_args()

    # Create tester
    tester = SuspendResumeHTTPTester(
        base_url=args.url,
        config_file=args.config
    )

    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}AgentMap Suspend/Resume HTTP Test{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}Server: {args.url}{Colors.END}")
    print(f"{Colors.CYAN}Config: {args.config}{Colors.END}")

    # Load config
    if not tester.load_config():
        sys.exit(1)

    # Check server
    if not tester.check_server():
        sys.exit(1)

    # Run test
    try:
        if args.interactive:
            success = tester.run_interactive_test()
        else:
            success = tester.run_predefined_test()

        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        if success:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 Suspend/Resume Test Completed!{Colors.END}")
            sys.exit(0)
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Test completed with warnings{Colors.END}")
            print(f"{Colors.YELLOW}   Run with --interactive to test a specific workflow{Colors.END}")
            sys.exit(0)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⏹️  Test interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Unexpected error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
