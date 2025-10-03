# AgentMap AWS Deployment Script for PowerShell
# Alternative to the batch script for users who prefer PowerShell

param(
    [string]$ProjectName = "agentmap",
    [string]$Environment = "dev", 
    [string]$AwsRegion = "us-east-1",
    [bool]$CreateFullStack = $false,
    [bool]$CreateApiGateway = $true,
    [switch]$SkipVerification
)

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "AgentMap AWS Serverless Deployment" -ForegroundColor Cyan  
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check AWS CLI
try {
    $awsVersion = aws --version 2>$null
    Write-Host "✓ AWS CLI found: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ AWS CLI not found. Please install from: https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

# Check Terraform
try {
    $terraformVersion = terraform version 2>$null | Select-Object -First 1
    Write-Host "✓ Terraform found: $terraformVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Terraform not found. Please install from: https://www.terraform.io/downloads" -ForegroundColor Red
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version 2>$null
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.12+ from: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "- Project: $ProjectName"
Write-Host "- Environment: $Environment"
Write-Host "- Region: $AwsRegion"
Write-Host "- Full Stack: $CreateFullStack"
Write-Host "- API Gateway: $CreateApiGateway"
Write-Host ""

# Step 1: Prepare deployment
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Step 1: Preparing deployment package" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Clean up previous files
if (Test-Path "lambda_package.zip") { Remove-Item "lambda_package.zip" -Force }
if (Test-Path "main.tf") { Remove-Item "main.tf" -Force }

# Install AgentMap
Write-Host "Installing AgentMap..." -ForegroundColor Yellow
$installResult = & pip install agentmap -t . --upgrade --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to install AgentMap: $installResult" -ForegroundColor Red
    exit 1
}
Write-Host "✓ AgentMap installed successfully" -ForegroundColor Green

# Prepare Terraform config
if (Test-Path "aws-terraform-deployment.txt") {
    Rename-Item "aws-terraform-deployment.txt" "main.tf"
    Write-Host "✓ Terraform configuration ready" -ForegroundColor Green
} else {
    Write-Host "✗ aws-terraform-deployment.txt not found" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Deploy infrastructure
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Step 2: Deploying AWS infrastructure" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Initialize Terraform
Write-Host "Initializing Terraform..." -ForegroundColor Yellow
& terraform init | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Terraform init failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Terraform initialized" -ForegroundColor Green

# Plan deployment
Write-Host "Planning deployment..." -ForegroundColor Yellow
$tfVars = @(
    "-var=project_name=$ProjectName",
    "-var=environment=$Environment", 
    "-var=aws_region=$AwsRegion",
    "-var=create_full_stack=$($CreateFullStack.ToString().ToLower())",
    "-var=create_api_gateway=$($CreateApiGateway.ToString().ToLower())"
)

& terraform plan @tfVars -out=plan.out | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Terraform plan failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Terraform plan completed" -ForegroundColor Green

# Confirm deployment
Write-Host ""
Write-Host "Ready to deploy infrastructure. Continue? [y/N]: " -NoNewline -ForegroundColor Yellow
$confirmation = Read-Host
if ($confirmation -ne 'y' -and $confirmation -ne 'Y') {
    Write-Host "Deployment cancelled." -ForegroundColor Yellow
    Remove-Item "plan.out" -Force -ErrorAction SilentlyContinue
    exit 0
}

# Apply deployment
Write-Host ""
Write-Host "Applying Terraform configuration..." -ForegroundColor Yellow
& terraform apply plan.out
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Terraform apply failed" -ForegroundColor Red
    exit 1
}

Remove-Item "plan.out" -Force -ErrorAction SilentlyContinue
Write-Host "✓ Infrastructure deployed successfully!" -ForegroundColor Green
Write-Host ""

# Step 3: Get deployment info
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Step 3: Getting deployment information" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

$functionName = & terraform output -raw lambda_function_name 2>$null
$apiUrl = & terraform output -raw api_gateway_url 2>$null
$logGroup = & terraform output -raw cloudwatch_log_group 2>$null

Write-Host "Deployment Information:" -ForegroundColor Yellow
Write-Host "- Function Name: $functionName"
Write-Host "- API Gateway URL: $apiUrl"
Write-Host "- Log Group: $logGroup"
Write-Host ""

# Step 4: Verify deployment
if (-not $SkipVerification) {
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host "Step 4: Verifying deployment" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan

    Write-Host "Running deployment verification..." -ForegroundColor Yellow
    & python verify_deployment.py $functionName $AwsRegion $apiUrl
    $verificationResult = $LASTEXITCODE
    
    Write-Host ""
    if ($verificationResult -eq 0) {
        Write-Host "====================================" -ForegroundColor Green
        Write-Host "✓ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
        Write-Host "====================================" -ForegroundColor Green
    } else {
        Write-Host "====================================" -ForegroundColor Yellow
        Write-Host "⚠ DEPLOYMENT COMPLETED WITH WARNINGS" -ForegroundColor Yellow
        Write-Host "====================================" -ForegroundColor Yellow
        Write-Host "Some verification tests failed, but infrastructure was deployed." -ForegroundColor Yellow
    }
}

# Next steps
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Test your Lambda function:" -ForegroundColor White
Write-Host "   aws lambda invoke --function-name $functionName --payload `"{\\`"test\\`":\\`"data\\`"}`" response.json" -ForegroundColor Gray

if ($CreateApiGateway) {
    Write-Host ""
    Write-Host "2. Test your API Gateway:" -ForegroundColor White
    Write-Host "   Open: $apiUrl" -ForegroundColor Gray
}

Write-Host ""
Write-Host "3. Monitor logs:" -ForegroundColor White
Write-Host "   aws logs tail $logGroup --follow" -ForegroundColor Gray

Write-Host ""
Write-Host "4. AWS Console Links:" -ForegroundColor White
Write-Host "   Lambda: https://$AwsRegion.console.aws.amazon.com/lambda/home?region=$AwsRegion#/functions/$functionName" -ForegroundColor Gray
Write-Host "   CloudWatch: https://$AwsRegion.console.aws.amazon.com/cloudwatch/home?region=$AwsRegion" -ForegroundColor Gray

Write-Host ""
Write-Host "Deployment completed!" -ForegroundColor Green
