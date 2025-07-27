---
title: System Health Monitoring
sidebar_position: 9
description: Production system health monitoring, dependency tracking, and operational procedures for AgentMap deployments
keywords: [system health, monitoring, production, operations, dependency tracking, alerting, maintenance]
---

# System Health Monitoring

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <strong>System Health</strong></span>
</div>

This guide covers comprehensive system health monitoring for AgentMap production deployments, including dependency tracking, performance monitoring, and operational procedures using AgentMap's built-in diagnostic capabilities.

## Health Monitoring Architecture

### Health Check Components

AgentMap provides multiple layers of health monitoring:

1. **Dependency Health**: LLM and storage provider availability
2. **Registry Health**: Features registry consistency and synchronization
3. **Cache Health**: Validation cache performance and integrity
4. **System Health**: Environment, configuration, and resource status
5. **Graph Health**: Workflow-specific dependency and execution status

### Monitoring Services

**DependencyCheckerService**: Provides technical validation and health status
**FeaturesRegistryService**: Maintains provider availability and feature status
**ValidationCacheService**: Manages cache performance and integrity
**GraphRunnerService**: Provides workflow execution health data

## Basic Health Checks

### Manual Health Verification

```bash
# Comprehensive system health check
agentmap diagnose

# Cache health verification
agentmap validate-cache --stats

# Graph-specific health check
agentmap inspect-graph ProductionWorkflow --resolution

# Configuration validation
agentmap config
```

### Automated Health Check Script

```bash
#!/bin/bash
# health_check.sh - Basic health monitoring script

set -e

LOG_FILE="/var/log/agentmap/health_check.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting AgentMap health check..." | tee -a "$LOG_FILE"

# 1. Basic system diagnostics
echo "[$TIMESTAMP] Running system diagnostics..." | tee -a "$LOG_FILE"
if ! agentmap diagnose >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] ERROR: System diagnostics failed" | tee -a "$LOG_FILE"
    exit 1
fi

# 2. Check for critical LLM availability
echo "[$TIMESTAMP] Checking LLM provider availability..." | tee -a "$LOG_FILE"
if agentmap diagnose | grep -q "LLM feature enabled: False"; then
    echo "[$TIMESTAMP] CRITICAL: LLM feature disabled" | tee -a "$LOG_FILE"
    exit 2
fi

# 3. Check dependency count
echo "[$TIMESTAMP] Checking dependency availability..." | tee -a "$LOG_FILE"
missing_deps=$(agentmap diagnose | grep -c "Not available" || true)
if [ "$missing_deps" -gt 5 ]; then
    echo "[$TIMESTAMP] WARNING: Multiple dependencies missing ($missing_deps)" | tee -a "$LOG_FILE"
    exit 1
fi

# 4. Check cache health
echo "[$TIMESTAMP] Checking cache health..." | tee -a "$LOG_FILE"
corrupted_files=$(agentmap validate-cache --stats | grep "Corrupted files:" | awk '{print $3}' || echo "0")
if [ "$corrupted_files" -gt 0 ]; then
    echo "[$TIMESTAMP] WARNING: $corrupted_files corrupted cache files" | tee -a "$LOG_FILE"
    agentmap validate-cache --cleanup
fi

echo "[$TIMESTAMP] Health check completed successfully" | tee -a "$LOG_FILE"
exit 0
```

## Production Health Monitoring

### Continuous Monitoring Service

