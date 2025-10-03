@echo off
REM AgentMap AWS Deployment Script for Windows
REM This script handles the complete deployment process with error checking

echo ====================================
echo AgentMap AWS Serverless Deployment
echo ====================================
echo.

REM Check if AWS CLI is installed
echo Checking prerequisites...
aws --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: AWS CLI is not installed or not in PATH
    echo Please install AWS CLI from: https://aws.amazon.com/cli/
    echo Then run: aws configure
    pause
    exit /b 1
)

REM Check if Terraform is installed
terraform version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Terraform is not installed or not in PATH
    echo Please install Terraform from: https://www.terraform.io/downloads
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12+ from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✓ All prerequisites found!
echo.

REM Set deployment variables (customize these)
set PROJECT_NAME=agentmap
set ENVIRONMENT=dev
set AWS_REGION=us-east-1
set FULL_STACK=false
set API_GATEWAY=true

REM Allow user to customize settings
echo Current configuration:
echo - Project: %PROJECT_NAME%
echo - Environment: %ENVIRONMENT%
echo - Region: %AWS_REGION%
echo - Full Stack (SQS/DynamoDB/S3): %FULL_STACK%
echo - API Gateway: %API_GATEWAY%
echo.

set /p CUSTOM="Do you want to customize these settings? (y/N): "
if /i "%CUSTOM%"=="y" (
    echo.
    echo Customize deployment settings:
    set /p PROJECT_NAME="Project name [%PROJECT_NAME%]: " || set PROJECT_NAME=%PROJECT_NAME%
    set /p ENVIRONMENT="Environment [%ENVIRONMENT%]: " || set ENVIRONMENT=%ENVIRONMENT%
    set /p AWS_REGION="AWS region [%AWS_REGION%]: " || set AWS_REGION=%AWS_REGION%
    
    echo.
    echo Do you want the full stack with SQS, DynamoDB, S3, etc?
    set /p FULL_STACK_INPUT="Full stack deployment? (y/N): "
    if /i "%FULL_STACK_INPUT%"=="y" (
        set FULL_STACK=true
    ) else (
        set FULL_STACK=false
    )
    
    echo.
    echo Do you want to create an API Gateway for HTTP access?
    set /p API_GATEWAY_INPUT="Create API Gateway? (Y/n): "
    if /i "%API_GATEWAY_INPUT%"=="n" (
        set API_GATEWAY=false
    ) else (
        set API_GATEWAY=true
    )
)

echo.
echo Final configuration:
echo - Project: %PROJECT_NAME%
echo - Environment: %ENVIRONMENT%
echo - Region: %AWS_REGION%
echo - Full Stack: %FULL_STACK%
echo - API Gateway: %API_GATEWAY%
echo.

REM Step 1: Prepare deployment package
echo ====================================
echo Step 1: Preparing deployment package
echo ====================================

REM Clean up any previous deployment files
if exist lambda_package.zip del lambda_package.zip
if exist main.tf del main.tf

REM Install AgentMap and dependencies
echo Installing AgentMap...
pip install agentmap -t . --upgrade --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install AgentMap
    echo Make sure you have internet connectivity and pip is working
    pause
    exit /b 1
)

echo ✓ AgentMap installed successfully
echo.

REM Prepare Terraform configuration
echo Preparing Terraform configuration...
ren aws-terraform-deployment.txt main.tf
if %errorlevel% neq 0 (
    echo ERROR: Could not find aws-terraform-deployment.txt
    echo Make sure you're running this from the deployment_scripts\aws directory
    pause
    exit /b 1
)

echo ✓ Terraform configuration ready
echo.

REM Step 2: Deploy infrastructure
echo ====================================
echo Step 2: Deploying AWS infrastructure
echo ====================================

echo Initializing Terraform...
terraform init >nul
if %errorlevel% neq 0 (
    echo ERROR: Terraform init failed
    echo Check your AWS credentials and try again
    pause
    exit /b 1
)

echo ✓ Terraform initialized

echo.
echo Planning deployment...
terraform plan -var="project_name=%PROJECT_NAME%" -var="environment=%ENVIRONMENT%" -var="aws_region=%AWS_REGION%" -var="create_full_stack=%FULL_STACK%" -var="create_api_gateway=%API_GATEWAY%" -out=plan.out >nul
if %errorlevel% neq 0 (
    echo ERROR: Terraform plan failed
    echo Check the error messages above
    pause
    exit /b 1
)

echo ✓ Terraform plan completed

echo.
echo About to deploy the following resources:
terraform show -json plan.out | findstr "create"
echo.

set /p CONFIRM="Do you want to apply these changes? (y/N): "
if /i "%CONFIRM%" neq "y" (
    echo Deployment cancelled.
    del plan.out
    pause
    exit /b 0
)

echo.
echo Applying Terraform configuration...
terraform apply plan.out
if %errorlevel% neq 0 (
    echo ERROR: Terraform apply failed
    echo Check the error messages above
    pause
    exit /b 1
)

del plan.out
echo ✓ Infrastructure deployed successfully!
echo.

REM Step 3: Get deployment information
echo ====================================
echo Step 3: Getting deployment information
echo ====================================

for /f "delims=" %%i in ('terraform output -raw lambda_function_name 2^>nul') do set FUNCTION_NAME=%%i
for /f "delims=" %%i in ('terraform output -raw api_gateway_url 2^>nul') do set API_URL=%%i
for /f "delims=" %%i in ('terraform output -raw cloudwatch_log_group 2^>nul') do set LOG_GROUP=%%i

echo Deployment Information:
echo - Function Name: %FUNCTION_NAME%
echo - API Gateway URL: %API_URL%
echo - Log Group: %LOG_GROUP%
echo.

REM Step 4: Verify deployment
echo ====================================
echo Step 4: Verifying deployment
echo ====================================

echo Running deployment verification...
python verify_deployment.py %FUNCTION_NAME% %AWS_REGION% %API_URL%
set VERIFICATION_RESULT=%errorlevel%

echo.
if %VERIFICATION_RESULT% equ 0 (
    echo ====================================
    echo ✓ DEPLOYMENT SUCCESSFUL!
    echo ====================================
) else (
    echo ====================================
    echo ⚠ DEPLOYMENT COMPLETED WITH WARNINGS
    echo ====================================
    echo Some verification tests failed, but the infrastructure was deployed.
    echo Check the verification output above for details.
)

echo.
echo Next steps:
echo 1. Test your Lambda function:
echo    aws lambda invoke --function-name %FUNCTION_NAME% --payload "{\"test\":\"data\"}" response.json
echo.
if /i "%API_GATEWAY%"=="true" (
    echo 2. Test your API Gateway:
    echo    Open: %API_URL%
    echo    Or use curl/Postman to POST JSON data to that URL
    echo.
)
echo 3. Monitor logs:
echo    aws logs tail %LOG_GROUP% --follow
echo.
echo 4. Update your deployment:
echo    Re-run this script to update with new code
echo.

echo Useful AWS Console Links:
echo - Lambda: https://%AWS_REGION%.console.aws.amazon.com/lambda/home?region=%AWS_REGION%#/functions/%FUNCTION_NAME%
echo - CloudWatch: https://%AWS_REGION%.console.aws.amazon.com/cloudwatch/home?region=%AWS_REGION%#logsV2:log-groups/log-group/%%252Faws%%252Flambda%%252F%FUNCTION_NAME%

echo.
echo Press any key to exit...
pause >nul
