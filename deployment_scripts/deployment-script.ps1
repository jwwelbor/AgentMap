# AgentMap Serverless Deployment Script for Windows
# This script builds, packages, and deploys AgentMap serverless functions

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("aws", "azure", "gcp")]
    [string]$CloudProvider,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "C:\Users\jwwel\Documents\code\AgentMap",
    
    [Parameter(Mandatory=$false)]
    [string]$ConfigFile = $null,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipTests = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$DeployOnly = $false,
    
    [Parameter(Mandatory=$false)]
    [string]$Region = $null
)

# Set error handling
$ErrorActionPreference = "Stop"
$InformationPreference = "Continue"

# Set up paths
$ProjectRoot = Resolve-Path $ProjectRoot
$SrcPath = Join-Path $ProjectRoot "src"
$DeploymentPath = Join-Path $ProjectRoot "deployment"
$BuildPath = Join-Path $DeploymentPath "build"
$DistPath = Join-Path $DeploymentPath "dist"

Write-Information "🚀 Starting AgentMap Serverless Deployment"
Write-Information "   Cloud Provider: $CloudProvider"
Write-Information "   Environment: $Environment"
Write-Information "   Project Root: $ProjectRoot"

# Validate prerequisites
function Test-Prerequisites {
    Write-Information "🔍 Checking prerequisites..."
    
    # Check if source directory exists
    if (!(Test-Path $SrcPath)) {
        throw "Source directory not found: $SrcPath"
    }
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Information "   ✅ Python: $pythonVersion"
    } catch {
        throw "Python not found in PATH. Please install Python 3.9+"
    }
    
    # Check pip
    try {
        pip --version | Out-Null
        Write-Information "   ✅ pip available"
    } catch {
        throw "pip not found. Please install pip"
    }
    
    # Check cloud-specific tools
    switch ($CloudProvider) {
        "aws" {
            try {
                aws --version | Out-Null
                Write-Information "   ✅ AWS CLI available"
            } catch {
                throw "AWS CLI not found. Please install AWS CLI v2"
            }
            
            try {
                terraform --version | Out-Null
                Write-Information "   ✅ Terraform available"
            } catch {
                throw "Terraform not found. Please install Terraform"
            }
        }
        "azure" {
            try {
                az --version | Out-Null
                Write-Information "   ✅ Azure CLI available"
            } catch {
                throw "Azure CLI not found. Please install Azure CLI"
            }
        }
        "gcp" {
            try {
                gcloud version | Out-Null
                Write-Information "   ✅ Google Cloud CLI available"
            } catch {
                throw "Google Cloud CLI not found. Please install gcloud"
            }
        }
    }
}