```python
#!/usr/bin/env python3
# agentmap_monitor.py - Continuous health monitoring service

import time
import json
import logging
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional
from agentmap.core.cli.diagnostic_commands import diagnose_command, cache_info_command

@dataclass
class HealthMetrics:
    timestamp: datetime
    llm_providers_available: int
    storage_providers_available: int
    registry_inconsistencies: int
    cache_corrupted_files: int
    cache_expired_files: int
    total_dependencies_missing: int
    critical_errors: List[str]
    warnings: List[str]

class AgentMapHealthMonitor:
    def __init__(self, check_interval: int = 300, log_file: str = "/var/log/agentmap/monitor.log"):
        self.check_interval = check_interval
        self.logger = self._setup_logging(log_file)
        self.previous_metrics: Optional[HealthMetrics] = None
        
    def _setup_logging(self, log_file: str) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('AgentMapMonitor')
    
    def collect_metrics(self) -> HealthMetrics:
        \"\"\"Collect current health metrics.\"\"\"
        try:
            # Get diagnostic data
            diagnostic_data = diagnose_command()
            cache_data = cache_info_command()
            
            # Count available providers
            llm_available = sum(1 for provider in diagnostic_data['llm'].values() 
                              if provider['available'])
            storage_available = sum(1 for provider in diagnostic_data['storage'].values() 
                                  if provider['available'])
            
            # Count registry inconsistencies
            registry_inconsistencies = 0
            for category in ['llm', 'storage']:
                for provider, status in diagnostic_data[category].items():
                    if status['has_dependencies'] and not status['available']:
                        registry_inconsistencies += 1
            
            # Get cache metrics
            cache_stats = cache_data['cache_statistics']
            
            # Count total missing dependencies
            total_missing = sum(len(provider['missing_dependencies']) 
                              for provider in diagnostic_data['llm'].values())
            total_missing += sum(len(provider['missing_dependencies']) 
                               for provider in diagnostic_data['storage'].values())
            
            # Identify critical errors and warnings
            critical_errors = []
            warnings = []
            
            if llm_available == 0:
                critical_errors.append("No LLM providers available")
            
            if registry_inconsistencies > 0:
                warnings.append(f"{registry_inconsistencies} registry inconsistencies detected")
            
            if cache_stats['corrupted_files'] > 0:
                warnings.append(f"{cache_stats['corrupted_files']} corrupted cache files")
            
            if cache_stats['expired_files'] > 10:
                warnings.append(f"{cache_stats['expired_files']} expired cache files")
            
            return HealthMetrics(
                timestamp=datetime.now(),
                llm_providers_available=llm_available,
                storage_providers_available=storage_available,
                registry_inconsistencies=registry_inconsistencies,
                cache_corrupted_files=cache_stats['corrupted_files'],
                cache_expired_files=cache_stats['expired_files'],
                total_dependencies_missing=total_missing,
                critical_errors=critical_errors,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
            return HealthMetrics(
                timestamp=datetime.now(),
                llm_providers_available=0,
                storage_providers_available=0,
                registry_inconsistencies=0,
                cache_corrupted_files=0,
                cache_expired_files=0,
                total_dependencies_missing=0,
                critical_errors=[f"Metric collection failed: {e}"],
                warnings=[]
            )
    
    def check_health_changes(self, current: HealthMetrics, previous: HealthMetrics) -> None:
        \"\"\"Check for significant health changes and alert.\"\"\"
        
        # Check for provider availability changes
        if current.llm_providers_available != previous.llm_providers_available:
            self.logger.warning(f"LLM provider availability changed: "
                              f"{previous.llm_providers_available} → {current.llm_providers_available}")
        
        if current.storage_providers_available != previous.storage_providers_available:
            self.logger.warning(f"Storage provider availability changed: "
                              f"{previous.storage_providers_available} → {current.storage_providers_available}")
        
        # Check for new critical errors
        new_errors = set(current.critical_errors) - set(previous.critical_errors)
        if new_errors:
            for error in new_errors:
                self.logger.critical(f"NEW CRITICAL ERROR: {error}")
        
        # Check for resolved errors
        resolved_errors = set(previous.critical_errors) - set(current.critical_errors)
        if resolved_errors:
            for error in resolved_errors:
                self.logger.info(f"RESOLVED: {error}")
    
    def log_metrics(self, metrics: HealthMetrics) -> None:
        \"\"\"Log current metrics.\"\"\"
        self.logger.info(f"Health Status: "
                        f"LLM={metrics.llm_providers_available}, "
                        f"Storage={metrics.storage_providers_available}, "
                        f"Inconsistencies={metrics.registry_inconsistencies}, "
                        f"CacheCorrupted={metrics.cache_corrupted_files}")
        
        # Log critical errors
        for error in metrics.critical_errors:
            self.logger.critical(error)
        
        # Log warnings
        for warning in metrics.warnings:
            self.logger.warning(warning)
    
    def perform_maintenance(self, metrics: HealthMetrics) -> None:
        \"\"\"Perform automatic maintenance tasks.\"\"\"
        
        # Clean up expired cache files if too many
        if metrics.cache_expired_files > 20:
            self.logger.info(f"Cleaning up {metrics.cache_expired_files} expired cache files")
            try:
                subprocess.run(["agentmap", "validate-cache", "--cleanup"], check=True)
                self.logger.info("Cache cleanup completed")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Cache cleanup failed: {e}")
        
        # Clear corrupted cache files
        if metrics.cache_corrupted_files > 0:
            self.logger.info(f"Clearing {metrics.cache_corrupted_files} corrupted cache files")
            try:
                subprocess.run(["agentmap", "validate-cache", "--clear"], check=True)
                self.logger.info("Corrupted cache cleared")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Cache clear failed: {e}")
    
    def run(self) -> None:
        \"\"\"Run continuous monitoring.\"\"\"
        self.logger.info(f"Starting AgentMap health monitoring (interval: {self.check_interval}s)")
        
        while True:
            try:
                current_metrics = self.collect_metrics()
                
                # Log current metrics
                self.log_metrics(current_metrics)
                
                # Check for changes if we have previous metrics
                if self.previous_metrics:
                    self.check_health_changes(current_metrics, self.previous_metrics)
                
                # Perform maintenance if needed
                self.perform_maintenance(current_metrics)
                
                # Store current metrics for next comparison
                self.previous_metrics = current_metrics
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    monitor = AgentMapHealthMonitor(check_interval=300)  # 5 minutes
    monitor.run()
```

