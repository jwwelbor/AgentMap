# AgentMap — AWS Lambda Serverless Deployment

## Overview
Deploy AgentMap as a serverless function on AWS Lambda with multiple trigger options.

## Files
- `main.py` — Fixed Lambda adapter with proper error handling and fallback imports
- `requirements.txt` — AgentMap dependency (boto3 provided by Lambda runtime)
- `aws-terraform-deployment.txt` — Terraform configuration with corrected paths and packaging

## Prerequisites
1. **AWS CLI** installed and configured: https://aws.amazon.com/cli/
2. **Terraform** installed: https://www.terraform.io/downloads
3. **Python 3.12+** installed: https://www.python.org/downloads/
4. **AWS credentials** configured: `aws configure`

## Quick Deploy (Windows)

### Method 1: Minimal Lambda + API Gateway (Recommended)
```cmd
cd C:\Users\jwwel\Documents\code\AgentMap\deployment_scripts\aws

REM Install AgentMap as dependency
pip install agentmap -t . --upgrade

REM Rename Terraform file
ren aws-terraform-deployment.txt main.tf

REM Initialize and deploy
terraform init
terraform apply -var="create_full_stack=false" -var="create_api_gateway=true"
```

### Method 2: Full Stack with SQS, DynamoDB, S3
```cmd
terraform apply -var="create_full_stack=true" -var="create_api_gateway=true"
```

## Manual Deployment Steps

### Step 1: Prepare Lambda Package
```cmd
REM Install AgentMap and dependencies locally
pip install agentmap -t . --upgrade

REM Verify main.py handler function exists
type main.py | findstr "def handler"
```

### Step 2: Deploy Infrastructure
```cmd
REM Rename Terraform configuration
ren aws-terraform-deployment.txt main.tf

REM Initialize Terraform
terraform init

REM Plan deployment (review changes)
terraform plan -var="project_name=agentmap" -var="environment=dev"

REM Apply deployment
terraform apply -var="project_name=agentmap" -var="environment=dev"
```

### Step 3: Test Deployment
```cmd
REM Get function name and API URL from outputs
terraform output lambda_function_name
terraform output api_gateway_url

REM Test Lambda function directly
aws lambda invoke --function-name agentmap-dev --payload "{\"graph\":\"Demo\",\"state\":{\"hello\":\"world\"},\"action\":\"run\"}" response.json
type response.json

REM Test via API Gateway (replace with your actual URL)
curl -X POST https://YOUR_API_URL -H "Content-Type: application/json" -d "{\"graph\":\"Demo\",\"state\":{\"hello\":\"world\"},\"action\":\"run\"}"
```

## Configuration Options

### Deployment Variables
- `project_name` - Project name prefix (default: "agentmap")
- `environment` - Environment suffix (default: "dev")
- `aws_region` - AWS region (default: "us-east-1")
- `create_api_gateway` - Create HTTP API (default: true)
- `create_full_stack` - Create SQS, DynamoDB, S3, etc. (default: false)

### Examples
```cmd
REM Minimal deployment (Lambda + API Gateway only)
terraform apply -var="create_full_stack=false"

REM Production deployment with full stack
terraform apply -var="environment=prod" -var="create_full_stack=true" -var="aws_region=us-west-2"

REM Event-only deployment (no API Gateway)
terraform apply -var="create_api_gateway=false"
```

## What Gets Created

### Minimal Deployment (create_full_stack=false)
- ✅ Lambda function with AgentMap
- ✅ IAM role with basic execution permissions
- ✅ CloudWatch log group
- ✅ API Gateway HTTP API (if enabled)

### Full Stack Deployment (create_full_stack=true)
- ✅ All minimal components, plus:
- ✅ SQS queue with dead letter queue
- ✅ DynamoDB table with streams
- ✅ S3 bucket with event notifications
- ✅ SNS topic for results
- ✅ EventBridge scheduled trigger
- ✅ CloudWatch dashboard

## Event Formats

### API Gateway HTTP Request
```json
POST /
Content-Type: application/json

{
  "graph": "MyGraph",
  "state": {"key": "value"},
  "action": "run"
}
```

### SQS Message
```json
{
  "Records": [
    {
      "body": "{\"graph\":\"MyGraph\",\"state\":{\"key\":\"value\"},\"action\":\"run\"}"
    }
  ]
}
```

### Direct Lambda Invocation
```json
{
  "graph": "MyGraph",
  "state": {"key": "value"},
  "action": "run"
}
```

## Monitoring and Troubleshooting

### View Logs
```cmd
aws logs tail /aws/lambda/agentmap-dev --follow
```

### Common Issues

1. **Import errors**: AgentMap AWS handlers not found
   - Verify AgentMap is installed: `pip show agentmap`
   - Check handler import paths in `main.py`

2. **Permission errors**: Lambda execution failed
   - Check IAM role has necessary permissions
   - Review CloudWatch logs for specific errors

3. **Timeout errors**: Function execution timed out
   - Increase `lambda_timeout` variable
   - Optimize AgentMap graph execution time

4. **Package too large**: Deployment package exceeds 50MB
   - Remove unnecessary dependencies
   - Use Lambda layers for large dependencies

### Debug Commands
```cmd
REM Check function configuration
aws lambda get-function --function-name agentmap-dev

REM Update function code (after changes)
terraform apply

REM View recent errors
aws logs filter-log-events --log-group-name /aws/lambda/agentmap-dev --filter-pattern "ERROR"
```

## Cleanup

```cmd
REM Destroy all resources
terraform destroy

REM Remove local files
del lambda_package.zip
rmdir /s agentmap*
del main.tf
```

## Next Steps

After successful deployment:
1. Configure AgentMap graphs and agents
2. Set up monitoring alerts in CloudWatch
3. Add authentication if needed (API Gateway authorizers)
4. Configure environment-specific settings
5. Set up CI/CD pipeline for automatic deployments

## Support

For AgentMap-specific configuration, refer to the AgentMap documentation.
For AWS deployment issues, check:
- CloudWatch logs: `/aws/lambda/agentmap-dev`
- AWS Lambda console for function details
- API Gateway console for HTTP endpoint configuration
