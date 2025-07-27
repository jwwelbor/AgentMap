---
sidebar_position: 1
title: Cache Management & System Administration
description: Administrative guide for AgentMap cache management, system maintenance, and performance optimization
keywords: [cache administration, system maintenance, performance optimization, cache cleanup, monitoring]
---

# Cache Management & System Administration

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/guides">Guides</a> → <a href="/docs/guides/administration">Administration</a> → <strong>Cache Management</strong></span>
</div>

This guide provides comprehensive administrative procedures for managing AgentMap's cache systems, including validation cache, system performance optimization, and maintenance workflows.

## Administrative Overview

### Cache System Architecture

AgentMap implements a sophisticated caching system with multiple components:

- **Validation Cache**: Stores CSV and configuration validation results
- **File Hash Cache**: MD5-based change detection for automatic invalidation
- **Performance Cache**: System-level performance optimizations
- **Temporary Cache**: Short-lived cache for active sessions

### Cache Storage Locations

```bash
# Primary cache directory
~/.agentmap/validation_cache/

# System cache (if applicable)
/tmp/agentmap_cache/

# Application cache
~/.agentmap/app_cache/
```

### Administrative Responsibilities

- **Cache Health Monitoring**: Regular cache statistics review
- **Storage Management**: Disk space monitoring and cleanup
- **Performance Optimization**: Cache hit rate analysis and tuning
- **Maintenance Scheduling**: Automated and manual cache maintenance
- **Troubleshooting**: Cache-related issue resolution

## Cache Administration Commands

### System-Wide Cache Statistics

Monitor cache health across the entire system:

```bash
# Comprehensive cache statistics
agentmap validate-cache --stats

# System-wide cache analysis
agentmap validate-cache --stats --verbose

# JSON output for monitoring tools
agentmap validate-cache --stats --format json
```

**Sample Administrative Output**:
```
🔧 AgentMap Cache Administration Report
==========================================

📊 Cache Statistics:
- Total cache entries: 247
- Valid cache entries: 198 (80.16%)
- Expired cache entries: 34 (13.77%)
- Corrupted cache entries: 15 (6.07%)

💾 Storage Usage:
- Cache directory: ~/.agentmap/validation_cache
- Total cache size: 1.2 MB
- Average file size: 4.9 KB
- Disk space available: 45.2 GB

⚡ Performance Metrics:
- Cache hit rate (24h): 87.3%
- Average cache access time: 12ms
- Average validation time: 234ms
- Performance improvement: 19.5x

🕒 Cache Age Distribution:
- < 1 hour: 45 files (18.2%)
- 1-6 hours: 89 files (36.0%)
- 6-24 hours: 64 files (25.9%)
- > 24 hours (expired): 34 files (13.8%)
- Corrupted: 15 files (6.1%)

📈 Recent Activity:
- Cache writes (24h): 156
- Cache reads (24h): 1,247
- Cache invalidations (24h): 23
- Cleanup operations (24h): 3
```

### Administrative Cache Cleanup

Comprehensive cache maintenance operations:

```bash
# Remove all expired cache entries
agentmap validate-cache --cleanup

# Remove corrupted cache files  
agentmap validate-cache --cleanup --corrupted

# Full cache reset (use with caution)
agentmap validate-cache --clear --force

# Cleanup with size limits
agentmap validate-cache --cleanup --max-size 500MB

# Cleanup files older than specific time
agentmap validate-cache --cleanup --older-than 7d
```

### Cache Maintenance Scheduling

Set up automated cache maintenance:

```bash
# Daily cleanup of expired entries
0 2 * * * /usr/local/bin/agentmap validate-cache --cleanup >/dev/null 2>&1

# Weekly full cache analysis
0 3 * * 0 /usr/local/bin/agentmap validate-cache --stats --verbose >> /var/log/agentmap-cache.log

# Monthly cache optimization
0 4 1 * * /usr/local/bin/agentmap validate-cache --optimize >> /var/log/agentmap-cache.log
```

## Performance Monitoring

### Cache Performance Metrics

Key metrics for administrative monitoring:

**Hit Rate Analysis**:
```bash
# Current hit rate
agentmap validate-cache --stats | grep "hit rate"

# Historical hit rate (if logging enabled)
grep "cache hit" /var/log/agentmap.log | tail -100
```

**Storage Growth Monitoring**:
```bash
# Monitor cache directory size
du -sh ~/.agentmap/validation_cache

# Track cache growth over time
echo "$(date): $(du -sh ~/.agentmap/validation_cache)" >> /var/log/agentmap-cache-size.log
```