## Monitoring Integration

### Prometheus Integration

```python
# agentmap_prometheus_exporter.py
from prometheus_client import Gauge, Counter, start_http_server, generate_latest
from agentmap.core.cli.diagnostic_commands import diagnose_command, cache_info_command
import time
import threading

# Define metrics
llm_providers_available = Gauge('agentmap_llm_providers_available', 'Number of available LLM providers')
storage_providers_available = Gauge('agentmap_storage_providers_available', 'Number of available storage providers')
registry_inconsistencies = Gauge('agentmap_registry_inconsistencies', 'Number of registry inconsistencies')
cache_corrupted_files = Gauge('agentmap_cache_corrupted_files', 'Number of corrupted cache files')
cache_expired_files = Gauge('agentmap_cache_expired_files', 'Number of expired cache files')
dependency_check_errors = Counter('agentmap_dependency_check_errors_total', 'Total dependency check errors')
provider_availability = Gauge('agentmap_provider_availability', 'Provider availability status', ['category', 'provider'])

def collect_metrics():
    \"\"\"Collect AgentMap metrics for Prometheus.\"\"\"
    try:
        # Get diagnostic data
        diagnostic_data = diagnose_command()
        cache_data = cache_info_command()
        
        # Update LLM and storage provider counts
        llm_available = sum(1 for provider in diagnostic_data['llm'].values() if provider['available'])
        storage_available = sum(1 for provider in diagnostic_data['storage'].values() if provider['available'])
        
        llm_providers_available.set(llm_available)
        storage_providers_available.set(storage_available)
        
        # Update provider-specific metrics
        for category in ['llm', 'storage']:
            for provider, status in diagnostic_data[category].items():
                provider_availability.labels(category=category, provider=provider).set(
                    1 if status['available'] else 0
                )
        
        # Count registry inconsistencies
        inconsistencies = 0
        for category in ['llm', 'storage']:
            for provider, status in diagnostic_data[category].items():
                if status['has_dependencies'] and not status['available']:
                    inconsistencies += 1
        
        registry_inconsistencies.set(inconsistencies)
        
        # Update cache metrics
        cache_stats = cache_data['cache_statistics']
        cache_corrupted_files.set(cache_stats['corrupted_files'])
        cache_expired_files.set(cache_stats['expired_files'])
        
    except Exception as e:
        dependency_check_errors.inc()
        print(f"Error collecting metrics: {e}")

def metrics_collector():
    \"\"\"Background thread to collect metrics.\"\"\"
    while True:
        collect_metrics()
        time.sleep(60)  # Collect every minute

if __name__ == "__main__":
    # Start metrics collection in background
    collector_thread = threading.Thread(target=metrics_collector)
    collector_thread.daemon = True
    collector_thread.start()
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    print("AgentMap Prometheus exporter running on port 8000")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exporter stopped")
```

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "AgentMap System Health",
    "panels": [
      {
        "title": "LLM Provider Availability",
        "type": "stat",
        "targets": [
          {
            "expr": "agentmap_llm_providers_available",
            "legendFormat": "Available Providers"
          }
        ]
      },
      {
        "title": "Provider Availability by Type",
        "type": "table",
        "targets": [
          {
            "expr": "agentmap_provider_availability",
            "legendFormat": "{{category}}.{{provider}}"
          }
        ]
      },
      {
        "title": "Registry Inconsistencies",
        "type": "graph",
        "targets": [
          {
            "expr": "agentmap_registry_inconsistencies",
            "legendFormat": "Inconsistencies"
          }
        ]
      },
      {
        "title": "Cache Health",
        "type": "graph",
        "targets": [
          {
            "expr": "agentmap_cache_corrupted_files",
            "legendFormat": "Corrupted Files"
          },
          {
            "expr": "agentmap_cache_expired_files", 
            "legendFormat": "Expired Files"
          }
        ]
      }
    ]
  }
}
```

### Nagios/Icinga Integration

```bash
#!/bin/bash
# check_agentmap.sh - Nagios/Icinga check plugin