# Create build directories
function Initialize-BuildEnvironment {
    Write-Information "📁 Setting up build environment..."
    
    if (Test-Path $BuildPath) {
        Remove-Item $BuildPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $BuildPath -Force | Out-Null
    
    if (Test-Path $DistPath) {
        Remove-Item $DistPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
    
    Write-Information "   ✅ Build directories created"
}

# Install dependencies
function Install-Dependencies {
    Write-Information "📦 Installing dependencies..."
    
    Push-Location $ProjectRoot
    try {
        # Create virtual environment if it doesn't exist
        if (!(Test-Path "venv")) {
            python -m venv venv
            Write-Information "   ✅ Virtual environment created"
        }
        
        # Activate virtual environment
        & "venv\Scripts\Activate.ps1"
        
        # Upgrade pip
        python -m pip install --upgrade pip
        
        # Install requirements
        if (Test-Path "requirements.txt") {
            pip install -r requirements.txt
            Write-Information "   ✅ Requirements installed"
        }
        
        # Install development dependencies
        if (Test-Path "requirements-dev.txt") {
            pip install -r requirements-dev.txt
            Write-Information "   ✅ Development requirements installed"
        }
        
        # Install project in development mode
        pip install -e .
        Write-Information "   ✅ Project installed in development mode"
        
    } finally {
        Pop-Location
    }
}

# Run tests
function Invoke-Tests {
    if ($SkipTests) {
        Write-Information "⏭️  Skipping tests"
        return
    }
    
    Write-Information "🧪 Running tests..."
    
    Push-Location $ProjectRoot
    try {
        # Activate virtual environment
        & "venv\Scripts\Activate.ps1"
        
        # Run pytest
        $testResult = pytest tests/ -v --tb=short
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed"
        }
        Write-Information "   ✅ All tests passed"
        
    } finally {
        Pop-Location
    }
}

# Build serverless package
function Build-ServerlessPackage {
    if ($SkipBuild -and $DeployOnly) {
        Write-Information "⏭️  Skipping build"
        return
    }
    
    Write-Information "🔨 Building serverless package..."
    
    # Copy source files
    $buildSrcPath = Join-Path $BuildPath "src"
    Copy-Item -Path $SrcPath -Destination $buildSrcPath -Recurse
    Write-Information "   ✅ Source files copied"
    
    # Install production dependencies in build directory
    Push-Location $BuildPath
    try {
        # Create requirements.txt for production
        $prodRequirements = @(
            "dependency-injector",
            "pydantic",
            "typer",
            "pathlib",
            "python-dotenv"
        )
        
        # Add cloud-specific dependencies
        switch ($CloudProvider) {
            "aws" { 
                $prodRequirements += @("boto3", "botocore")
            }
            "azure" { 
                $prodRequirements += @("azure-functions", "azure-servicebus", "azure-storage-blob")
            }
            "gcp" { 
                $prodRequirements += @("functions-framework", "google-cloud-pubsub", "google-cloud-storage")
            }
        }
        
        $prodRequirements | Out-File -FilePath "requirements.txt" -Encoding utf8
        
        # Install dependencies
        pip install -r requirements.txt -t .
        Write-Information "   ✅ Production dependencies installed"
        
        # Remove unnecessary files
        Get-ChildItem -Recurse -Include "*.pyc", "__pycache__", "*.dist-info", "tests" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Information "   ✅ Unnecessary files removed"
        
    } finally {
        Pop-Location
    }
}

# Create deployment package
function New-DeploymentPackage {
    Write-Information "📦 Creating deployment package..."
    
    $packageName = "agentmap-$CloudProvider-$Environment.zip"
    $packagePath = Join-Path $DistPath $packageName
    
    # Create ZIP package
    Push-Location $BuildPath
    try {
        Compress-Archive -Path * -DestinationPath $packagePath -Force
        Write-Information "   ✅ Package created: $packageName"
        
        # Display package size
        $packageSize = [math]::Round((Get-Item $packagePath).Length / 1MB, 2)
        Write-Information "   📏 Package size: $packageSize MB"
        
    } finally {
        Pop-Location
    }
    
    return $packagePath
}

# Deploy to AWS
function Deploy-ToAWS {
    param($PackagePath)
    
    Write-Information "☁️ Deploying to AWS..."
    
    $terraformPath = Join-Path $DeploymentPath "aws" "terraform"
    
    if (!(Test-Path $terraformPath)) {
        throw "Terraform configuration not found: $terraformPath"
    }
    
    # Set default region if not provided
    if (!$Region) {
        $Region = "us-east-1"
    }
    
    Push-Location $terraformPath
    try {
        # Initialize Terraform
        terraform init
        Write-Information "   ✅ Terraform initialized"
        
        # Plan deployment
        $tfVars = @{
            "environment" = $Environment
            "aws_region" = $Region
            "lambda_package_path" = $PackagePath
        }
        
        $tfVarArgs = $tfVars.GetEnumerator() | ForEach-Object { "-var", "$($_.Key)=$($_.Value)" }
        
        terraform plan @tfVarArgs
        Write-Information "   ✅ Terraform plan completed"
        
        # Apply deployment
        terraform apply -auto-approve @tfVarArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Terraform apply failed"
        }
        Write-Information "   ✅ Deployment completed"
        
        # Get outputs
        $apiUrl = terraform output -raw api_gateway_url
        $queueUrl = terraform output -raw sqs_queue_url
        $tableName = terraform output -raw dynamodb_table_name
        $bucketName = terraform output -raw s3_bucket_name
        
        Write-Information ""
        Write-Information "🎉 AWS Deployment Successful!"
        Write-Information "   API Gateway URL: $apiUrl"
        Write-Information "   SQS Queue URL: $queueUrl"
        Write-Information "   DynamoDB Table: $tableName"
        Write-Information "   S3 Bucket: $bucketName"
        
    } finally {
        Pop-Location
    }
}

# Deploy to Azure
function Deploy-ToAzure {
    param($PackagePath)
    
    Write-Information "☁️ Deploying to Azure..."
    
    # Set default region if not provided
    if (!$Region) {
        $Region = "East US"
    }
    
    $resourceGroupName = "agentmap-$Environment-rg"
    $functionAppName = "agentmap-$Environment-func"
    $storageAccountName = "agentmap$Environment$(Get-Random -Maximum 9999)"
    
    try {
        # Create resource group
        az group create --name $resourceGroupName --location $Region
        Write-Information "   ✅ Resource group created: $resourceGroupName"
        
        # Create storage account
        az storage account create --name $storageAccountName --location $Region --resource-group $resourceGroupName --sku Standard_LRS
        Write-Information "   ✅ Storage account created: $storageAccountName"
        
        # Create function app
        az functionapp create --resource-group $resourceGroupName --consumption-plan-location $Region --runtime python --runtime-version 3.9 --functions-version 4 --name $functionAppName --storage-account $storageAccountName
        Write-Information "   ✅ Function app created: $functionAppName"
        
        # Deploy package
        az functionapp deployment source config-zip --resource-group $resourceGroupName --name $functionAppName --src $PackagePath
        Write-Information "   ✅ Package deployed"
        
        # Get function app URL
        $functionAppUrl = az functionapp show --resource-group $resourceGroupName --name $functionAppName --query "defaultHostName" --output tsv
        
        Write-Information ""
        Write-Information "🎉 Azure Deployment Successful!"
        Write-Information "   Function App: https://$functionAppUrl"
        Write-Information "   Resource Group: $resourceGroupName"
        
    } catch {
        Write-Error "Azure deployment failed: $_"
        throw
    }
}

