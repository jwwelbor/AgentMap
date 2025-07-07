---
sidebar_position: 7
title: "Lesson 6: External Services Integration"
description: Build robust workflows that integrate with external APIs, databases, and custom services using AgentMap's extensible service architecture
keywords: [external services, API integration, custom services, service registry, host protocols]
---

# Lesson 6: External Services Integration

Ready to connect your AI workflows to the real world? In this advanced lesson, you'll learn to integrate external APIs, databases, and custom services into AgentMap workflows, creating powerful systems that bridge AI capabilities with existing infrastructure.

## Learning Objectives

By the end of this lesson, you will:
- ✅ Build custom service implementations for external APIs
- ✅ Use the host protocol registry for service management
- ✅ Implement service injection patterns for flexible architectures
- ✅ Handle authentication, rate limiting, and error recovery
- ✅ Create reusable service libraries for common integrations
- ✅ Design fault-tolerant service interaction patterns

## Overview: What We're Building

We'll create a **Comprehensive External Integration System** that:
1. **Connects** to multiple external APIs (Slack, GitHub, email)
2. **Manages** authentication and rate limiting automatically
3. **Processes** data from multiple sources intelligently
4. **Handles** failures gracefully with retry logic
5. **Provides** a unified interface for service interactions

```mermaid
flowchart TD
    A[📄 Workflow Input<br/>Tasks & Data] --> B[🔍 Task Analyzer<br/>AI Processing]
    B --> C[📋 Service Router<br/>Determine Services Needed]
    
    C --> D[🌐 External Services]
    D --> E[💬 Slack Notifier<br/>Team Communication]
    D --> F[🔗 GitHub Integration<br/>Code Repository]
    D --> G[📧 Email Service<br/>Notifications]
    D --> H[💾 Database Service<br/>Data Storage]
    
    E --> I[📊 Results Aggregator<br/>Combine All Responses]
    F --> I
    G --> I
    H --> I
    
    I --> J[📋 Status Reporter<br/>Comprehensive Update]
    J --> K[💾 Audit Logger<br/>Record All Actions]
    
    style D fill:#e3f2fd
    style E fill:#fff3e0
    style F fill:#f3e5f5
    style G fill:#e8f5e8
    style H fill:#fce4ec
```

## Step 1: Download the External Integration System

Let's get all the files for our comprehensive external services integration:

import DownloadButton from '@site/src/components/DownloadButton';