# Exit codes
OK=0
WARNING=1
CRITICAL=2
UNKNOWN=3

# Thresholds
WARNING_MISSING_DEPS=3
CRITICAL_MISSING_DEPS=8
WARNING_CORRUPTED_CACHE=1
CRITICAL_CORRUPTED_CACHE=5

# Temporary files
DIAG_OUTPUT=$(mktemp)
CACHE_OUTPUT=$(mktemp)

# Cleanup on exit
trap "rm -f $DIAG_OUTPUT $CACHE_OUTPUT" EXIT

# Run diagnostics
if ! agentmap diagnose > "$DIAG_OUTPUT" 2>&1; then
    echo "UNKNOWN - Failed to run agentmap diagnose"
    exit $UNKNOWN
fi

if ! agentmap validate-cache --stats > "$CACHE_OUTPUT" 2>&1; then
    echo "UNKNOWN - Failed to run cache validation"
    exit $UNKNOWN
fi

# Check for critical failures
if grep -q "LLM feature enabled: False" "$DIAG_OUTPUT"; then
    echo "CRITICAL - LLM feature disabled"
    exit $CRITICAL
fi

# Count missing dependencies
missing_deps=$(grep -c "Not available" "$DIAG_OUTPUT" || echo "0")

# Check cache corruption
corrupted_files=$(grep "Corrupted files:" "$CACHE_OUTPUT" | awk '{print $3}' || echo "0")

# Determine exit status
exit_code=$OK
status_msg="OK"

