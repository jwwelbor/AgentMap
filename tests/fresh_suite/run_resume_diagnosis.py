"""
Resume Workflow Diagnosis Test Runner
====================================

Quick runner script to execute the resume workflow diagnosis test
and capture detailed output for debugging.

Usage:
    python run_resume_diagnosis.py

This will:
1. Run the focused resume workflow tests
2. Capture detailed error information
3. Generate a diagnostic report
4. Help identify the root cause of HTTP 500 errors
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

def run_resume_diagnosis():
    """Run the resume workflow diagnosis tests with detailed output"""
    
    print("🔧 AgentMap Resume Workflow Diagnosis")
    print("=" * 50)
    print(f"Project root: {project_root}")
    print(f"Test execution time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Import the test after adding project root to path
    try:
        from tests.fresh_suite.test_resume_workflow_diagnosis import (
            ResumeWorkflowDiagnosisTest, 
            ResumeWorkflowServiceTest
        )
        print("✅ Successfully imported test modules")
    except ImportError as e:
        print(f"❌ Failed to import test modules: {e}")
        print("Make sure you're running this from the project root directory")
        return False
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add API endpoint tests (main issue)
    suite.addTest(ResumeWorkflowDiagnosisTest('test_resume_endpoint_accessibility'))
    suite.addTest(ResumeWorkflowDiagnosisTest('test_resume_workflow_error_patterns'))
    suite.addTest(ResumeWorkflowDiagnosisTest('test_resume_with_different_auth_methods'))
    suite.addTest(ResumeWorkflowDiagnosisTest('test_server_logs_during_resume_attempt'))
    
    # Add service layer tests (to isolate business logic)
    suite.addTest(ResumeWorkflowServiceTest('test_workflow_service_resume_method_exists'))
    suite.addTest(ResumeWorkflowServiceTest('test_workflow_service_resume_with_invalid_id'))
    
    # Run tests with detailed output
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        buffer=False  # Show print statements immediately
    )
    
    print("\n🚀 Starting Resume Workflow Diagnosis Tests...")
    print("-" * 50)
    
    result = runner.run(suite)
    
    # Print test output
    test_output = stream.getvalue()
    print(test_output)
    
    # Generate summary report
    print("\n📊 Diagnosis Summary")
    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    # Detailed failure analysis
    if result.failures:
        print(f"\n❌ Test Failures ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  • {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
    
    if result.errors:
        print(f"\n🚨 Test Errors ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  • {test}: {traceback.split('\n')[-2]}")
    
    # Generate recommendations
    print(f"\n💡 Diagnostic Recommendations")
    print("-" * 30)
    
    if len(result.errors) > 0:
        print("1. 🔍 Check server logs for any errors that occurred during test execution")
        print("2. 🔌 Verify AgentMap server is running at http://localhost:8000")
        print("3. 🔑 Confirm API keys are valid and permissions are correctly configured")
    
    if len(result.failures) > 0:
        print("1. 🐛 HTTP 500 errors confirmed - check server implementation")
        print("2. 📝 Review server logs for stack traces during test execution")
        print("3. 🔧 Focus on WorkflowService.resume_workflow method implementation")
    
    if len(result.failures) == 0 and len(result.errors) == 0:
        print("1. ✅ No issues detected - problem may be intermittent")
        print("2. 🔄 Try running authentication test suite again to reproduce")
        print("3. 📊 Check server performance during high load")
    
    print(f"\n📁 For more details, check:")
    print(f"   • Test file: tests/fresh_suite/test_resume_workflow_diagnosis.py") 
    print(f"   • Authentication analysis: dev-artifacts/authentication-analysis-2025-09-17.md")
    
    return len(result.failures) == 0 and len(result.errors) == 0

def main():
    """Main execution function"""
    try:
        success = run_resume_diagnosis()
        
        if success:
            print(f"\n🎉 Diagnosis completed successfully!")
            print("All tests passed - the resume workflow issue may be resolved or intermittent.")
        else:
            print(f"\n🔧 Diagnosis completed with issues identified.")
            print("Use the output above to debug the resume workflow problems.")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Test execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