### Main Workflow File
<DownloadButton 
  filename="lesson6.csv"
  content={`workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
ExternalIntegration,LoadTaskData,Load task and project data for processing,file_reader,AnalyzeRequirements,ErrorHandler,,task_data,data/project_tasks.json,"{""format"": ""json""}"
ExternalIntegration,AnalyzeRequirements,Analyze what external services are needed,llm,RouteToServices,ErrorHandler,task_data,service_requirements,"You are a system integration analyst. Analyze the task data and determine what external services should be used.

Task Data: {task_data}

Determine which services are needed based on the task requirements:

## 🔍 Service Requirements Analysis

### Task Classification
- **Type**: [Development/Communication/Deployment/Monitoring]
- **Complexity**: [Simple/Medium/Complex]
- **External Dependencies**: [List required external services]

### Required Services
For each needed service, specify:

#### 📧 Email Service
- **Needed**: [Yes/No]
- **Purpose**: [Notifications/Updates/Alerts]
- **Recipients**: [Who should be notified]

#### 💬 Slack Service  
- **Needed**: [Yes/No]
- **Purpose**: [Team updates/Alerts/Status reports]
- **Channels**: [Which channels to notify]

#### 🔗 GitHub Service
- **Needed**: [Yes/No]  
- **Purpose**: [Issue creation/PR updates/Repository actions]
- **Repositories**: [Which repos to interact with]

#### 💾 Database Service
- **Needed**: [Yes/No]
- **Purpose**: [Data storage/Retrieval/Updates]
- **Tables**: [Which data to store/retrieve]

#### 🌐 Custom API Service
- **Needed**: [Yes/No]
- **Purpose**: [Specific API interactions]
- **Endpoints**: [Which APIs to call]

### Execution Priority
1. [First service to call]
2. [Second service to call]
3. [Third service to call]

### Error Handling Strategy
- **Critical Services**: [Services that must succeed]
- **Optional Services**: [Services that can fail without stopping workflow]
- **Retry Strategy**: [Which services need retry logic]

Respond in this JSON format:
{
  ""services_needed"": [""slack"", ""github"", ""email"", ""database"", ""custom_api""],
  ""execution_order"": [""service1"", ""service2"", ""service3""],
  ""critical_services"": [""must_succeed_services""],
  ""optional_services"": [""can_fail_services""],
  ""service_configs"": {
    ""slack"": {""channels"": [""#general""], ""priority"": ""high""},
    ""github"": {""repo"": ""project/repo"", ""action"": ""create_issue""},
    ""email"": {""recipients"": [""team@company.com""], ""type"": ""notification""},
    ""database"": {""table"": ""projects"", ""operation"": ""insert""},
    ""custom_api"": {""endpoint"": ""api/endpoint"", ""method"": ""POST""}
  }
}","{""provider"": ""anthropic"", ""model"": ""claude-3-sonnet-20240229"", ""temperature"": 0.2}"
ExternalIntegration,RouteToServices,Route to appropriate external services,orchestrator,EmailNotification,ErrorHandler,"task_data,service_requirements",service_routing,,"{""nodes"": ""EmailNotification|SlackNotification|GitHubIntegration|DatabaseService|CustomAPIService""}"
ExternalIntegration,EmailNotification,Send email notifications using external email service,email_service,SlackNotification,RetryEmail,"task_data,service_requirements",email_result,,"{""service_type"": ""email"", ""retry_count"": 3, ""timeout"": 30}"
ExternalIntegration,SlackNotification,Send Slack notifications to team channels,slack_service,GitHubIntegration,RetrySlack,"task_data,service_requirements,email_result",slack_result,,"{""service_type"": ""slack"", ""retry_count"": 3, ""timeout"": 30}"
ExternalIntegration,GitHubIntegration,Interact with GitHub repositories and issues,github_service,DatabaseService,RetryGitHub,"task_data,service_requirements,email_result,slack_result",github_result,,"{""service_type"": ""github"", ""retry_count"": 3, ""timeout"": 45}"
ExternalIntegration,DatabaseService,Store and retrieve data from external database,database_service,CustomAPIService,RetryDatabase,"task_data,service_requirements,email_result,slack_result,github_result",database_result,,"{""service_type"": ""database"", ""retry_count"": 2, ""timeout"": 60}"
ExternalIntegration,CustomAPIService,Call custom external APIs for specialized functions,custom_api_service,AggregateResults,RetryCustomAPI,"task_data,service_requirements,email_result,slack_result,github_result,database_result",api_result,,"{""service_type"": ""custom_api"", ""retry_count"": 3, ""timeout"": 30}"
ExternalIntegration,AggregateResults,Combine results from all external service calls,llm,GenerateStatusReport,ErrorHandler,"email_result,slack_result,github_result,database_result,api_result,service_requirements",aggregated_results,"You are a system integration coordinator. Combine and analyze the results from all external service calls.

Service Results:
- Email: {email_result}
- Slack: {slack_result}  
- GitHub: {github_result}
- Database: {database_result}
- Custom API: {api_result}

Service Requirements: {service_requirements}

Create a comprehensive aggregation report:

## 📊 External Services Integration Report

### Execution Summary
- **Total Services Called**: [number]
- **Successful Services**: [list successful services]
- **Failed Services**: [list failed services]
- **Partial Failures**: [list services with warnings]

### Service-by-Service Results

#### 📧 Email Service
- **Status**: [Success/Failed/Partial]
- **Details**: [Summary of email service results]
- **Recipients Reached**: [number/list]

#### 💬 Slack Service
- **Status**: [Success/Failed/Partial]
- **Details**: [Summary of Slack service results]
- **Channels Updated**: [list]

#### 🔗 GitHub Service
- **Status**: [Success/Failed/Partial]
- **Details**: [Summary of GitHub service results]
- **Actions Performed**: [list]

#### 💾 Database Service
- **Status**: [Success/Failed/Partial]
- **Details**: [Summary of database service results]
- **Records Affected**: [number]

#### 🌐 Custom API Service
- **Status**: [Success/Failed/Partial]
- **Details**: [Summary of custom API service results]
- **API Responses**: [summary]

### Cross-Service Analysis
- **Data Consistency**: [Check if services received consistent data]
- **Timing Issues**: [Any sequence or timing problems]
- **Error Correlations**: [Related failures across services]

### Overall Integration Health
- **Success Rate**: [percentage]
- **Critical Services Status**: [All critical services status]
- **Recommendation**: [PROCEED/RETRY_FAILED/INVESTIGATE]

### Next Steps
- [Immediate actions needed]
- [Follow-up requirements]
- [Monitoring recommendations]","{""provider"": ""anthropic"", ""model"": ""claude-3-sonnet-20240229"", ""temperature"": 0.3}"
ExternalIntegration,GenerateStatusReport,Generate comprehensive status report for stakeholders,llm,AuditLogging,ErrorHandler,"aggregated_results,task_data",status_report,"You are creating a comprehensive status report for stakeholders about external service integration results.

Aggregated Results: {aggregated_results}
Task Data: {task_data}

Create a professional stakeholder report:

# 🌐 EXTERNAL SERVICES INTEGRATION REPORT

## Executive Summary
[High-level overview of integration success/challenges]

## 📊 Integration Performance
- **Overall Success Rate**: [percentage]
- **Services Utilized**: [number and types]
- **Processing Time**: [total time taken]
- **Data Integrity**: [confirmation of data consistency]

## 🔍 Service-Level Performance

### Communication Services
**Email & Slack Notifications**
- Status: [Success/Partial/Failed]
- Reach: [number of recipients/channels]
- Response Time: [average time]

### Development Services  
**GitHub Integration**
- Status: [Success/Partial/Failed]
- Actions: [issues created, PRs updated, etc.]
- Integration Health: [API connectivity status]

### Data Services
**Database & Custom APIs**
- Status: [Success/Partial/Failed]
- Transactions: [number of successful operations]
- Performance: [response times and throughput]

## ⚠️ Issues and Resolutions
[Any problems encountered and how they were handled]

## 📈 Quality Metrics
- **Reliability**: [service uptime and availability]
- **Performance**: [response times and throughput]
- **Accuracy**: [data integrity and consistency]

## 🎯 Business Impact
- **Team Coordination**: [How notifications improved collaboration]
- **Development Flow**: [Impact on development processes]
- **Data Availability**: [Improvement in data access and storage]

## 📋 Recommendations
1. [Operational improvements]
2. [Service optimization opportunities]  
3. [Future integration considerations]

## 🔄 Next Steps
- **Immediate**: [Actions needed within 24 hours]
- **Short-term**: [Actions needed within 1 week]
- **Long-term**: [Strategic improvements]

---
*Report generated by AgentMap External Services Integration*
*Integration completed at: [timestamp]*","{""provider"": ""anthropic"", ""model"": ""claude-3-sonnet-20240229"", ""temperature"": 0.3}"
ExternalIntegration,AuditLogging,Log all external service interactions for compliance,audit_logger,SaveResults,ErrorHandler,"status_report,aggregated_results",audit_log,,"{""log_level"": ""detailed"", ""include_sensitive"": false, ""compliance_mode"": true}"
ExternalIntegration,SaveResults,Save all results and generate final notification,file_writer,FinalNotification,ErrorHandler,status_report,save_result,data/integration_report.md,"{""mode"": ""write""}"
ExternalIntegration,FinalNotification,Final notification of integration completion,echo,End,,"save_result",notification,"🎉 **External Services Integration Complete!**

## 📋 Integration Summary
Your external services integration has been successfully completed!

✅ **Services Processed**: Multiple external integrations executed
✅ **Results Aggregated**: All service responses combined and analyzed  
✅ **Status Report**: Comprehensive report generated
✅ **Audit Trail**: Complete logging for compliance

## 📁 Deliverables
- **Integration Report**: data/integration_report.md
- **Audit Logs**: System logs for all service interactions
- **Service Health**: Current status of all external integrations

## 🔄 Post-Integration Actions
- Review service performance metrics
- Check for any failed integrations requiring attention
- Monitor external service health dashboards
- Plan for any necessary follow-up actions

**Integration ID**: {save_result}
**Timestamp**: $(date)

External services integration workflow completed successfully! 🚀",
ExternalIntegration,RetryEmail,Retry failed email service with exponential backoff,retry_service,SlackNotification,ErrorHandler,"task_data,service_requirements",email_retry_result,,"{""original_service"": ""email_service"", ""max_retries"": 3, ""backoff_strategy"": ""exponential""}"
ExternalIntegration,RetrySlack,Retry failed Slack service with circuit breaker,retry_service,GitHubIntegration,ErrorHandler,"task_data,service_requirements,email_result",slack_retry_result,,"{""original_service"": ""slack_service"", ""max_retries"": 3, ""circuit_breaker"": true}"
ExternalIntegration,RetryGitHub,Retry failed GitHub service with rate limit handling,retry_service,DatabaseService,ErrorHandler,"task_data,service_requirements,email_result,slack_result",github_retry_result,,"{""original_service"": ""github_service"", ""max_retries"": 2, ""rate_limit_aware"": true}"
ExternalIntegration,RetryDatabase,Retry failed database service with connection pooling,retry_service,CustomAPIService,ErrorHandler,"task_data,service_requirements,email_result,slack_result,github_result",database_retry_result,,"{""original_service"": ""database_service"", ""max_retries"": 2, ""connection_pooling"": true}"
ExternalIntegration,RetryCustomAPI,Retry failed custom API service with adaptive timeout,retry_service,AggregateResults,ErrorHandler,"task_data,service_requirements,email_result,slack_result,github_result,database_result",api_retry_result,,"{""original_service"": ""custom_api_service"", ""max_retries"": 3, ""adaptive_timeout"": true}"
ExternalIntegration,ErrorHandler,Handle external service integration errors,echo,End,,error,error_message,"❌ **External Service Integration Error**

Error Details: {error}

🔧 **Troubleshooting External Services**:

### Common Integration Issues
1. **Authentication Failures**
   - Check API keys and tokens
   - Verify service account permissions
   - Confirm OAuth flows are working

2. **Network Connectivity**
   - Test service endpoints directly
   - Check firewall and proxy settings
   - Verify DNS resolution

3. **Rate Limiting**
   - Check service usage limits
   - Implement proper backoff strategies
   - Consider upgrading service plans

4. **Service Dependencies**
   - Verify all required services are available
   - Check service health status
   - Confirm service version compatibility

### Recovery Actions
- Use retry mechanisms for transient failures
- Implement circuit breakers for persistent issues
- Fall back to alternative services when possible
- Log detailed error information for debugging

Please resolve the integration issue and restart the workflow.",
ExternalIntegration,End,Workflow completion,echo,,,notification,completion,✨ External services integration completed successfully!,`}
/>