if [ "$missing_deps" -ge $CRITICAL_MISSING_DEPS ]; then
    exit_code=$CRITICAL
    status_msg="CRITICAL"
elif [ "$missing_deps" -ge $WARNING_MISSING_DEPS ]; then
    exit_code=$WARNING
    status_msg="WARNING"
fi

if [ "$corrupted_files" -ge $CRITICAL_CORRUPTED_CACHE ]; then
    exit_code=$CRITICAL
    status_msg="CRITICAL"
elif [ "$corrupted_files" -ge $WARNING_CORRUPTED_CACHE ]; then
    if [ $exit_code -eq $OK ]; then
        exit_code=$WARNING
        status_msg="WARNING"
    fi
fi

# Output status message
echo "$status_msg - Missing deps: $missing_deps, Corrupted cache: $corrupted_files"
exit $exit_code
```

## Health Check Automation

### Systemd Service

```ini
# /etc/systemd/system/agentmap-monitor.service
[Unit]
Description=AgentMap Health Monitor
After=network.target

[Service]
Type=simple
User=agentmap
Group=agentmap
WorkingDirectory=/opt/agentmap
ExecStart=/usr/local/bin/python3 /opt/agentmap/agentmap_monitor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment variables
Environment=PYTHONPATH=/opt/agentmap
Environment=AGENTMAP_CONFIG_PATH=/etc/agentmap/config.yaml

[Install]
WantedBy=multi-user.target
```

### Cron-Based Health Checks

```bash
# /etc/cron.d/agentmap-health
# Run health check every 5 minutes
*/5 * * * * agentmap /opt/agentmap/health_check.sh

# Run deep health analysis hourly
0 * * * * agentmap /opt/agentmap/deep_health_check.sh

# Daily cache maintenance
0 2 * * * agentmap /usr/local/bin/agentmap validate-cache --cleanup

# Weekly dependency report
0 0 * * 0 agentmap /opt/agentmap/weekly_dependency_report.sh
```

### Docker Health Checks

```dockerfile
# Dockerfile with comprehensive health checks
FROM python:3.11-slim

# Install AgentMap
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy health check scripts
COPY health_check.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/health_check.sh

# Multi-stage health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /usr/local/bin/health_check.sh || exit 1

# Secondary health check for deep validation
HEALTHCHECK --interval=300s --timeout=30s --start-period=30s --retries=2 \
    CMD agentmap diagnose --quiet && agentmap validate-cache --stats || exit 1

COPY . /app
WORKDIR /app

CMD ["python", "app.py"]
```

## Performance Monitoring

### Performance Metrics Collection

```python
# performance_monitor.py
import time
import psutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    timestamp: float
    diagnose_duration: float
    cache_stats_duration: float
    memory_usage_mb: float
    cpu_percent: float
    disk_usage_percent: float

