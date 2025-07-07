---
sidebar_position: 5
title: CLI Deployment Guide
description: Complete guide to deploying AgentMap workflows using the command-line interface for development, testing, and production environments
keywords: [CLI deployment, command line deployment, batch processing, automation, development workflow]
---

# CLI Deployment Guide

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>CLI Deployment</strong></span>
</div>

The AgentMap CLI provides a simple, powerful way to deploy and run workflows directly from the command line. This approach is ideal for development, testing, automation scripts, batch processing, and production scenarios that don't require web API interfaces.

## Quick Start

### 1. Installation

```bash
# Basic installation
pip install agentmap

# With additional features
pip install agentmap[all]  # All features
pip install agentmap[llm]  # LLM providers only
pip install agentmap[data] # Data processing features
```

### 2. Create Your First Workflow

```bash
# Create a simple workflow CSV
cat > hello_world.csv << EOF
graph_name,node_nameagent_type,context,description,input_fields,output_field,prompt
HelloWorld,greet,LLMAgent,,Generate greeting,name,greeting,Generate a friendly greeting for {name}
EOF

# Run the workflow
agentmap run --graph HelloWorld --csv hello_world.csv --state '{"name": "World"}'
```

### 3. Validate and Debug

```bash
# Validate workflow structure
agentmap validate-csv --csv hello_world.csv

# Inspect graph structure
agentmap inspect-graph HelloWorld --csv hello_world.csv

# Run with detailed output
agentmap run --graph HelloWorld --csv hello_world.csv --state '{"name": "World"}' --pretty --verbose
```

## Development Workflow

### 📝 Step 1: Design Your Workflow

Create a CSV file defining your workflow:

```csv
graph_name,node_nameagent_type,context,description,input_fields,output_field,Next_Node,prompt
DataPipeline,start,InputAgent,,Get input data,file_path,raw_data,process,
DataPipeline,process,LLMAgent,,Process the data,raw_data,processed_data,save,Analyze and clean this data: {raw_data}
DataPipeline,save,CSVAgent,"{'operation': 'write', 'filename': 'output.csv'}",Save results,processed_data,saved_path,,
```

### 🔍 Step 2: Validate Structure

```bash
# Check CSV syntax and structure
agentmap validate-csv --csv data_pipeline.csv

# Expected output:
# ✅ CSV validation successful
# ✅ Found 3 nodes in workflow
# ✅ All required columns present
# ✅ Graph structure is valid
```

### 🛠️ Step 3: Scaffold Missing Agents

```bash
# Generate custom agent implementations
agentmap scaffold --csv data_pipeline.csv

# Expected output:
# ✅ All agent types available - no scaffolding needed
# OR
# ✅ Generated CustomAgent in agentmap/agents/custom/custom_agent.py
# ℹ️  Edit generated files to implement your logic
```

### ⚡ Step 4: Test Execution

```bash
# Test with sample data
agentmap run --graph DataPipeline --csv data_pipeline.csv --state '{"file_path": "sample.csv"}' --pretty

# Expected output:
# ✅ Graph execution completed successfully
# ================================================================================
# GRAPH EXECUTION SUMMARY
# ================================================================================
# Graph Name: DataPipeline
# Status: COMPLETED
# Success: ✅ Yes
# Total Duration: 2.34 seconds
```

### 🚀 Step 5: Production Deployment

```bash
# Compile for production (optional optimization)
agentmap compile --graph DataPipeline --csv data_pipeline.csv --output ./compiled/

# Run in production
agentmap run --graph DataPipeline --csv data_pipeline.csv --state '{"file_path": "production_data.csv"}' --log-level INFO
```

## Production Deployment Patterns

### 🗂️ File Organization

```
project/
├── workflows/
│   ├── data_pipeline.csv
│   ├── user_onboarding.csv
│   └── analytics.csv
├── custom_agents/
│   ├── __init__.py
│   ├── data_processor.py
│   └── notification_agent.py
├── configs/
│   ├── development.yaml
│   ├── staging.yaml
│   └── production.yaml
├── scripts/
│   ├── deploy.sh
│   ├── validate_all.sh
│   └── run_pipeline.sh
└── logs/
    └── (generated log files)
```