### Sample Project Tasks Data
<DownloadButton 
  filename="project_tasks.json"
  content={`{
  "project": {
    "id": "PRJ-2024-001",
    "name": "Customer Portal Enhancement",
    "description": "Enhance the customer portal with new analytics dashboard and mobile responsiveness",
    "priority": "HIGH",
    "deadline": "2024-02-15",
    "team_lead": "sarah.johnson@company.com",
    "repository": "company/customer-portal",
    "slack_channel": "#customer-portal-team"
  },
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Analytics Dashboard Backend API",
      "description": "Develop REST API endpoints for analytics data aggregation and real-time metrics",
      "type": "development",
      "priority": "HIGH",
      "status": "in_progress",
      "assignee": "mike.chen@company.com",
      "estimated_hours": 24,
      "dependencies": ["database_schema_update"],
      "github_issue": 145,
      "external_services_needed": [
        {
          "service": "github",
          "purpose": "Update issue status and create PR",
          "config": {
            "repository": "company/customer-portal",
            "issue_number": 145,
            "labels": ["backend", "api", "analytics"]
          }
        },
        {
          "service": "slack",
          "purpose": "Notify team of API completion",
          "config": {
            "channel": "#customer-portal-team",
            "notification_type": "development_update"
          }
        }
      ]
    },
    {
      "id": "TASK-002", 
      "title": "Mobile Responsive Design Implementation",
      "description": "Implement responsive design patterns for mobile devices and tablets",
      "type": "frontend",
      "priority": "MEDIUM",
      "status": "pending",
      "assignee": "lisa.wong@company.com",
      "estimated_hours": 16,
      "dependencies": ["TASK-001"],
      "external_services_needed": [
        {
          "service": "email",
          "purpose": "Notify QA team when ready for mobile testing",
          "config": {
            "recipients": ["qa-team@company.com", "mobile-testing@company.com"],
            "template": "mobile_testing_ready",
            "priority": "normal"
          }
        },
        {
          "service": "database",
          "purpose": "Log responsive design test results",
          "config": {
            "table": "ui_test_results",
            "operation": "insert",
            "data_type": "mobile_responsive_tests"
          }
        }
      ]
    },
    {
      "id": "TASK-003",
      "title": "Performance Optimization",
      "description": "Optimize page load times and implement caching strategies",
      "type": "optimization",
      "priority": "MEDIUM", 
      "status": "planning",
      "assignee": "david.kim@company.com",
      "estimated_hours": 12,
      "dependencies": ["TASK-001", "TASK-002"],
      "external_services_needed": [
        {
          "service": "custom_api",
          "purpose": "Performance monitoring and metrics collection",
          "config": {
            "endpoint": "https://monitoring.company.com/api/v1/performance",
            "method": "POST",
            "authentication": "bearer_token",
            "metrics": ["page_load_time", "api_response_time", "resource_usage"]
          }
        },
        {
          "service": "slack",
          "purpose": "Alert on performance degradation",
          "config": {
            "channel": "#alerts",
            "notification_type": "performance_alert",
            "threshold_rules": {
              "page_load_time": "> 3 seconds",
              "api_response_time": "> 500ms"
            }
          }
        }
      ]
    },
    {
      "id": "TASK-004",
      "title": "Security Audit and Implementation",
      "description": "Conduct security review and implement additional security measures",
      "type": "security",
      "priority": "HIGH",
      "status": "planning",
      "assignee": "security-team@company.com", 
      "estimated_hours": 20,
      "dependencies": [],
      "external_services_needed": [
        {
          "service": "email",
          "purpose": "Security audit report distribution",
          "config": {
            "recipients": ["cto@company.com", "security-team@company.com", "compliance@company.com"],
            "template": "security_audit_report",
            "priority": "high",
            "encryption": true
          }
        },
        {
          "service": "database",
          "purpose": "Store security audit findings",
          "config": {
            "table": "security_audits",
            "operation": "insert",
            "encryption": true,
            "retention_policy": "7_years"
          }
        },
        {
          "service": "custom_api",
          "purpose": "Integration with security scanning tools",
          "config": {
            "endpoint": "https://security-tools.company.com/api/v2/scan",
            "method": "POST",
            "authentication": "api_key",
            "scan_types": ["vulnerability", "dependency", "code_quality"]
          }
        }
      ]
    }
  ],
  "integration_requirements": {
    "notification_preferences": {
      "email": {
        "enabled": true,
        "frequency": "immediate",
        "recipients": {
          "development_updates": ["dev-team@company.com"],
          "critical_alerts": ["oncall@company.com", "management@company.com"],
          "daily_summaries": ["project-managers@company.com"]
        }
      },
      "slack": {
        "enabled": true,
        "channels": {
          "#customer-portal-team": ["development_updates", "task_completion"],
          "#alerts": ["critical_issues", "performance_problems"],
          "#general": ["project_milestones"]
        }
      }
    },
    "external_apis": {
      "github": {
        "rate_limit_strategy": "exponential_backoff",
        "retry_attempts": 3,
        "timeout": 30
      },
      "monitoring": {
        "health_check_interval": 300,
        "alert_thresholds": {
          "response_time": 1000,
          "error_rate": 0.05,
          "uptime": 0.99
        }
      }
    },
    "data_storage": {
      "audit_logging": true,
      "retention_policy": "90_days",
      "encryption": "at_rest_and_in_transit",
      "backup_frequency": "daily"
    }
  }
}`}
/>