class PerformanceMonitor:
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
    
    def measure_command_performance(self, command: List[str]) -> float:
        \"\"\"Measure execution time of a command.\"\"\"
        start_time = time.time()
        try:
            subprocess.run(command, capture_output=True, check=True)
            return time.time() - start_time
        except subprocess.CalledProcessError:
            return -1  # Indicate failure
    
    def collect_system_metrics(self) -> PerformanceMetrics:
        \"\"\"Collect system performance metrics.\"\"\"
        
        # Measure AgentMap command performance
        diagnose_time = self.measure_command_performance(["agentmap", "diagnose"])
        cache_time = self.measure_command_performance(["agentmap", "validate-cache", "--stats"])
        
        # Collect system metrics
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage('/')
        
        return PerformanceMetrics(
            timestamp=time.time(),
            diagnose_duration=diagnose_time,
            cache_stats_duration=cache_time,
            memory_usage_mb=memory.used / 1024 / 1024,
            cpu_percent=cpu_percent,
            disk_usage_percent=disk.percent
        )
    
    def analyze_performance_trends(self) -> Dict[str, float]:
        \"\"\"Analyze performance trends over time.\"\"\"
        if len(self.metrics_history) < 2:
            return {}
        
        recent = self.metrics_history[-10:]  # Last 10 measurements
        
        avg_diagnose_time = sum(m.diagnose_duration for m in recent if m.diagnose_duration > 0) / len(recent)
        avg_cache_time = sum(m.cache_stats_duration for m in recent if m.cache_stats_duration > 0) / len(recent)
        avg_memory = sum(m.memory_usage_mb for m in recent) / len(recent)
        
        return {
            "avg_diagnose_duration": avg_diagnose_time,
            "avg_cache_duration": avg_cache_time,
            "avg_memory_usage_mb": avg_memory,
            "trend_diagnose": self._calculate_trend([m.diagnose_duration for m in recent]),
            "trend_memory": self._calculate_trend([m.memory_usage_mb for m in recent])
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        \"\"\"Calculate trend direction (increasing, decreasing, stable).\"\"\"
        if len(values) < 2:
            return "unknown"
        
        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        change_percent = ((second_half - first_half) / first_half) * 100
        
        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"
```

## Alerting and Notifications

### Slack Integration

```python
# slack_alerts.py
import requests
import json
from typing import Dict, List

class SlackAlerter:
    def __init__(self, webhook_url: str, channel: str = "#ops"):
        self.webhook_url = webhook_url
        self.channel = channel
    
    def send_health_alert(self, severity: str, message: str, metrics: Dict = None) -> None:
        \"\"\"Send health alert to Slack.\"\"\"
        
        color_map = {
            "critical": "danger",
            "warning": "warning", 
            "info": "good"
        }
        
        payload = {
            "channel": self.channel,
            "username": "AgentMap Monitor",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color_map.get(severity, "warning"),
                    "title": f"AgentMap {severity.upper()} Alert",
                    "text": message,
                    "timestamp": int(time.time())
                }
            ]
        }
        
        if metrics:
            fields = []
            for key, value in metrics.items():
                fields.append({
                    "title": key.replace('_', ' ').title(),
                    "value": str(value),
                    "short": True
                })
            payload["attachments"][0]["fields"] = fields
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to send Slack alert: {e}")
    
    def send_dependency_change_alert(self, provider: str, category: str, 
                                   old_status: bool, new_status: bool) -> None:
        \"\"\"Send provider availability change alert.\"\"\"
        
        status_text = "became available" if new_status else "became unavailable"
        severity = "info" if new_status else "warning"
        
        message = f"Provider {category}.{provider} {status_text}"
        
        self.send_health_alert(severity, message, {
            "Provider": provider,
            "Category": category,
            "Previous Status": "Available" if old_status else "Unavailable",
            "New Status": "Available" if new_status else "Unavailable"
        })
```

### Email Notifications

```python
# email_alerts.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List

class EmailAlerter:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_health_report(self, recipients: List[str], subject: str, 
                          metrics: Dict, critical_errors: List[str], 
                          warnings: List[str]) -> None:
        \"\"\"Send comprehensive health report via email.\"\"\"
        
        # Create HTML email content
        html_content = f\"\"\"
        <html>
        <body>
        <h2>AgentMap Health Report</h2>
        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h3>System Status</h3>
        <table border="1" style="border-collapse: collapse;">
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>LLM Providers Available</td><td>{metrics.get('llm_providers_available', 'N/A')}</td></tr>
        <tr><td>Storage Providers Available</td><td>{metrics.get('storage_providers_available', 'N/A')}</td></tr>
        <tr><td>Registry Inconsistencies</td><td>{metrics.get('registry_inconsistencies', 'N/A')}</td></tr>
        <tr><td>Cache Corrupted Files</td><td>{metrics.get('cache_corrupted_files', 'N/A')}</td></tr>
        </table>
        \"\"\"
        
        if critical_errors:
            html_content += \"\"\"
            <h3 style="color: red;">Critical Errors</h3>
            <ul>
            \"\"\"
            for error in critical_errors:
                html_content += f"<li>{error}</li>"
            html_content += "</ul>"
        
        if warnings:
            html_content += \"\"\"
            <h3 style="color: orange;">Warnings</h3>
            <ul>
            \"\"\"
            for warning in warnings:
                html_content += f"<li>{warning}</li>"
            html_content += "</ul>"
        
        html_content += \"\"\"
        </body>
        </html>
        \"\"\"
        
        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.username
        msg['To'] = ', '.join(recipients)
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")
```

## Maintenance Procedures

### Automated Maintenance Tasks

```python
# maintenance.py
import subprocess
import logging
from datetime import datetime, timedelta
from agentmap.core.cli.diagnostic_commands import cache_info_command