### 🔧 Configuration Management

**agentmap_config.yaml**:
```yaml
# Base configuration
csv_path: "./workflows/"
custom_agents_path: "./custom_agents/"
log_level: "INFO"
max_retries: 3
timeout: 300

# Environment-specific overrides
environments:
  development:
    log_level: "DEBUG"
    timeout: 60
  production:
    log_level: "WARNING"
    enable_metrics: true
    storage:
      backup_enabled: true
```

**Environment Variables**:
```bash
# Production environment
export AGENTMAP_ENV=production
export AGENTMAP_LOG_LEVEL=INFO
export OPENAI_API_KEY=your_api_key
export AGENTMAP_CONFIG_PATH=./configs/production.yaml
```

### 📜 Deployment Scripts

**deploy.sh**:
```bash
#!/bin/bash
set -e

echo "🚀 Deploying AgentMap workflows..."

# Validate all workflows
echo "📋 Validating workflows..."
agentmap validate-all --csv-dir ./workflows/ --warnings-as-errors

# Run tests
echo "🧪 Running tests..."
agentmap run --graph TestSuite --csv ./workflows/tests.csv

# Deploy to production
echo "📦 Deploying to production..."
rsync -av ./workflows/ /opt/agentmap/workflows/
rsync -av ./custom_agents/ /opt/agentmap/custom_agents/
rsync -av ./configs/production.yaml /opt/agentmap/config.yaml

echo "✅ Deployment completed successfully"
```

**run_pipeline.sh**:
```bash
#!/bin/bash
set -e

# Set environment
export AGENTMAP_ENV=production
export AGENTMAP_CONFIG_PATH=/opt/agentmap/config.yaml

# Run with monitoring
agentmap run \
    --graph DataPipeline \
    --csv /opt/agentmap/workflows/data_pipeline.csv \
    --state-file "$1" \
    --log-file /var/log/agentmap/pipeline.log \
    --monitor \
    --pretty

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Pipeline completed successfully"
    exit 0
else
    echo "❌ Pipeline failed"
    exit 1
fi
```

### 🔄 Batch Processing

**Process Multiple Files**:
```bash
#!/bin/bash

# Process all CSV files in a directory
for file in /data/input/*.csv; do
    echo "Processing $file..."
    agentmap run \
        --graph FileProcessor \
        --csv ./workflows/file_processing.csv \
        --state "{\"input_file\": \"$file\"}" \
        --log-level INFO
    
    if [ $? -eq 0 ]; then
        mv "$file" /data/processed/
        echo "✅ Processed: $file"
    else
        mv "$file" /data/failed/
        echo "❌ Failed: $file"
    fi
done
```

**Scheduled Processing**:
```bash
# crontab entry
# Process data every hour
0 * * * * /opt/agentmap/scripts/run_pipeline.sh /data/hourly_data.json

# Generate daily reports
0 6 * * * /opt/agentmap/scripts/generate_report.sh

# Weekly data cleanup
0 2 * * 0 /opt/agentmap/scripts/cleanup_old_data.sh
```

## Advanced CLI Features

### 🎯 Performance Optimization

**Parallel Execution** (when supported):
```bash
# Run multiple workflows concurrently
agentmap run --graph Pipeline1 --csv pipeline1.csv &
agentmap run --graph Pipeline2 --csv pipeline2.csv &
agentmap run --graph Pipeline3 --csv pipeline3.csv &
wait

echo "All pipelines completed"
```

**Memory Optimization**:
```bash
# Limit memory usage
export AGENTMAP_MEMORY_LIMIT=512MB

# Use streaming for large files
agentmap run --graph LargeDataProcessor \
    --csv large_data.csv \
    --state '{"input_file": "large_dataset.csv"}' \
    --streaming \
    --chunk-size 1000
```

### 📊 Monitoring & Logging