### Custom Service: Email Service
<DownloadButton 
  filename="email_service.py"
  content={`"""
Email Service Implementation

Custom service for sending emails through various providers with 
retry logic, template support, and delivery tracking.
"""

from agentmap.services.base_service import BaseService
from typing import Dict, Any, List, Optional
import smtplib
import ssl
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import time
from datetime import datetime
import logging


class EmailService(BaseService):
    """
    Comprehensive email service with multiple provider support.
    
    Features:
    - Multiple email providers (SMTP, SendGrid, AWS SES)
    - Template-based email composition
    - Retry logic with exponential backoff
    - Delivery tracking and status reporting
    - Attachment support
    - HTML and text email formats
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})
        
        self.provider = self.config.get('provider', 'smtp')
        self.retry_count = self.config.get('retry_count', 3)
        self.timeout = self.config.get('timeout', 30)
        
        # SMTP Configuration
        self.smtp_host = self.config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.smtp_username = self.config.get('smtp_username', '')
        self.smtp_password = self.config.get('smtp_password', '')
        
        # Email templates
        self.templates = self.config.get('templates', {})
        
        # Delivery tracking
        self.delivery_log = []
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"EmailService initialized with provider: {self.provider}")
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send email based on input configuration.
        
        Args:
            inputs: Email configuration including recipients, subject, content
            
        Returns:
            Dict: Email sending results with delivery status
        """
        try:
            # Extract email configuration
            email_config = self._extract_email_config(inputs)
            
            if not email_config:
                return {"error": "No valid email configuration found"}
            
            # Send emails with retry logic
            results = []
            for email in email_config:
                result = self._send_email_with_retry(email)
                results.append(result)
            
            # Aggregate results
            return self._aggregate_email_results(results)
            
        except Exception as e:
            error_msg = f"Email service failed: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "service": "email"}
    
    def _extract_email_config(self, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract email configuration from inputs."""
        emails = []
        
        # Check for direct email configuration
        if 'email_config' in inputs:
            email_data = inputs['email_config']
            if isinstance(email_data, list):
                emails.extend(email_data)
            else:
                emails.append(email_data)
        
        # Check for service requirements structure
        if 'service_requirements' in inputs:
            service_req = inputs['service_requirements']
            if isinstance(service_req, str):
                try:
                    service_req = json.loads(service_req)
                except:
                    pass
            
            if isinstance(service_req, dict):
                service_configs = service_req.get('service_configs', {})
                if 'email' in service_configs:
                    email_conf = service_configs['email']
                    emails.append({
                        'recipients': email_conf.get('recipients', []),
                        'subject': self._generate_subject(inputs),
                        'content': self._generate_content(inputs),
                        'template': email_conf.get('template', 'default'),
                        'priority': email_conf.get('priority', 'normal')
                    })
        
        # Check for task-based email extraction
        if 'task_data' in inputs:
            task_emails = self._extract_task_emails(inputs['task_data'])
            emails.extend(task_emails)
        
        return emails
    
    def _extract_task_emails(self, task_data: Any) -> List[Dict[str, Any]]:
        """Extract email configurations from task data."""
        emails = []
        
        if isinstance(task_data, str):
            try:
                task_data = json.loads(task_data)
            except:
                return emails
        
        if isinstance(task_data, dict):
            # Check project level notifications
            if 'integration_requirements' in task_data:
                integration_req = task_data['integration_requirements']
                if 'notification_preferences' in integration_req:
                    email_prefs = integration_req['notification_preferences'].get('email', {})
                    if email_prefs.get('enabled'):
                        recipients = email_prefs.get('recipients', {})
                        for notification_type, recipient_list in recipients.items():
                            emails.append({
                                'recipients': recipient_list,
                                'subject': f"Project Update: {notification_type}",
                                'content': self._generate_project_update(task_data),
                                'template': notification_type,
                                'priority': 'normal'
                            })
            
            # Check individual task emails
            if 'tasks' in task_data:
                for task in task_data['tasks']:
                    if 'external_services_needed' in task:
                        for service in task['external_services_needed']:
                            if service.get('service') == 'email':
                                config = service.get('config', {})
                                emails.append({
                                    'recipients': config.get('recipients', []),
                                    'subject': f"Task Update: {task.get('title', 'Unknown Task')}",
                                    'content': self._generate_task_update(task),
                                    'template': config.get('template', 'task_update'),
                                    'priority': config.get('priority', 'normal')
                                })
        
        return emails
    
    def _send_email_with_retry(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Send email with retry logic."""
        last_error = None
        
        for attempt in range(self.retry_count + 1):
            try:
                if attempt > 0:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying email send (attempt {attempt + 1}) after {wait_time}s")
                    time.sleep(wait_time)
                
                result = self._send_single_email(email_config)
                
                # Log successful delivery
                self.delivery_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'status': 'success',
                    'recipients': email_config.get('recipients', []),
                    'attempt': attempt + 1
                })
                
                return result
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Email send attempt {attempt + 1} failed: {last_error}")
        
        # All attempts failed
        error_result = {
            'status': 'failed',
            'error': last_error,
            'recipients': email_config.get('recipients', []),
            'attempts': self.retry_count + 1
        }
        
        self.delivery_log.append({
            'timestamp': datetime.now().isoformat(),
            'status': 'failed',
            'recipients': email_config.get('recipients', []),
            'error': last_error,
            'attempts': self.retry_count + 1
        })
        
        return error_result
    
    def _send_single_email(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single email using configured provider."""
        if self.provider == 'smtp':
            return self._send_smtp_email(email_config)
        elif self.provider == 'sendgrid':
            return self._send_sendgrid_email(email_config)
        elif self.provider == 'ses':
            return self._send_ses_email(email_config)
        else:
            raise ValueError(f"Unsupported email provider: {self.provider}")
    
    def _send_smtp_email(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using SMTP."""
        recipients = email_config.get('recipients', [])
        subject = email_config.get('subject', 'No Subject')
        content = email_config.get('content', '')
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = self.smtp_username
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        # Add content (HTML and text)
        if email_config.get('html', False):
            html_part = MIMEText(content, 'html')
            msg.attach(html_part)
        else:
            text_part = MIMEText(content, 'plain')
            msg.attach(text_part)
        
        # Send email
        context = ssl.create_default_context()
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls(context=context)
            server.login(self.smtp_username, self.smtp_password)
            
            for recipient in recipients:
                server.sendmail(self.smtp_username, recipient, msg.as_string())
        
        return {
            'status': 'success',
            'provider': 'smtp',
            'recipients': recipients,
            'message_id': f"smtp_{int(time.time())}",
            'timestamp': datetime.now().isoformat()
        }
    
    def _send_sendgrid_email(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using SendGrid API."""
        # This is a placeholder for SendGrid implementation
        # In practice, you would use the SendGrid Python library
        
        self.logger.info("SendGrid email sending (simulated)")
        
        return {
            'status': 'success',
            'provider': 'sendgrid',
            'recipients': email_config.get('recipients', []),
            'message_id': f"sendgrid_{int(time.time())}",
            'timestamp': datetime.now().isoformat()
        }
    
    def _send_ses_email(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using AWS SES."""
        # This is a placeholder for AWS SES implementation
        # In practice, you would use boto3 and AWS SES
        
        self.logger.info("AWS SES email sending (simulated)")
        
        return {
            'status': 'success',
            'provider': 'ses',
            'recipients': email_config.get('recipients', []),
            'message_id': f"ses_{int(time.time())}",
            'timestamp': datetime.now().isoformat()
        }
    
    def _aggregate_email_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple email sending results."""
        total_emails = len(results)
        successful_emails = len([r for r in results if r.get('status') == 'success'])
        failed_emails = total_emails - successful_emails
        
        all_recipients = []
        successful_recipients = []
        failed_recipients = []
        
        for result in results:
            recipients = result.get('recipients', [])
            all_recipients.extend(recipients)
            
            if result.get('status') == 'success':
                successful_recipients.extend(recipients)
            else:
                failed_recipients.extend(recipients)
        
        return {
            'service': 'email',
            'status': 'success' if failed_emails == 0 else ('partial' if successful_emails > 0 else 'failed'),
            'summary': {
                'total_emails': total_emails,
                'successful_emails': successful_emails,
                'failed_emails': failed_emails,
                'success_rate': successful_emails / total_emails if total_emails > 0 else 0
            },
            'recipients': {
                'total': len(set(all_recipients)),
                'successful': len(set(successful_recipients)),
                'failed': len(set(failed_recipients)),
                'successful_list': list(set(successful_recipients)),
                'failed_list': list(set(failed_recipients))
            },
            'detailed_results': results,
            'delivery_log': self.delivery_log,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_subject(self, inputs: Dict[str, Any]) -> str:
        """Generate email subject based on inputs."""
        if 'task_data' in inputs:
            task_data = inputs['task_data']
            if isinstance(task_data, str):
                try:
                    task_data = json.loads(task_data)
                except:
                    pass
            
            if isinstance(task_data, dict) and 'project' in task_data:
                project_name = task_data['project'].get('name', 'Unknown Project')
                return f"Project Update: {project_name}"
        
        return "AgentMap Integration Update"
    
    def _generate_content(self, inputs: Dict[str, Any]) -> str:
        """Generate email content based on inputs."""
        content_parts = []
        
        content_parts.append("# AgentMap Integration Update")
        content_parts.append("")
        content_parts.append("This is an automated update from your AgentMap workflow integration.")
        content_parts.append("")
        
        # Add task information if available
        if 'task_data' in inputs:
            task_data = inputs['task_data']
            if isinstance(task_data, str):
                try:
                    task_data = json.loads(task_data)
                except:
                    pass
            
            if isinstance(task_data, dict):
                if 'project' in task_data:
                    project = task_data['project']
                    content_parts.append(f"**Project**: {project.get('name', 'Unknown')}")
                    content_parts.append(f"**Description**: {project.get('description', 'No description')}")
                    content_parts.append(f"**Priority**: {project.get('priority', 'Normal')}")
                    content_parts.append("")
                
                if 'tasks' in task_data:
                    content_parts.append("## Task Updates")
                    for task in task_data['tasks'][:3]:  # Limit to first 3 tasks
                        content_parts.append(f"- **{task.get('title', 'Unknown Task')}**: {task.get('status', 'Unknown')}")
                    content_parts.append("")
        
        content_parts.append("For more details, please check the project dashboard.")
        content_parts.append("")
        content_parts.append("---")
        content_parts.append("*This email was sent by AgentMap External Services Integration*")
        
        return "\\n".join(content_parts)
    
    def _generate_project_update(self, task_data: Dict[str, Any]) -> str:
        """Generate project-specific update content."""
        content_parts = []
        
        project = task_data.get('project', {})
        content_parts.append(f"# Project Update: {project.get('name', 'Unknown Project')}")
        content_parts.append("")
        content_parts.append(f"**Status**: Integration services executed successfully")
        content_parts.append(f"**Priority**: {project.get('priority', 'Normal')}")
        content_parts.append(f"**Team Lead**: {project.get('team_lead', 'Unknown')}")
        content_parts.append("")
        
        # Task summary
        tasks = task_data.get('tasks', [])
        if tasks:
            content_parts.append("## Task Summary")
            for task in tasks:
                status = task.get('status', 'unknown')
                content_parts.append(f"- {task.get('title', 'Unknown')}: {status.upper()}")
            content_parts.append("")
        
        content_parts.append("External services integration completed successfully.")
        
        return "\\n".join(content_parts)
    
    def _generate_task_update(self, task: Dict[str, Any]) -> str:
        """Generate task-specific update content."""
        content_parts = []
        
        content_parts.append(f"# Task Update: {task.get('title', 'Unknown Task')}")
        content_parts.append("")
        content_parts.append(f"**Description**: {task.get('description', 'No description')}")
        content_parts.append(f"**Status**: {task.get('status', 'Unknown')}")
        content_parts.append(f"**Priority**: {task.get('priority', 'Normal')}")
        content_parts.append(f"**Assignee**: {task.get('assignee', 'Unassigned')}")
        content_parts.append("")
        
        if 'estimated_hours' in task:
            content_parts.append(f"**Estimated Hours**: {task['estimated_hours']}")
        
        if 'dependencies' in task and task['dependencies']:
            content_parts.append(f"**Dependencies**: {', '.join(task['dependencies'])}")
        
        content_parts.append("")
        content_parts.append("External services have been notified of this task update.")
        
        return "\\n".join(content_parts)


def create_email_service(config: Dict[str, Any] = None) -> EmailService:
    """Factory function to create EmailService instances."""
    return EmailService(config)


# Register the service with AgentMap
def register_service():
    """Register this service with the AgentMap service registry."""
    from agentmap.registry import ServiceRegistry
    
    ServiceRegistry.register_service('email_service', EmailService)
    ServiceRegistry.register_service('email', EmailService)  # Alias


__all__ = ['EmailService', 'create_email_service', 'register_service']
`}
/>