**Performance Benchmarking**:
```bash
# Benchmark cache vs no-cache performance
time agentmap validate csv --csv large_file.csv          # With cache
time agentmap validate csv --csv large_file.csv --no-cache  # Without cache
```

### System Resource Impact

Monitor cache impact on system resources:

```bash
# Memory usage analysis
ps aux | grep agentmap

# I/O usage monitoring  
iotop -p $(pgrep agentmap)

# Disk usage tracking
df -h ~/.agentmap/
```

## Cache Optimization Strategies

### Hit Rate Optimization

Improve cache efficiency through configuration tuning:

**Cache TTL Adjustment**:
```bash
# Extend cache lifetime for stable environments
export AGENTMAP_CACHE_TTL=48h

# Reduce cache lifetime for dynamic environments  
export AGENTMAP_CACHE_TTL=6h
```

**Cache Size Optimization**:
```bash
# Set maximum cache size
export AGENTMAP_MAX_CACHE_SIZE=1GB

# Set maximum cache files
export AGENTMAP_MAX_CACHE_FILES=10000
```

### Storage Optimization

Optimize cache storage for performance:

**SSD Optimization**:
```bash
# Move cache to SSD for better performance
export AGENTMAP_CACHE_DIR=/fast-ssd/agentmap-cache
```

**Network Storage Considerations**:
```bash
# Avoid network storage for cache (performance impact)
# Use local storage: ~/.agentmap/validation_cache
# Avoid: /nfs/shared/cache or /smb/cache
```

### Multi-User Environment Setup

Configure cache for multi-user environments:

```bash
# Per-user cache isolation (default)
~/.agentmap/validation_cache/

# Shared cache directory (advanced setup)
/opt/agentmap/shared_cache/
chmod 775 /opt/agentmap/shared_cache/
chgrp agentmap-users /opt/agentmap/shared_cache/
```

## Troubleshooting Administration

### Common Administrative Issues

**High Cache Miss Rate**:
```bash
# Analyze cache miss patterns
agentmap validate-cache --stats --verbose | grep "miss"

# Check for frequent file changes
find ~/.agentmap/validation_cache -name "*.json" -newer -1h | wc -l

# Review cache TTL settings
echo "Current TTL: $AGENTMAP_CACHE_TTL"
```

**Disk Space Issues**:
```bash
# Check cache directory size
du -sh ~/.agentmap/validation_cache

# Find largest cache files
find ~/.agentmap/validation_cache -type f -exec ls -lh {} + | sort -k5 -hr | head -20

# Emergency cache cleanup
agentmap validate-cache --cleanup --max-size 100MB
```

**Corrupted Cache Files**:
```bash
# Identify corrupted files
agentmap validate-cache --stats | grep "corrupted"

# Remove corrupted files
agentmap validate-cache --cleanup --corrupted

# Verify cache integrity
agentmap validate-cache --verify
```

### Cache Recovery Procedures

**Complete Cache Recovery**:
```bash
# Step 1: Backup current cache (optional)
tar -czf cache-backup-$(date +%Y%m%d).tar.gz ~/.agentmap/validation_cache/

# Step 2: Clear all cache
agentmap validate-cache --clear --force

# Step 3: Verify cache directory is clean
ls -la ~/.agentmap/validation_cache/

# Step 4: Run test validation to rebuild cache
agentmap validate all

# Step 5: Verify cache is working
agentmap validate-cache --stats
```

**Selective Cache Recovery**:
```bash
# Remove cache for specific patterns
find ~/.agentmap/validation_cache -name "*corrupted_file*" -delete

# Rebuild cache for specific files
agentmap validate csv --csv problem_file.csv --no-cache
```

## Monitoring and Alerting

### Cache Health Monitoring Scripts

Create monitoring scripts for cache health:

```bash
#!/bin/bash
# cache-health-check.sh

CACHE_DIR="$HOME/.agentmap/validation_cache"
MAX_SIZE_MB=1000
MAX_CORRUPTED=10

# Check cache size
CACHE_SIZE_MB=$(du -sm "$CACHE_DIR" | cut -f1)
if [ "$CACHE_SIZE_MB" -gt "$MAX_SIZE_MB" ]; then
    echo "WARNING: Cache size $CACHE_SIZE_MB MB exceeds $MAX_SIZE_MB MB"
fi

# Check corrupted files
CORRUPTED_COUNT=$(agentmap validate-cache --stats | grep -o '[0-9]* corrupted' | cut -d' ' -f1)
if [ "$CORRUPTED_COUNT" -gt "$MAX_CORRUPTED" ]; then
    echo "WARNING: $CORRUPTED_COUNT corrupted cache files exceeds threshold $MAX_CORRUPTED"
fi

# Check hit rate
HIT_RATE=$(agentmap validate-cache --stats | grep "hit rate" | grep -o '[0-9.]*%' | cut -d'%' -f1)
if (( $(echo "$HIT_RATE < 70" | bc -l) )); then
    echo "WARNING: Cache hit rate $HIT_RATE% is below 70%"
fi
```

