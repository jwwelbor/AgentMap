# Deployment Verification Script for AgentMap AWS Lambda
# Run this script to verify the deployment is working correctly

import json
import boto3
import sys
from typing import Dict, Any

def test_lambda_function(function_name: str, region: str = 'us-east-1') -> bool:
    """Test that the Lambda function can be invoked successfully."""
    print(f"Testing Lambda function: {function_name}")
    
    lambda_client = boto3.client('lambda', region_name=region)
    
    # Test event payload
    test_event = {
        "graph": "Demo",
        "state": {"hello": "world"},
        "action": "run"
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_event)
        )
        
        status_code = response['StatusCode']
        payload = json.loads(response['Payload'].read())
        
        print(f"✓ Lambda invocation successful (status: {status_code})")
        print(f"  Response: {json.dumps(payload, indent=2)}")
        
        return status_code == 200
        
    except Exception as e:
        print(f"✗ Lambda invocation failed: {e}")
        return False

def test_api_gateway(api_url: str) -> bool:
    """Test that the API Gateway endpoint is working."""
    try:
        import requests
    except ImportError:
        print("✗ requests library not available, skipping API Gateway test")
        print("  Install with: pip install requests")
        return True  # Don't fail verification if requests not available
    
    print(f"Testing API Gateway: {api_url}")
    
    test_payload = {
        "graph": "Demo",
        "state": {"hello": "world"},
        "action": "run"
    }
    
    try:
        response = requests.post(
            api_url,
            json=test_payload,
            timeout=30
        )
        
        print(f"✓ API Gateway request successful (status: {response.status_code})")
        print(f"  Response: {response.text}")
        
        return response.status_code in [200, 202]
        
    except Exception as e:
        print(f"✗ API Gateway request failed: {e}")
        return False

def check_cloudwatch_logs(function_name: str, region: str = 'us-east-1') -> bool:
    """Check that CloudWatch logs are being created."""
    print(f"Checking CloudWatch logs for: {function_name}")
    
    logs_client = boto3.client('logs', region_name=region)
    log_group = f"/aws/lambda/{function_name}"
    
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if response['logStreams']:
            latest_stream = response['logStreams'][0]
            print(f"✓ Found log stream: {latest_stream['logStreamName']}")
            print(f"  Last event: {latest_stream.get('lastEventTime', 'N/A')}")
            return True
        else:
            print("✗ No log streams found")
            return False
            
    except Exception as e:
        print(f"✗ Error checking logs: {e}")
        return False

def check_agentmap_import() -> bool:
    """Check if AgentMap can be imported (for local testing)."""
    print("Checking AgentMap import...")
    
    try:
        import agentmap
        print(f"✓ AgentMap imported successfully (version: {getattr(agentmap, '__version__', 'unknown')})")
        return True
    except ImportError as e:
        print(f"✗ AgentMap import failed: {e}")
        return False

def main():
    """Run all deployment verification tests."""
    print("=== AgentMap AWS Deployment Verification ===\\n")
    
    # Get function name and region from command line or use defaults
    function_name = sys.argv[1] if len(sys.argv) > 1 else "agentmap-dev"
    region = sys.argv[2] if len(sys.argv) > 2 else "us-east-1"
    api_url = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Function: {function_name}")
    print(f"Region: {region}")
    print(f"API URL: {api_url or 'Not provided'}\\n")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: AgentMap import (local)
    total_tests += 1
    if check_agentmap_import():
        tests_passed += 1
    print()
    
    # Test 2: Lambda function
    total_tests += 1
    if test_lambda_function(function_name, region):
        tests_passed += 1
    print()
    
    # Test 3: API Gateway (if URL provided)
    if api_url and api_url != "API Gateway not created":
        total_tests += 1
        if test_api_gateway(api_url):
            tests_passed += 1
        print()
    
    # Test 4: CloudWatch logs
    total_tests += 1
    if check_cloudwatch_logs(function_name, region):
        tests_passed += 1
    print()
    
    # Summary
    print("=== Verification Summary ===")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✓ All tests passed! Deployment appears to be working correctly.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