### Custom Service: Slack Service
<DownloadButton 
  filename="slack_service.py"
  content={`"""
Slack Service Implementation

Custom service for sending Slack notifications with rich formatting,
thread support, and channel management.
"""

from agentmap.services.base_service import BaseService
from typing import Dict, Any, List, Optional
import json
import time
from datetime import datetime
import logging
import requests


class SlackService(BaseService):
    """
    Comprehensive Slack integration service.
    
    Features:
    - Rich message formatting with blocks and attachments
    - Multi-channel notifications
    - Thread support for organized conversations
    - Rate limiting and retry logic
    - Reaction and emoji support
    - File upload capabilities
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})
        
        self.bot_token = self.config.get('bot_token', '')
        self.webhook_url = self.config.get('webhook_url', '')
        self.retry_count = self.config.get('retry_count', 3)
        self.timeout = self.config.get('timeout', 30)
        
        # Default channels
        self.default_channels = self.config.get('default_channels', ['#general'])
        
        # Message formatting options
        self.use_blocks = self.config.get('use_blocks', True)
        self.include_metadata = self.config.get('include_metadata', True)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("SlackService initialized")
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send Slack notifications based on input configuration.
        
        Args:
            inputs: Slack configuration including channels, messages, formatting
            
        Returns:
            Dict: Slack sending results with delivery status
        """
        try:
            # Extract Slack configuration
            slack_configs = self._extract_slack_config(inputs)
            
            if not slack_configs:
                return {"error": "No valid Slack configuration found"}
            
            # Send messages with retry logic
            results = []
            for config in slack_configs:
                result = self._send_slack_message_with_retry(config)
                results.append(result)
            
            # Aggregate results
            return self._aggregate_slack_results(results)
            
        except Exception as e:
            error_msg = f"Slack service failed: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "service": "slack"}
    
    def _extract_slack_config(self, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract Slack configuration from inputs."""
        configs = []
        
        # Check for direct Slack configuration
        if 'slack_config' in inputs:
            slack_data = inputs['slack_config']
            if isinstance(slack_data, list):
                configs.extend(slack_data)
            else:
                configs.append(slack_data)
        
        # Check for service requirements structure
        if 'service_requirements' in inputs:
            service_req = inputs['service_requirements']
            if isinstance(service_req, str):
                try:
                    service_req = json.loads(service_req)
                except:
                    pass
            
            if isinstance(service_req, dict):
                service_configs = service_req.get('service_configs', {})
                if 'slack' in service_configs:
                    slack_conf = service_configs['slack']
                    configs.append({
                        'channels': slack_conf.get('channels', self.default_channels),
                        'message': self._generate_message(inputs),
                        'priority': slack_conf.get('priority', 'normal'),
                        'notification_type': slack_conf.get('notification_type', 'update')
                    })
        
        # Check for task-based Slack extraction
        if 'task_data' in inputs:
            task_configs = self._extract_task_slack_configs(inputs['task_data'])
            configs.extend(task_configs)
        
        return configs
    
    def _extract_task_slack_configs(self, task_data: Any) -> List[Dict[str, Any]]:
        """Extract Slack configurations from task data."""
        configs = []
        
        if isinstance(task_data, str):
            try:
                task_data = json.loads(task_data)
            except:
                return configs
        
        if isinstance(task_data, dict):
            # Check project level Slack settings
            if 'integration_requirements' in task_data:
                integration_req = task_data['integration_requirements']
                if 'notification_preferences' in integration_req:
                    slack_prefs = integration_req['notification_preferences'].get('slack', {})
                    if slack_prefs.get('enabled'):
                        channels_config = slack_prefs.get('channels', {})
                        for channel, notification_types in channels_config.items():
                            configs.append({
                                'channels': [channel],
                                'message': self._generate_project_slack_message(task_data),
                                'priority': 'normal',
                                'notification_type': 'project_update',
                                'allowed_types': notification_types
                            })
            
            # Check individual task Slack notifications
            if 'tasks' in task_data:
                for task in task_data['tasks']:
                    if 'external_services_needed' in task:
                        for service in task['external_services_needed']:
                            if service.get('service') == 'slack':
                                config = service.get('config', {})
                                configs.append({
                                    'channels': [config.get('channel', '#general')],
                                    'message': self._generate_task_slack_message(task),
                                    'priority': config.get('priority', 'normal'),
                                    'notification_type': config.get('notification_type', 'task_update'),
                                    'task_info': task
                                })
        
        return configs
    
    def _send_slack_message_with_retry(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Send Slack message with retry logic."""
        last_error = None
        
        for attempt in range(self.retry_count + 1):
            try:
                if attempt > 0:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + (time.time() % 1)
                    self.logger.info(f"Retrying Slack send (attempt {attempt + 1}) after {wait_time:.1f}s")
                    time.sleep(wait_time)
                
                result = self._send_single_slack_message(config)
                return result
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Slack send attempt {attempt + 1} failed: {last_error}")
        
        # All attempts failed
        return {
            'status': 'failed',
            'error': last_error,
            'channels': config.get('channels', []),
            'attempts': self.retry_count + 1
        }
    
    def _send_single_slack_message(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single Slack message."""
        channels = config.get('channels', self.default_channels)
        message = config.get('message', '')
        
        # Format message based on configuration
        if self.use_blocks:
            payload = self._create_blocks_message(config)
        else:
            payload = self._create_simple_message(config)
        
        sent_channels = []
        failed_channels = []
        
        for channel in channels:
            try:
                if self.webhook_url:
                    result = self._send_webhook_message(channel, payload)
                else:
                    result = self._send_api_message(channel, payload)
                
                if result.get('ok', False):
                    sent_channels.append(channel)
                else:
                    failed_channels.append(channel)
                    
            except Exception as e:
                self.logger.error(f"Failed to send to channel {channel}: {str(e)}")
                failed_channels.append(channel)
        
        return {
            'status': 'success' if not failed_channels else ('partial' if sent_channels else 'failed'),
            'sent_channels': sent_channels,
            'failed_channels': failed_channels,
            'total_channels': len(channels),
            'message_preview': message[:100] + "..." if len(message) > 100 else message,
            'timestamp': datetime.now().isoformat()
        }
    
    def _create_blocks_message(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create rich Slack message using blocks."""
        message = config.get('message', '')
        priority = config.get('priority', 'normal')
        notification_type = config.get('notification_type', 'update')
        
        # Determine emoji and color based on priority and type
        if priority == 'high' or 'alert' in notification_type:
            emoji = "🚨"
            color = "#FF0000"
        elif priority == 'medium' or 'warning' in notification_type:
            emoji = "⚠️"
            color = "#FF9500"
        else:
            emoji = "ℹ️"
            color = "#36C5F0"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} AgentMap Integration Update"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]
        
        # Add task information if available
        if 'task_info' in config:
            task = config['task_info']
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Task:*\\n{task.get('title', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\\n{task.get('status', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:*\\n{task.get('priority', 'Normal')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Assignee:*\\n{task.get('assignee', 'Unassigned')}"
                    }
                ]
            })
        
        # Add metadata if enabled
        if self.include_metadata:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🤖 *AgentMap* | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {notification_type}"
                    }
                ]
            })
        
        return {
            "blocks": blocks,
            "attachments": [
                {
                    "color": color,
                    "blocks": []
                }
            ]
        }
    
    def _create_simple_message(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create simple text Slack message."""
        message = config.get('message', '')
        priority = config.get('priority', 'normal')
        
        # Add emoji based on priority
        if priority == 'high':
            prefix = "🚨 HIGH PRIORITY: "
        elif priority == 'medium':
            prefix = "⚠️ "
        else:
            prefix = "ℹ️ "
        
        formatted_message = f"{prefix}{message}"
        
        if self.include_metadata:
            formatted_message += f"\\n\\n_Sent by AgentMap at {datetime.now().strftime('%H:%M:%S')}_"
        
        return {
            "text": formatted_message
        }
    
    def _send_webhook_message(self, channel: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message using Slack webhook."""
        # Add channel to payload
        payload["channel"] = channel
        
        response = requests.post(
            self.webhook_url,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            return {"ok": True}
        else:
            return {"ok": False, "error": f"HTTP {response.status_code}"}
    
    def _send_api_message(self, channel: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message using Slack API."""
        # This is a placeholder for Slack API implementation
        # In practice, you would use the Slack SDK
        
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        
        payload["channel"] = channel
        
        # Simulate API call
        self.logger.info(f"Slack API message sent to {channel} (simulated)")
        
        return {"ok": True, "ts": str(time.time())}
    
    def _aggregate_slack_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple Slack sending results."""
        total_messages = len(results)
        successful_messages = len([r for r in results if r.get('status') == 'success'])
        failed_messages = total_messages - successful_messages
        
        all_channels = []
        successful_channels = []
        failed_channels = []
        
        for result in results:
            sent_channels = result.get('sent_channels', [])
            fail_channels = result.get('failed_channels', [])
            
            all_channels.extend(sent_channels + fail_channels)
            successful_channels.extend(sent_channels)
            failed_channels.extend(fail_channels)
        
        return {
            'service': 'slack',
            'status': 'success' if failed_messages == 0 else ('partial' if successful_messages > 0 else 'failed'),
            'summary': {
                'total_messages': total_messages,
                'successful_messages': successful_messages,
                'failed_messages': failed_messages,
                'success_rate': successful_messages / total_messages if total_messages > 0 else 0
            },
            'channels': {
                'total': len(set(all_channels)),
                'successful': len(set(successful_channels)),
                'failed': len(set(failed_channels)),
                'successful_list': list(set(successful_channels)),
                'failed_list': list(set(failed_channels))
            },
            'detailed_results': results,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_message(self, inputs: Dict[str, Any]) -> str:
        """Generate Slack message based on inputs."""
        message_parts = []
        
        message_parts.append("🤖 **AgentMap Integration Update**")
        message_parts.append("")
        
        # Add task information if available
        if 'task_data' in inputs:
            task_data = inputs['task_data']
            if isinstance(task_data, str):
                try:
                    task_data = json.loads(task_data)
                except:
                    pass
            
            if isinstance(task_data, dict):
                if 'project' in task_data:
                    project = task_data['project']
                    message_parts.append(f"📋 **Project**: {project.get('name', 'Unknown')}")
                    message_parts.append(f"🎯 **Priority**: {project.get('priority', 'Normal')}")
                    message_parts.append("")
                
                if 'tasks' in task_data:
                    active_tasks = [t for t in task_data['tasks'] if t.get('status') == 'in_progress']
                    if active_tasks:
                        message_parts.append("⚡ **Active Tasks**:")
                        for task in active_tasks[:3]:  # Limit to 3 tasks
                            message_parts.append(f"• {task.get('title', 'Unknown')}")
                        message_parts.append("")
        
        message_parts.append("✅ External services integration completed successfully!")
        
        return "\\n".join(message_parts)
    
    def _generate_project_slack_message(self, task_data: Dict[str, Any]) -> str:
        """Generate project-specific Slack message."""
        message_parts = []
        
        project = task_data.get('project', {})
        message_parts.append(f"📋 **Project Update: {project.get('name', 'Unknown Project')}**")
        message_parts.append("")
        message_parts.append(f"🎯 **Priority**: {project.get('priority', 'Normal')}")
        message_parts.append(f"👤 **Team Lead**: {project.get('team_lead', 'Unknown')}")
        message_parts.append("")
        
        # Task summary
        tasks = task_data.get('tasks', [])
        if tasks:
            status_counts = {}
            for task in tasks:
                status = task.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            message_parts.append("📊 **Task Status Summary**:")
            for status, count in status_counts.items():
                emoji = "✅" if status == "completed" else "⚡" if status == "in_progress" else "📋"
                message_parts.append(f"{emoji} {status.title()}: {count}")
            message_parts.append("")
        
        message_parts.append("🔗 External services integration completed")
        
        return "\\n".join(message_parts)
    
    def _generate_task_slack_message(self, task: Dict[str, Any]) -> str:
        """Generate task-specific Slack message."""
        message_parts = []
        
        message_parts.append(f"⚡ **Task Update: {task.get('title', 'Unknown Task')}**")
        message_parts.append("")
        message_parts.append(f"📝 **Status**: {task.get('status', 'Unknown').title()}")
        message_parts.append(f"🎯 **Priority**: {task.get('priority', 'Normal')}")
        message_parts.append(f"👤 **Assignee**: {task.get('assignee', 'Unassigned')}")
        message_parts.append("")
        
        if 'description' in task:
            desc = task['description']
            if len(desc) > 100:
                desc = desc[:100] + "..."
            message_parts.append(f"📋 **Description**: {desc}")
            message_parts.append("")
        
        if 'github_issue' in task:
            message_parts.append(f"🔗 **GitHub Issue**: #{task['github_issue']}")
        
        if 'estimated_hours' in task:
            message_parts.append(f"⏱️ **Estimated Hours**: {task['estimated_hours']}")
        
        message_parts.append("")
        message_parts.append("🔔 External services have been notified")
        
        return "\\n".join(message_parts)


def create_slack_service(config: Dict[str, Any] = None) -> SlackService:
    """Factory function to create SlackService instances."""
    return SlackService(config)


# Register the service with AgentMap
def register_service():
    """Register this service with the AgentMap service registry."""
    from agentmap.registry import ServiceRegistry
    
    ServiceRegistry.register_service('slack_service', SlackService)
    ServiceRegistry.register_service('slack', SlackService)  # Alias


__all__ = ['SlackService', 'create_slack_service', 'register_service']
`}
/>