class MaintenanceManager:
    def __init__(self, log_file: str = "/var/log/agentmap/maintenance.log"):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('MaintenanceManager')
    
    def cache_maintenance(self) -> Dict[str, int]:
        \"\"\"Perform cache maintenance tasks.\"\"\"
        self.logger.info("Starting cache maintenance")
        
        # Get current cache stats
        cache_data = cache_info_command()
        stats = cache_data['cache_statistics']
        
        results = {
            "expired_cleaned": 0,
            "corrupted_cleared": 0,
            "total_files_before": stats['total_files']
        }
        
        # Clean expired files if more than 10
        if stats['expired_files'] > 10:
            self.logger.info(f"Cleaning {stats['expired_files']} expired cache files")
            try:
                result = subprocess.run(
                    ["agentmap", "validate-cache", "--cleanup"], 
                    capture_output=True, text=True, check=True
                )
                results["expired_cleaned"] = stats['expired_files']
                self.logger.info("Cache cleanup completed successfully")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Cache cleanup failed: {e}")
        
        # Clear corrupted files if any exist
        if stats['corrupted_files'] > 0:
            self.logger.info(f"Clearing {stats['corrupted_files']} corrupted cache files")
            try:
                result = subprocess.run(
                    ["agentmap", "validate-cache", "--clear"], 
                    capture_output=True, text=True, check=True
                )
                results["corrupted_cleared"] = stats['corrupted_files']
                self.logger.info("Corrupted cache cleared successfully")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Cache clear failed: {e}")
        
        return results
    
    def dependency_refresh(self) -> bool:
        \"\"\"Force refresh of dependency validation.\"\"\"
        self.logger.info("Refreshing dependency validation")
        
        try:
            from agentmap.di import initialize_di
            container = initialize_di()
            checker = container.dependency_checker_service()
            
            # Re-validate all LLM dependencies
            for provider in ["openai", "anthropic", "google"]:
                has_deps, missing = checker.check_llm_dependencies(provider)
                self.logger.debug(f"Validated {provider}: {has_deps}, missing: {missing}")
            
            # Re-validate all storage dependencies  
            for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
                has_deps, missing = checker.check_storage_dependencies(storage_type)
                self.logger.debug(f"Validated {storage_type}: {has_deps}, missing: {missing}")
            
            self.logger.info("Dependency refresh completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Dependency refresh failed: {e}")
            return False
    
    def system_health_report(self) -> Dict:
        \"\"\"Generate comprehensive system health report.\"\"\"
        self.logger.info("Generating system health report")
        
        try:
            # Run full diagnostics
            result = subprocess.run(
                ["agentmap", "diagnose"], 
                capture_output=True, text=True, check=True
            )
            
            # Parse diagnostic output for key metrics
            output = result.stdout
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "llm_feature_enabled": "LLM feature enabled: True" in output,
                "storage_feature_enabled": "Storage feature enabled: True" in output,
                "providers_unavailable": output.count("Not available"),
                "registry_inconsistencies": output.count("Registration issue"),
                "diagnostic_output": output
            }
            
            self.logger.info(f"Health report generated: {report['providers_unavailable']} providers unavailable")
            return report
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Health report generation failed: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def weekly_maintenance(self) -> Dict:
        \"\"\"Perform comprehensive weekly maintenance.\"\"\"
        self.logger.info("Starting weekly maintenance")
        
        results = {
            "cache_maintenance": self.cache_maintenance(),
            "dependency_refresh": self.dependency_refresh(),
            "health_report": self.system_health_report()
        }
        
        self.logger.info("Weekly maintenance completed")
        return results

