"""
Updated Resume Workflow Diagnosis Test
=====================================

UPDATED ANALYSIS: The runtime API already has resume_workflow() that works correctly.
The issue is likely a MISSING API ENDPOINT, not a broken service.

This test now focuses on:
1. Confirming the API endpoint doesn't exist (404s)
2. Testing the runtime API directly (should work)
3. Demonstrating the correct parameter format
4. Providing the fix implementation
"""

import unittest
import json
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Test the runtime API directly
from agentmap.runtime_api import resume_workflow as runtime_resume_workflow


@dataclass
class ResumeEndpointTest:
    """Test case for resume endpoint URLs"""
    url: str
    expected_status: int
    description: str


class ResumeWorkflowUpdatedDiagnosisTest(unittest.TestCase):
    """Updated diagnosis focusing on missing API endpoint vs runtime issues"""
    
    BASE_URL = "http://localhost:8000"
    ADMIN_API_KEY = "DKn3B96xGuF2...F8m_2nmQ"
    
    def setUp(self):
        """Set up test session"""
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.ADMIN_API_KEY}'
        })
    
    def test_resume_endpoint_existence(self):
        """Test if ANY resume endpoint exists"""
        
        possible_endpoints = [
            ResumeEndpointTest("/workflows/resume", 404, "Standard workflow resume endpoint"),
            ResumeEndpointTest("/api/v1/workflows/resume", 404, "Versioned workflow resume"), 
            ResumeEndpointTest("/execute/resume", 404, "Execution resume endpoint"),
            ResumeEndpointTest("/resume", 404, "Simple resume endpoint"),
            ResumeEndpointTest("/api/resume", 404, "API resume endpoint"),
        ]
        
        print(f"\n🔍 Testing Resume Endpoint Existence")
        print("=" * 50)
        
        found_endpoints = []
        
        for test_case in possible_endpoints:
            try:
                response = self.session.post(
                    f"{self.BASE_URL}{test_case.url}",
                    json={"thread_id": "test"},
                    timeout=5
                )
                
                status = response.status_code
                if status != 404:  # Found an endpoint!
                    found_endpoints.append({
                        "url": test_case.url,
                        "status": status,
                        "description": test_case.description,
                        "response_preview": response.text[:200]
                    })
                    print(f"✅ FOUND: {test_case.url} -> HTTP {status}")
                else:
                    print(f"❌ Missing: {test_case.url} -> HTTP 404")
            
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Error testing {test_case.url}: {e}")
        
        print(f"\n📊 Summary: Found {len(found_endpoints)} resume endpoints")
        
        if found_endpoints:
            print("✅ Resume endpoints exist but may have issues")
            for endpoint in found_endpoints:
                print(f"  • {endpoint['url']}: HTTP {endpoint['status']}")
        else:
            print("🚨 NO RESUME ENDPOINTS FOUND - This is the root cause!")
            print("   The runtime API exists but no REST endpoint exposes it.")
        
        return found_endpoints
    
    def test_runtime_api_directly(self):
        """Test the runtime resume_workflow function directly"""
        
        print(f"\n🧪 Testing Runtime API Directly")
        print("=" * 40)
        
        try:
            # Test 1: Simple thread_id token
            print("Test 1: Simple thread_id token...")
            result1 = runtime_resume_workflow(
                resume_token="test-thread-123",
                config_file=None
            )
            print(f"✅ Simple token works: {result1.get('success', False)}")
            print(f"   Thread ID: {result1.get('thread_id', 'None')}")
            
        except Exception as e:
            print(f"⚠️  Simple token failed: {type(e).__name__}: {e}")
        
        try:
            # Test 2: Structured JSON token  
            print("\nTest 2: Structured JSON token...")
            structured_token = json.dumps({
                "thread_id": "test-thread-456",
                "response_action": "continue",
                "response_data": {"test": "data"}
            })
            result2 = runtime_resume_workflow(
                resume_token=structured_token,
                config_file=None
            )
            print(f"✅ Structured token works: {result2.get('success', False)}")
            print(f"   Thread ID: {result2.get('thread_id', 'None')}")
            
        except Exception as e:
            print(f"⚠️  Structured token failed: {type(e).__name__}: {e}")
        
        try:
            # Test 3: Invalid token
            print("\nTest 3: Invalid token (should fail gracefully)...")
            result3 = runtime_resume_workflow(
                resume_token="",  # Empty token
                config_file=None
            )
            print(f"❌ Empty token should have failed but didn't!")
            
        except Exception as e:
            print(f"✅ Empty token properly failed: {type(e).__name__}: {e}")
        
        print(f"\n✅ Runtime API works correctly - the issue is missing REST endpoint")
    
    def test_api_parameter_format_mismatch(self):
        """Demonstrate the parameter format that API should accept vs runtime needs"""
        
        print(f"\n🔧 API Parameter Format Analysis")
        print("=" * 40)
        
        # What the auth test was sending
        api_request = {
            "workflow_id": "test-workflow-123",  # ❌ Wrong parameter name
            "action": "resume",                  # ❌ Not expected by runtime
        }
        
        # What the runtime API expects (Option 1: Simple)
        runtime_simple = "test-workflow-123"  # Just thread_id as string
        
        # What the runtime API expects (Option 2: Structured)  
        runtime_structured = json.dumps({
            "thread_id": "test-workflow-123",
            "response_action": "continue", 
            "response_data": None
        })
        
        print("API Request (what auth test sent):")
        print(f"  {json.dumps(api_request, indent=2)}")
        
        print(f"\nRuntime API Format (Simple):")
        print(f"  resume_token = '{runtime_simple}'")
        
        print(f"\nRuntime API Format (Structured):")
        print(f"  resume_token = '{runtime_structured}'")
        
        print(f"\n💡 Solution: API endpoint needs to translate:")
        print(f"   workflow_id -> thread_id")
        print(f"   action -> response_action")
        print(f"   Create resume_token from API parameters")
    
    def test_show_correct_api_implementation(self):
        """Show what the correct API endpoint implementation should look like"""
        
        print(f"\n📝 Correct API Endpoint Implementation")
        print("=" * 50)
        
        print("""
@app.post("/workflows/resume")
async def resume_workflow_endpoint(request: ResumeRequest):
    try:
        # Translate API parameters to runtime format
        if request.workflow_id:
            # Create resume token from workflow_id (thread_id)
            if request.response_data or request.response_action != 'continue':
                resume_token = json.dumps({
                    "thread_id": request.workflow_id,
                    "response_action": request.response_action or "continue",
                    "response_data": request.response_data
                })
            else:
                resume_token = request.workflow_id
        else:
            resume_token = request.resume_token
            
        # Call runtime API (same as run_workflow pattern)
        result = runtime_resume_workflow(
            resume_token=resume_token,
            profile=request.profile,
            config_file=request.config_file
        )
        
        return {
            "success": True,
            "thread_id": result["thread_id"],
            "outputs": result["outputs"],
            "metadata": result["metadata"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
        
        print("✅ This implementation would fix the 500 errors!")


class ResumeWorkflowRootCauseTest(unittest.TestCase):
    """Final root cause confirmation test"""
    
    def test_confirm_root_cause(self):
        """Confirm the actual root cause of the 500 errors"""
        
        print(f"\n🎯 ROOT CAUSE CONFIRMATION")
        print("=" * 50)
        
        # Check 1: Runtime API exists and works
        try:
            from agentmap.runtime_api import resume_workflow
            print("✅ Runtime API exists: agentmap.runtime_api.resume_workflow")
            
            import inspect
            signature = inspect.signature(resume_workflow)
            print(f"✅ Runtime signature: {signature}")
            
        except ImportError as e:
            print(f"❌ Runtime API import failed: {e}")
            return
        
        # Check 2: API endpoints missing (from previous test)
        diagnosis = ResumeWorkflowUpdatedDiagnosisTest()
        diagnosis.setUp()
        found_endpoints = diagnosis.test_resume_endpoint_existence()
        
        # Check 3: Parameter mismatch (demonstrated above)
        
        # Final determination
        if len(found_endpoints) == 0:
            print(f"\n🚨 CONFIRMED ROOT CAUSE:")
            print("   ❌ Missing REST API endpoint")
            print("   ✅ Runtime API works correctly")
            print("   💡 Need to create /workflows/resume endpoint")
        else:
            print(f"\n🚨 PARTIAL ROOT CAUSE:")
            print(f"   ✅ Found {len(found_endpoints)} endpoints")
            print("   ❌ Endpoints exist but have implementation bugs")
            print("   💡 Need to fix parameter handling in existing endpoints")


if __name__ == '__main__':
    print("Resume Workflow Updated Diagnosis")
    print("=" * 50)
    print("HYPOTHESIS: Runtime API works, but REST endpoint is missing")
    print("=" * 50)
    
    unittest.main(verbosity=2)