## Step 2: Understanding Service Architecture

### Service Registration Pattern

AgentMap uses a service registry pattern for external integrations:

```python
# Service registration
from agentmap.registry import ServiceRegistry

ServiceRegistry.register_service('email_service', EmailService)
ServiceRegistry.register_service('slack_service', SlackService)
ServiceRegistry.register_service('github_service', GitHubService)
```

### Host Protocol Implementation

Services implement the host protocol interface:

```python
class BaseService:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Main service processing method."""
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """Check if service is healthy."""
        return True
    
    def get_capabilities(self) -> List[str]:
        """Return list of service capabilities."""
        return []
```

### Service Injection Patterns

#### 1. **Configuration-Based Injection**
```csv
node,type,context
EmailNotification,email_service,"{""provider"": ""smtp"", ""retry_count"": 3}"
```

#### 2. **Dynamic Service Selection**
```python
def select_service(requirements):
    if requirements.get('priority') == 'high':
        return 'premium_email_service'
    else:
        return 'standard_email_service'
```

#### 3. **Service Composition**
```python
class CompositeService(BaseService):
    def __init__(self, services: List[BaseService]):
        self.services = services
    
    def process(self, inputs):
        results = []
        for service in self.services:
            result = service.process(inputs)
            results.append(result)
        return self.aggregate_results(results)
```