**Structured Logging**:
```bash
# JSON formatted logs for log aggregation
agentmap run --graph MyWorkflow \
    --csv workflow.csv \
    --log-format json \
    --log-file /var/log/agentmap/workflow.jsonl
```

**Performance Monitoring**:
```bash
# Profile execution
agentmap run --graph MyWorkflow \
    --csv workflow.csv \
    --profile \
    --metrics-output /var/metrics/workflow_metrics.json
```

**Health Checks**:
```bash
#!/bin/bash
# health_check.sh

# Check system health
agentmap diagnose || exit 1

# Validate critical workflows
agentmap validate-csv --csv /opt/agentmap/workflows/critical.csv || exit 1

# Test connectivity
agentmap run --graph HealthCheck \
    --csv /opt/agentmap/workflows/health.csv \
    --timeout 10 || exit 1

echo "✅ All health checks passed"
```

### 🔐 Security Considerations

**Secure Configuration**:
```bash
# Set secure file permissions
chmod 600 /opt/agentmap/configs/production.yaml
chmod 700 /opt/agentmap/scripts/

# Use encrypted environment variables
export AGENTMAP_ENCRYPTED_CONFIG=true
export AGENTMAP_ENCRYPTION_KEY_FILE=/secure/encryption.key
```

**Input Validation**:
```bash
# Validate input files before processing
agentmap validate-input \
    --file "$INPUT_FILE" \
    --schema /opt/agentmap/schemas/input_schema.json \
    --sanitize

# Only proceed if validation passes
if [ $? -eq 0 ]; then
    agentmap run --graph ProcessData --state "{\"input\": \"$INPUT_FILE\"}"
fi
```

**Audit Logging**:
```bash
# Enable audit logging
export AGENTMAP_AUDIT_LOG=true
export AGENTMAP_AUDIT_LOG_FILE=/var/log/audit/agentmap.log

# Run with full audit trail
agentmap run --graph SensitiveWorkflow \
    --csv sensitive.csv \
    --audit-level full \
    --require-approval
```

## Troubleshooting

### 🔍 Common Issues

**Graph Not Found**:
```bash
# Error: Graph 'MyWorkflow' not found in CSV
# Solution: Check graph name matches CSV
grep "^MyWorkflow," workflow.csv

# Or list available graphs
agentmap list-graphs --csv workflow.csv
```

**Missing Dependencies**:
```bash
# Error: Agent type not resolvable
# Solution: Generate missing agents
agentmap scaffold --csv workflow.csv

# Or check what's missing
agentmap inspect-graph MyWorkflow --csv workflow.csv --resolution
```

**Permission Errors**:
```bash
# Error: Permission denied writing to output
# Solution: Check directory permissions
ls -la /output/directory/
chmod 755 /output/directory/
```

### 🛠️ Debugging Techniques

**Verbose Debugging**:
```bash
# Maximum verbosity
agentmap run --graph MyWorkflow \
    --csv workflow.csv \
    --log-level DEBUG \
    --pretty \
    --verbose \
    --trace-execution
```

**Step-by-Step Execution**:
```bash
# Run single node for testing
agentmap run-node --graph MyWorkflow \
    --node SpecificNode \
    --csv workflow.csv \
    --state '{"input": "test"}'
```

**Configuration Debugging**:
```bash
# Show effective configuration
agentmap config show --effective

# Validate configuration
agentmap config validate

# Test service connections
agentmap test-services
```

## Integration Patterns

### 🏗️ CI/CD Integration

**GitHub Actions**:
```yaml
# .github/workflows/agentmap.yml
name: AgentMap Workflows
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install AgentMap
        run: |
          pip install agentmap[all]
          
      - name: Validate Workflows
        run: |
          agentmap validate-all --csv-dir ./workflows/
          
      - name: Run Tests
        run: |
          agentmap run --graph TestSuite --csv ./workflows/tests.csv
          
      - name: Deploy (if main branch)
        if: github.ref == 'refs/heads/main'
        run: |
          ./scripts/deploy.sh
        env:
          AGENTMAP_ENV: production
```