if __name__ == "__main__":
    manager = MaintenanceManager()
    results = manager.weekly_maintenance()
    print(json.dumps(results, indent=2, default=str))
```

## Best Practices

### Production Health Monitoring Checklist

1. **Continuous Monitoring**
   - [ ] Health check service running continuously
   - [ ] Metrics exported to monitoring system (Prometheus/Grafana)
   - [ ] Alerting configured for critical failures
   - [ ] Log aggregation configured

2. **Dependency Management**
   - [ ] Regular dependency validation (every 5 minutes)
   - [ ] Registry inconsistency monitoring
   - [ ] Provider availability tracking
   - [ ] Installation suggestion monitoring

3. **Cache Management**
   - [ ] Cache health monitoring
   - [ ] Automatic expired file cleanup
   - [ ] Corrupted file detection and clearing
   - [ ] Cache performance tracking

4. **System Resources**
   - [ ] Memory usage monitoring
   - [ ] Disk usage tracking
   - [ ] CPU utilization monitoring
   - [ ] Network connectivity validation

5. **Alerting and Response**
   - [ ] Critical error alerting (Slack/email)
   - [ ] Provider availability change notifications
   - [ ] Performance degradation alerts
   - [ ] Automated maintenance procedures

### Health Monitoring Configuration

```yaml
# health_monitoring.yaml - Example configuration
monitoring:
  enabled: true
  check_interval: 300  # 5 minutes
  
  thresholds:
    critical:
      llm_providers_unavailable: 0
      missing_dependencies: 8
      registry_inconsistencies: 5
      cache_corrupted_files: 5
    
    warning:
      missing_dependencies: 3
      cache_expired_files: 20
      registry_inconsistencies: 1
      cache_corrupted_files: 1
  
  alerts:
    slack:
      enabled: true
      webhook_url: "env:SLACK_WEBHOOK_URL"
      channel: "#ops-alerts"
    
    email:
      enabled: true
      smtp_server: "smtp.company.com"
      recipients: ["ops@company.com", "devs@company.com"]
  
  maintenance:
    cache_cleanup:
      enabled: true
      schedule: "0 2 * * *"  # Daily at 2 AM
      expired_threshold: 10
    
    dependency_refresh:
      enabled: true
      schedule: "0 */6 * * *"  # Every 6 hours
    
    health_report:
      enabled: true
      schedule: "0 8 * * 1"  # Weekly on Monday at 8 AM
```

## Related Documentation

### 🔧 **Diagnostic Tools**
- **[Diagnostic Commands](/docs/deployment/cli-diagnostics)**: Complete diagnostic command reference
- **[CLI Commands](/docs/deployment/cli-commands)**: All command-line tools
- **[Dependency Management](/docs/guides/dependency-management)**: Comprehensive dependency management

### 🏗️ **Operations**
- **[Troubleshooting Guide](/docs/guides/troubleshooting)**: Detailed issue resolution
- **[Configuration Reference](/docs/reference/configuration/)**: Complete configuration options
- **[Production Deployment](/docs/deployment/)**: Production deployment strategies

### 🚀 **Advanced Topics**
- **[Service Architecture](/docs/reference/services/)**: Understanding services and protocols
- **[Performance Optimization](/docs/guides/performance/)**: Performance tuning and optimization
- **[Security Guidelines](/docs/guides/security/)**: Security best practices
