"""
Run Updated Resume Diagnosis
============================

Updated test runner that focuses on confirming the missing API endpoint
vs runtime API functionality.

Usage:
    python run_updated_resume_diagnosis.py

This will confirm that:
1. Runtime API works perfectly
2. REST API endpoints are missing (404s)  
3. Parameter format translation needed
4. Exact fix implementation required
"""

import sys
import os
import unittest
import time
from io import StringIO

# Add project root and source to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_path)

def run_updated_diagnosis():
    """Run the updated resume workflow diagnosis"""
    
    print("🔧 AgentMap Resume Workflow - UPDATED Diagnosis")
    print("=" * 60)
    print(f"HYPOTHESIS: Runtime API works, REST endpoint missing")
    print(f"Project root: {project_root}")
    print(f"Test execution: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Import updated test modules
    try:
        from tests.fresh_suite.test_resume_workflow_updated_diagnosis import (
            ResumeWorkflowUpdatedDiagnosisTest,
            ResumeWorkflowRootCauseTest
        )
        print("✅ Successfully imported updated test modules")
    except ImportError as e:
        print(f"❌ Failed to import test modules: {e}")
        print("Make sure AgentMap server is running and modules are accessible")
        return False
    
    # Create focused test suite
    suite = unittest.TestSuite()
    
    # Test 1: Confirm endpoints are missing (should be 404s)
    suite.addTest(ResumeWorkflowUpdatedDiagnosisTest('test_resume_endpoint_existence'))
    
    # Test 2: Confirm runtime API works directly  
    suite.addTest(ResumeWorkflowUpdatedDiagnosisTest('test_runtime_api_directly'))
    
    # Test 3: Show parameter format mismatch
    suite.addTest(ResumeWorkflowUpdatedDiagnosisTest('test_api_parameter_format_mismatch'))
    
    # Test 4: Show correct implementation 
    suite.addTest(ResumeWorkflowUpdatedDiagnosisTest('test_show_correct_api_implementation'))
    
    # Test 5: Final root cause confirmation
    suite.addTest(ResumeWorkflowRootCauseTest('test_confirm_root_cause'))
    
    # Run tests with detailed output
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        buffer=False
    )
    
    print("\n🚀 Starting Updated Resume Diagnosis...")
    print("-" * 50)
    
    result = runner.run(suite)
    
    # Print test output
    test_output = stream.getvalue()
    print(test_output)
    
    # Generate updated analysis
    print("\n📊 Updated Diagnosis Results")
    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    # Analyze results
    if len(result.errors) > 0:
        print(f"\n🚨 Test Errors ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  • {test}")
            # Show just the key error message
            error_lines = traceback.strip().split('\n')
            if error_lines:
                print(f"    → {error_lines[-1]}")
    
    if len(result.failures) > 0:
        print(f"\n❌ Test Failures ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  • {test}")
    
    # Generate specific recommendations
    print(f"\n💡 Updated Recommendations")
    print("-" * 30)
    
    if len(result.errors) == 0 and len(result.failures) == 0:
        print("✅ CONFIRMED: Runtime API works, REST endpoints missing")
        print("1. 🔨 Create /workflows/resume REST endpoint")
        print("2. 🔄 Map API parameters to runtime parameters")  
        print("3. 🧪 Test with authentication suite")
        print("4. 📝 Update API documentation")
    else:
        print("⚠️  Some tests had issues - check error details above")
        print("1. 🔍 Ensure AgentMap server is running")
        print("2. 🔑 Verify API keys are valid")
        print("3. 📦 Check all dependencies are installed")
    
    print(f"\n📄 Next Steps:")
    print("1. 📖 Review: dev-artifacts/resume-workflow-UPDATED-root-cause-analysis.md")
    print("2. 💻 Use: dev-artifacts/resume_workflow_api_implementation.py")  
    print("3. 🧪 Test: Re-run authentication test suite after implementing endpoint")
    
    return len(result.failures) == 0 and len(result.errors) == 0

def main():
    """Main execution function"""
    try:
        success = run_updated_diagnosis()
        
        if success:
            print(f"\n🎯 Diagnosis CONFIRMED!")
            print("✅ Runtime API works perfectly")
            print("❌ REST endpoints missing - this is the fix needed")
            print("💡 Implementation code provided in dev-artifacts/")
        else:
            print(f"\n🔧 Diagnosis completed with issues.")
            print("Check error details above for specific problems.")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Diagnosis interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