### Log Analysis

Analyze cache behavior through logs:

```bash
# Enable cache logging
export AGENTMAP_CACHE_LOG_LEVEL=INFO

# Analyze cache patterns
grep "cache" /var/log/agentmap.log | tail -100

# Cache performance analysis
awk '/cache hit/ {hits++} /cache miss/ {misses++} END {print "Hit rate:", hits/(hits+misses)*100"%"}' /var/log/agentmap.log
```

## Security Considerations

### Cache Security

Protect cached data and system integrity:

**File Permissions**:
```bash
# Secure cache directory permissions
chmod 750 ~/.agentmap/validation_cache
chmod 640 ~/.agentmap/validation_cache/*.json
```

**Data Sensitivity**:
- Cache files may contain sensitive validation data
- Consider encryption for cache in sensitive environments
- Implement cache cleanup policies for compliance

**Access Control**:
```bash
# Multi-user environment access control
sudo groupadd agentmap-cache-users
sudo usermod -a -G agentmap-cache-users username
sudo chgrp -R agentmap-cache-users /opt/agentmap/cache
sudo chmod -R 2750 /opt/agentmap/cache
```

## Enterprise Administration

### Large-Scale Cache Management

For enterprise deployments with multiple AgentMap instances:

**Centralized Cache Monitoring**:
```bash
# Collect cache statistics from multiple instances
for host in $(cat agentmap-hosts.txt); do
    echo "=== $host ===" 
    ssh $host "agentmap validate-cache --stats"
done
```

**Distributed Cache Cleanup**:
```bash
# Automated cleanup across multiple systems
ansible-playbook -i inventory cache-cleanup.yml
```

**Cache Performance Aggregation**:
```bash
# Aggregate cache metrics for enterprise dashboard
for host in $(cat agentmap-hosts.txt); do
    ssh $host "agentmap validate-cache --stats --format json" >> cache-metrics.jsonl
done
```

### Backup and Disaster Recovery

**Cache Backup Strategy**:
```bash
# Daily cache backup (optional - cache is rebuiltable)
tar -czf "cache-backup-$(date +%Y%m%d).tar.gz" ~/.agentmap/validation_cache/

# Weekly cleanup of old backups
find . -name "cache-backup-*.tar.gz" -mtime +7 -delete
```

**Disaster Recovery**:
- Cache is rebuiltable from source files
- Focus on backing up source CSV/config files
- Cache can be rebuilt automatically during recovery

## Best Practices for Administrators

### Daily Operations

1. **Monitor Cache Health**: Check cache statistics daily
2. **Review Storage Usage**: Monitor disk space consumption
3. **Analyze Performance**: Track cache hit rates and performance metrics
4. **Cleanup Automation**: Ensure automated cleanup is running

### Weekly Maintenance

1. **Deep Analysis**: Review cache patterns and optimization opportunities
2. **Security Review**: Check cache permissions and access controls
3. **Performance Tuning**: Adjust cache parameters based on usage patterns
4. **Documentation Updates**: Update cache policies and procedures

### Monthly Reviews

1. **Capacity Planning**: Analyze growth trends and storage requirements
2. **Performance Benchmarking**: Compare cache performance over time
3. **Policy Review**: Update cache retention and cleanup policies
4. **Training Updates**: Ensure team is aware of cache management procedures

## Related Documentation

- **[Validation Cache Development Guide](../development/validation-cache)**: Developer-focused cache usage
- **[Performance Optimization Guide](../performance/optimization)**: System-wide performance tuning
- **[System Health Monitoring](../system-health)**: Overall system monitoring practices
- **[Troubleshooting Guide](../troubleshooting)**: General troubleshooting procedures
- **[CLI Validation Reference](/docs/deployment/08-cli-validation)**: Complete CLI command reference

## Next Steps

1. **Set Up Monitoring**: Implement cache health monitoring scripts
2. **Schedule Maintenance**: Configure automated cache cleanup procedures
3. **Optimize Performance**: Tune cache parameters for your environment
4. **Document Policies**: Create organization-specific cache management policies
5. **Train Team**: Ensure administrators understand cache management procedures