## Step 3: Running the External Integration System

### Setup Steps

1. **Create Directory Structure**:
```bash
mkdir -p external-integration/data
cd external-integration
```

2. **Download All Files**:
   - lesson6.csv (main workflow)
   - project_tasks.json (sample project data)
   - email_service.py (email integration)
   - slack_service.py (Slack integration)

3. **Configure Services**:
```bash
# Set environment variables for service authentication
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

4. **Install Service Files**:
```bash
# Copy service files to AgentMap services directory
cp email_service.py ~/.agentmap/services/
cp slack_service.py ~/.agentmap/services/
```

5. **Run the Integration**:
```bash
agentmap run lesson6.csv
```

### Expected Execution Flow

```
📄 Loading project tasks...
🔍 Analyzing service requirements...
📧 Sending email notifications...
💬 Posting Slack updates...
🔗 Creating GitHub issues...
💾 Storing data in database...
🌐 Calling custom APIs...
📊 Aggregating all results...
📋 Generating status report...
✅ Integration complete!
```

## Step 4: Advanced Service Patterns

### Pattern 1: Circuit Breaker

Prevent cascading failures with circuit breakers:

```python
class CircuitBreakerService(BaseService):
    def __init__(self, wrapped_service, failure_threshold=5, timeout=60):
        super().__init__()
        self.wrapped_service = wrapped_service
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def process(self, inputs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                return {"error": "Circuit breaker is OPEN"}
        
        try:
            result = self.wrapped_service.process(inputs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e
```

### Pattern 2: Service Proxy with Caching

Cache expensive service calls:

```python
class CachingServiceProxy(BaseService):
    def __init__(self, wrapped_service, cache_ttl=300):
        super().__init__()
        self.wrapped_service = wrapped_service
        self.cache = {}
        self.cache_ttl = cache_ttl
    
    def process(self, inputs):
        cache_key = self._generate_cache_key(inputs)
        
        # Check cache
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            if time.time() - cached_item['timestamp'] < self.cache_ttl:
                return cached_item['result']
        
        # Call service and cache result
        result = self.wrapped_service.process(inputs)
        self.cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        return result
    
    def _generate_cache_key(self, inputs):
        # Create a deterministic cache key
        return hashlib.md5(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
```

### Pattern 3: Service Health Monitoring

Monitor service health automatically:

```python
class HealthMonitoringService(BaseService):
    def __init__(self, services: Dict[str, BaseService]):
        super().__init__()
        self.services = services
        self.health_status = {}
        self.last_check_time = {}
    
    def process(self, inputs):
        # Check health of all services
        for name, service in self.services.items():
            if self._should_check_health(name):
                self.health_status[name] = service.health_check()
                self.last_check_time[name] = time.time()
        
        # Route to healthy services only
        healthy_services = {
            name: service for name, service in self.services.items()
            if self.health_status.get(name, True)
        }
        
        if not healthy_services:
            return {"error": "No healthy services available"}
        
        # Use first healthy service (could implement load balancing)
        service_name, service = next(iter(healthy_services.items()))
        return service.process(inputs)
    
    def _should_check_health(self, service_name):
        last_check = self.last_check_time.get(service_name, 0)
        return time.time() - last_check > 60  # Check every minute
```

## Step 5: Building Custom Services

### Exercise 1: GitHub Service

Create a comprehensive GitHub integration service:

```python
class GitHubService(BaseService):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.api_token = self.config.get('api_token', '')
        self.base_url = self.config.get('base_url', 'https://api.github.com')
        
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        github_config = self._extract_github_config(inputs)
        
        results = []
        for config in github_config:
            action = config.get('action', 'create_issue')
            
            if action == 'create_issue':
                result = self._create_issue(config)
            elif action == 'update_pr':
                result = self._update_pull_request(config)
            elif action == 'add_comment':
                result = self._add_comment(config)
            else:
                result = {'error': f'Unknown action: {action}'}
            
            results.append(result)
        
        return self._aggregate_github_results(results)
    
    def _create_issue(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a GitHub issue."""
        repo = config.get('repository', '')
        title = config.get('title', 'AgentMap Integration')
        body = config.get('body', '')
        labels = config.get('labels', [])
        
        # Simulate GitHub API call
        issue_data = {
            'title': title,
            'body': body,
            'labels': labels
        }
        
        return {
            'action': 'create_issue',
            'status': 'success',
            'repository': repo,
            'issue_number': 42,  # Simulated
            'url': f'https://github.com/{repo}/issues/42'
        }
```

### Exercise 2: Database Service

Build a database integration service:

```python
class DatabaseService(BaseService):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.connection_string = self.config.get('connection_string', '')
        self.pool_size = self.config.get('pool_size', 5)
        
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        db_operations = self._extract_db_operations(inputs)
        
        results = []
        for operation in db_operations:
            op_type = operation.get('operation', 'select')
            
            if op_type == 'insert':
                result = self._insert_data(operation)
            elif op_type == 'update':
                result = self._update_data(operation)
            elif op_type == 'select':
                result = self._select_data(operation)
            elif op_type == 'delete':
                result = self._delete_data(operation)
            else:
                result = {'error': f'Unknown operation: {op_type}'}
            
            results.append(result)
        
        return self._aggregate_db_results(results)
    
    def _insert_data(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Insert data into database."""
        table = operation.get('table', '')
        data = operation.get('data', {})
        
        # Simulate database insertion
        return {
            'operation': 'insert',
            'status': 'success',
            'table': table,
            'rows_affected': 1,
            'record_id': 12345
        }
```

### Exercise 3: Custom API Service

Create a flexible API integration service:

```python
class CustomAPIService(BaseService):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.default_timeout = self.config.get('timeout', 30)
        self.retry_count = self.config.get('retry_count', 3)
        
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        api_calls = self._extract_api_calls(inputs)
        
        results = []
        for call in api_calls:
            result = self._make_api_call_with_retry(call)
            results.append(result)
        
        return self._aggregate_api_results(results)
    
    def _make_api_call_with_retry(self, call_config: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call with retry logic."""
        last_error = None
        
        for attempt in range(self.retry_count + 1):
            try:
                return self._make_single_api_call(call_config)
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.retry_count:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        return {
            'status': 'failed',
            'error': last_error,
            'attempts': self.retry_count + 1
        }
    
    def _make_single_api_call(self, call_config: Dict[str, Any]) -> Dict[str, Any]:
        """Make a single API call."""
        endpoint = call_config.get('endpoint', '')
        method = call_config.get('method', 'GET')
        headers = call_config.get('headers', {})
        data = call_config.get('data', {})
        
        # Simulate API call
        return {
            'status': 'success',
            'endpoint': endpoint,
            'method': method,
            'response_code': 200,
            'response_time': 0.5,
            'data': {'message': 'API call successful'}
        }
```

## Step 6: Service Configuration and Management

### Environment-Based Configuration

```python
import os

class ServiceConfig:
    @staticmethod
    def get_email_config():
        return {
            'provider': os.getenv('EMAIL_PROVIDER', 'smtp'),
            'smtp_host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_username': os.getenv('SMTP_USERNAME', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'retry_count': int(os.getenv('EMAIL_RETRY_COUNT', '3'))
        }
    
    @staticmethod
    def get_slack_config():
        return {
            'bot_token': os.getenv('SLACK_BOT_TOKEN', ''),
            'webhook_url': os.getenv('SLACK_WEBHOOK_URL', ''),
            'default_channels': os.getenv('SLACK_DEFAULT_CHANNELS', '#general').split(','),
            'timeout': int(os.getenv('SLACK_TIMEOUT', '30'))
        }
```

### Service Discovery

```python
class ServiceDiscovery:
    def __init__(self):
        self.services = {}
        self.service_configs = {}
    
    def register_service(self, name: str, service_class: type, config: Dict[str, Any] = None):
        """Register a service with discovery system."""
        self.services[name] = service_class
        self.service_configs[name] = config or {}
    
    def get_service(self, name: str) -> BaseService:
        """Get service instance by name."""
        if name not in self.services:
            raise ValueError(f"Service {name} not found")
        
        service_class = self.services[name]
        config = self.service_configs[name]
        
        return service_class(config)
    
    def list_services(self) -> List[str]:
        """List all registered services."""
        return list(self.services.keys())
    
    def health_check_all(self) -> Dict[str, bool]:
        """Health check all registered services."""
        health_status = {}
        
        for name in self.services:
            try:
                service = self.get_service(name)
                health_status[name] = service.health_check()
            except Exception:
                health_status[name] = False
        
        return health_status
```

### Service Middleware

```python
class ServiceMiddleware:
    def __init__(self, service: BaseService):
        self.service = service
        self.middlewares = []
    
    def add_middleware(self, middleware):
        """Add middleware to the service chain."""
        self.middlewares.append(middleware)
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process inputs through middleware chain."""
        
        # Pre-processing middleware
        for middleware in self.middlewares:
            if hasattr(middleware, 'pre_process'):
                inputs = middleware.pre_process(inputs)
        
        # Main service processing
        result = self.service.process(inputs)
        
        # Post-processing middleware
        for middleware in reversed(self.middlewares):
            if hasattr(middleware, 'post_process'):
                result = middleware.post_process(result)
        
        return result


class LoggingMiddleware:
    def pre_process(self, inputs):
        logging.info(f"Service call started with inputs: {inputs}")
        return inputs
    
    def post_process(self, result):
        logging.info(f"Service call completed with result: {result}")
        return result


class MetricsMiddleware:
    def __init__(self):
        self.call_count = 0
        self.total_time = 0
    
    def pre_process(self, inputs):
        self.start_time = time.time()
        self.call_count += 1
        return inputs
    
    def post_process(self, result):
        end_time = time.time()
        self.total_time += (end_time - self.start_time)
        return result
```

## Step 7: Error Handling and Resilience

### Comprehensive Error Handling

```python
class ResilientService(BaseService):
    def __init__(self, services: List[BaseService], strategy='failover'):
        super().__init__()
        self.services = services
        self.strategy = strategy
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if self.strategy == 'failover':
            return self._failover_strategy(inputs)
        elif self.strategy == 'parallel':
            return self._parallel_strategy(inputs)
        elif self.strategy == 'load_balance':
            return self._load_balance_strategy(inputs)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _failover_strategy(self, inputs):
        """Try services in order until one succeeds."""
        last_error = None
        
        for i, service in enumerate(self.services):
            try:
                return service.process(inputs)
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Service {i} failed: {last_error}")
        
        return {"error": f"All services failed. Last error: {last_error}"}
    
    def _parallel_strategy(self, inputs):
        """Run all services in parallel and return first success."""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(service.process, inputs): service 
                      for service in self.services}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if 'error' not in result:
                        return result
                except Exception as e:
                    self.logger.warning(f"Service failed: {str(e)}")
        
        return {"error": "All parallel services failed"}
    
    def _load_balance_strategy(self, inputs):
        """Distribute load across services."""
        import random
        
        available_services = [s for s in self.services if s.health_check()]
        
        if not available_services:
            return {"error": "No healthy services available"}
        
        selected_service = random.choice(available_services)
        return selected_service.process(inputs)
```

### Graceful Degradation

```python
class GracefulDegradationService(BaseService):
    def __init__(self, primary_service: BaseService, fallback_service: BaseService):
        super().__init__()
        self.primary_service = primary_service
        self.fallback_service = fallback_service
    
    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Try primary service first
            result = self.primary_service.process(inputs)
            
            # Check if result indicates degraded performance
            if self._is_degraded_result(result):
                self.logger.warning("Primary service showing degraded performance")
                return self._try_fallback(inputs)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Primary service failed: {str(e)}")
            return self._try_fallback(inputs)
    
    def _try_fallback(self, inputs):
        """Try fallback service with reduced functionality."""
        try:
            result = self.fallback_service.process(inputs)
            result['degraded_mode'] = True
            result['message'] = 'Service running in degraded mode'
            return result
            
        except Exception as e:
            return {
                "error": "Both primary and fallback services failed",
                "primary_error": str(e),
                "fallback_error": str(e)
            }
    
    def _is_degraded_result(self, result):
        """Check if result indicates degraded performance."""
        if 'response_time' in result and result['response_time'] > 5.0:
            return True
        if 'error_rate' in result and result['error_rate'] > 0.1:
            return True
        return False
```

## Key Concepts Mastered

### 1. **Service Architecture Patterns**
- Service registration and discovery
- Host protocol implementation
- Service injection and composition
- Middleware and proxy patterns

### 2. **External Integration Strategies**
- Multi-provider service implementations
- Authentication and rate limiting
- Retry logic and circuit breakers
- Health monitoring and failover

### 3. **Resilience and Error Handling**
- Graceful degradation strategies
- Circuit breaker patterns
- Parallel and failover execution
- Comprehensive error recovery

### 4. **Service Management**
- Configuration management
- Service discovery and registration
- Health monitoring and metrics
- Load balancing and routing

## Troubleshooting External Services

### Common Integration Issues

#### Issue: Authentication failures
**Symptoms**: 401/403 errors from external APIs
**Solutions**:
- Verify API keys and tokens are correct
- Check token expiration and refresh logic
- Confirm service account permissions
- Test authentication outside of workflow

#### Issue: Rate limiting
**Symptoms**: 429 errors or throttling responses
**Solutions**:
- Implement exponential backoff
- Add rate limiting awareness to services
- Use service queues for high-volume operations
- Consider upgrading service plans

#### Issue: Network connectivity
**Symptoms**: Timeout errors or connection failures
**Solutions**:
- Check firewall and proxy configurations
- Verify DNS resolution
- Test service endpoints directly
- Implement connection pooling

#### Issue: Service dependencies
**Symptoms**: Cascading failures across services
**Solutions**:
- Use circuit breakers
- Implement service health checks
- Design for graceful degradation
- Add service isolation

## Congratulations!

You've mastered external services integration! You can now build workflows that:

- ✅ **Connect to External APIs** - Integrate with any REST/GraphQL service
- ✅ **Handle Authentication** - Manage tokens, keys, and OAuth flows
- ✅ **Implement Resilience** - Circuit breakers, retries, and failover
- ✅ **Monitor Service Health** - Track performance and availability
- ✅ **Manage Configuration** - Environment-based and dynamic configuration

### What's Next?

Ready for deployment and production patterns? Let's explore:
- **[Lesson 7: FastAPI Standalone](/docs/guides/learning/07-fastapi-standalone)** - Deploy as standalone web services
- **[Lesson 8: FastAPI Integration](/docs/guides/learning/08-fastapi-integration)** - Integrate into existing applications

---

*🌐 **External services integration opens unlimited possibilities** - connect your AI workflows to any system, API, or service in your technology ecosystem. You're now ready to build truly connected intelligent automation!*