# Deploy to GCP
function Deploy-ToGCP {
    param($PackagePath)
    
    Write-Information "☁️ Deploying to Google Cloud..."
    
    # Set default region if not provided
    if (!$Region) {
        $Region = "us-central1"
    }
    
    $functionName = "agentmap-$Environment"
    $projectId = gcloud config get-value project
    
    if (!$projectId) {
        throw "No GCP project configured. Run: gcloud config set project PROJECT_ID"
    }
    
    try {
        # Extract package for deployment
        $tempDir = Join-Path $env:TEMP "agentmap-gcp-deploy"
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force
        }
        Expand-Archive -Path $PackagePath -DestinationPath $tempDir
        
        Push-Location $tempDir
        try {
            # Create main.py entry point for GCP Functions
            $mainPy = @"
from agentmap.core.handlers.gcp_functions import main

def agentmap_function(request):
    return main(request)
"@
            $mainPy | Out-File -FilePath "main.py" -Encoding utf8
            
            # Deploy function
            gcloud functions deploy $functionName --runtime python39 --trigger-http --allow-unauthenticated --entry-point agentmap_function --region $Region --set-env-vars AGENTMAP_ENVIRONMENT=$Environment
            
            Write-Information "   ✅ Function deployed"
            
            # Get function URL
            $functionUrl = gcloud functions describe $functionName --region $Region --format="value(httpsTrigger.url)"
            
            Write-Information ""
            Write-Information "🎉 GCP Deployment Successful!"
            Write-Information "   Function URL: $functionUrl"
            Write-Information "   Function Name: $functionName"
            
        } finally {
            Pop-Location
            Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        
    } catch {
        Write-Error "GCP deployment failed: $_"
        throw
    }
}

# Test deployment
function Test-Deployment {
    Write-Information "🧪 Testing deployment..."
    
    switch ($CloudProvider) {
        "aws" {
            # Test API Gateway endpoint
            $apiUrl = terraform output -raw api_gateway_url 2>$null
            if ($apiUrl) {
                try {
                    $testPayload = @{
                        action = "info"
                    } | ConvertTo-Json
                    
                    $response = Invoke-RestMethod -Uri "$apiUrl/" -Method POST -Body $testPayload -ContentType "application/json" -TimeoutSec 30
                    if ($response.success) {
                        Write-Information "   ✅ HTTP trigger test passed"
                    }
                } catch {
                    Write-Warning "   ⚠️ HTTP trigger test failed: $_"
                }
            }
        }
        "azure" {
            # Test Azure Function
            Write-Information "   ℹ️ Azure function testing requires manual verification"
        }
        "gcp" {
            # Test GCP Function
            Write-Information "   ℹ️ GCP function testing requires manual verification"
        }
    }
}

# Main deployment flow
function Start-Deployment {
    try {
        Test-Prerequisites
        Initialize-BuildEnvironment
        Install-Dependencies
        Invoke-Tests
        Build-ServerlessPackage
        $packagePath = New-DeploymentPackage
        
        switch ($CloudProvider) {
            "aws" { Deploy-ToAWS -PackagePath $packagePath }
            "azure" { Deploy-ToAzure -PackagePath $packagePath }
            "gcp" { Deploy-ToGCP -PackagePath $packagePath }
        }
        
        Test-Deployment
        
        Write-Information ""
        Write-Information "🎉 Deployment completed successfully!"
        Write-Information "   Package: $packagePath"
        Write-Information "   Environment: $Environment"
        Write-Information "   Cloud Provider: $CloudProvider"
        
    } catch {
        Write-Error "❌ Deployment failed: $_"
        exit 1
    }
}

# Start deployment
Start-Deployment

# Example usage:
# .\deploy.ps1 -CloudProvider aws -Environment dev
# .\deploy.ps1 -CloudProvider azure -Environment staging -Region "West US 2"
# .\deploy.ps1 -CloudProvider gcp -Environment prod -SkipTests