**Jenkins Pipeline**:
```groovy
pipeline {
    agent any
    
    environment {
        AGENTMAP_ENV = 'production'
        AGENTMAP_LOG_LEVEL = 'INFO'
    }
    
    stages {
        stage('Validate') {
            steps {
                sh 'agentmap validate-all --csv-dir ./workflows/'
            }
        }
        
        stage('Test') {
            steps {
                sh 'agentmap run --graph TestSuite --csv ./workflows/tests.csv'
            }
        }
        
        stage('Deploy') {
            when { branch 'main' }
            steps {
                sh './scripts/deploy.sh'
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'logs/**/*', allowEmptyArchive: true
        }
    }
}
```

### 🐳 Container Deployment

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install AgentMap
RUN pip install agentmap[all]

# Copy application files
WORKDIR /app
COPY workflows/ ./workflows/
COPY custom_agents/ ./custom_agents/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Set permissions
RUN chmod +x ./scripts/*.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD agentmap diagnose || exit 1

# Default command
CMD ["./scripts/run_pipeline.sh"]
```

**Docker Compose**:
```yaml
# docker-compose.yml
version: '3.8'

services:
  agentmap:
    build: .
    environment:
      - AGENTMAP_ENV=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    
  redis:
    image: redis:alpine
    restart: unless-stopped
    
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

## Performance Tuning

### ⚡ Optimization Strategies

**1. Workflow Design**:
```csv
# Good: Minimize agent switching
graph_name,node_nameagent_type,description
Pipeline,Batch1,LLMAgent,Process items 1-100
Pipeline,Batch2,LLMAgent,Process items 101-200
Pipeline,Save,CSVAgent,Save all results

# Avoid: Frequent agent switching
graph_name,node_nameagent_type,description
Pipeline,Process1,LLMAgent,Process item 1
Pipeline,Save1,CSVAgent,Save item 1
Pipeline,Process2,LLMAgent,Process item 2
Pipeline,Save2,CSVAgent,Save item 2
```

**2. Resource Management**:
```bash
# Set resource limits
export AGENTMAP_MAX_MEMORY=1GB
export AGENTMAP_MAX_CPU_PERCENT=80
export AGENTMAP_PARALLEL_AGENTS=4

# Enable caching
export AGENTMAP_ENABLE_CACHE=true
export AGENTMAP_CACHE_SIZE=100MB
```

**3. Network Optimization**:
```yaml
# agentmap_config.yaml
network:
  connection_pool_size: 20
  request_timeout: 30
  retry_attempts: 3
  backoff_factor: 1.5
  
llm:
  batch_requests: true
  max_batch_size: 10
  request_interval: 0.1
```

### 📈 Performance Monitoring

**Metrics Collection**:
```bash
# Enable detailed metrics
agentmap run --graph MyWorkflow \
    --csv workflow.csv \
    --collect-metrics \
    --metrics-interval 5 \
    --metrics-output /var/metrics/

# Monitor resource usage
agentmap monitor --graph MyWorkflow \
    --interval 10 \
    --alert-thresholds memory:80%,cpu:90%
```

**Performance Analysis**:
```bash
# Generate performance report
agentmap analyze-performance \
    --metrics-dir /var/metrics/ \
    --output performance_report.html \
    --include-recommendations
```

## Next Steps

- **[CLI Commands Reference](deployment/cli-commands)**: Complete CLI command documentation
- **[CLI Graph Inspector](deployment/cli-graph-inspector)**: Advanced debugging and validation
- **[Configuration Reference](./configuration)**: Detailed configuration options
- **[FastAPI Deployment](./fastapi-standalone)**: Web API deployment option
- **[Monitoring Guide](./monitoring)**: Production monitoring and observability

## Related Resources

- **[Learning Guides](/docs/guides/learning/)**: Step-by-step tutorials
- **[Agent Development](/docs/guides/development/agents/agent-development)**: Custom agent creation
- **[Example Workflows](/docs/templates/)**: Real-world usage patterns
- **[Troubleshooting](./troubleshooting)**: Common issues and solutions
