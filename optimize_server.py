#!/usr/bin/env python3
"""
Server Optimization Script for Low-Memory Servers (2GB RAM)
This script optimizes the Email Campaign Manager for better performance on limited resources.
"""

import os
import sys
import json
import gc
import psutil
import subprocess
import time
from pathlib import Path

def log(message):
    """Print timestamped log message"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def optimize_system_settings():
    """Optimize system settings for low-memory servers"""
    log("🔧 Optimizing system settings for low-memory server...")
    
    # Check current memory
    total_memory = psutil.virtual_memory().total / 1024 / 1024 / 1024
    log(f"📊 Total system memory: {total_memory:.1f} GB")
    
    if total_memory < 3:
        log("⚠️ Low memory detected - applying aggressive optimizations")
        
        # Optimize swap settings
        try:
            # Increase swap usage
            subprocess.run(['sudo', 'sysctl', 'vm.swappiness=60'], check=True)
            log("✅ Increased swap usage")
        except:
            log("⚠️ Could not adjust swap settings")
        
        # Optimize file system cache
        try:
            subprocess.run(['sudo', 'sysctl', 'vm.vfs_cache_pressure=200'], check=True)
            log("✅ Optimized file system cache")
        except:
            log("⚠️ Could not adjust cache pressure")

def optimize_application_settings():
    """Optimize application-specific settings"""
    log("🔧 Optimizing application settings...")
    
    # Create optimized gunicorn configuration
    gunicorn_config = """
# Optimized Gunicorn configuration for low-memory servers
bind = "127.0.0.1:8000"
workers = 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
preload_app = True
worker_tmp_dir = "/dev/shm"
worker_exit_on_app_exit = True
"""

    with open('gunicorn_optimized.conf.py', 'w') as f:
        f.write(gunicorn_config)
    
    log("✅ Created optimized Gunicorn configuration")

def optimize_json_files():
    """Optimize JSON data files for better performance"""
    log("🔧 Optimizing JSON data files...")
    
    json_files = [
        'accounts.json',
        'campaigns.json', 
        'users.json',
        'notifications.json',
        'campaign_logs.json',
        'bounces.json',
        'rate_limit_config.json'
    ]
    
    for filename in json_files:
        if os.path.exists(filename):
            try:
                # Read and validate JSON
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                # Compact the JSON (remove extra whitespace)
                with open(filename, 'w') as f:
                    json.dump(data, f, separators=(',', ':'))
                
                log(f"✅ Optimized {filename}")
            except Exception as e:
                log(f"⚠️ Could not optimize {filename}: {e}")

def create_memory_monitor():
    """Create a memory monitoring script"""
    log("🔧 Creating memory monitoring script...")
    
    monitor_script = '''#!/usr/bin/env python3
"""
Memory Monitor for Email Campaign Manager
Monitors memory usage and performs cleanup when needed.
"""

import psutil
import time
import gc
import os
import signal
import sys

def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_memory_usage():
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def cleanup_memory():
    """Force garbage collection and memory cleanup"""
    gc.collect()
    log(f"🧹 Memory cleanup completed. Usage: {get_memory_usage():.1f} MB")

def monitor_memory():
    """Monitor memory usage and perform cleanup if needed"""
    while True:
        try:
            memory_usage = get_memory_usage()
            log(f"📊 Current memory usage: {memory_usage:.1f} MB")
            
            # If memory usage is high, perform cleanup
            if memory_usage > 1500:  # 1.5GB threshold
                log("⚠️ High memory usage detected - performing cleanup")
                cleanup_memory()
            
            time.sleep(300)  # Check every 5 minutes
            
        except KeyboardInterrupt:
            log("🛑 Memory monitor stopped")
            break
        except Exception as e:
            log(f"❌ Error in memory monitor: {e}")
            time.sleep(60)

if __name__ == "__main__":
    log("🚀 Starting memory monitor...")
    monitor_memory()
'''
    
    with open('memory_monitor.py', 'w') as f:
        f.write(monitor_script)
    
    # Make it executable
    os.chmod('memory_monitor.py', 0o755)
    log("✅ Created memory monitoring script")

def create_optimized_service():
    """Create optimized systemd service configuration"""
    log("🔧 Creating optimized systemd service...")
    
    service_config = """[Unit]
Description=Email Campaign Manager (Optimized)
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --config gunicorn_optimized.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Memory and performance optimizations
MemoryMax=1800M
MemorySwapMax=0
CPUQuota=80%
LimitNOFILE=65536
LimitNPROC=4096

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/emailcampaign/email-campaign-manager

[Install]
WantedBy=multi-user.target
"""
    
    with open('email-campaign-manager-optimized.service', 'w') as f:
        f.write(service_config)
    
    log("✅ Created optimized systemd service configuration")

def create_performance_script():
    """Create a performance monitoring and optimization script"""
    log("🔧 Creating performance optimization script...")
    
    perf_script = '''#!/bin/bash

echo "🚀 Email Campaign Manager - Performance Optimization"
echo "=================================================="

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check system resources
print_status "Checking system resources..."

# Memory usage
MEMORY_USAGE=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2 }')
print_status "Memory usage: $MEMORY_USAGE"

# Disk usage
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}')
print_status "Disk usage: $DISK_USAGE"

# CPU load
CPU_LOAD=$(uptime | awk -F'load average:' '{ print $2 }')
print_status "CPU load: $CPU_LOAD"

# Check if optimization is needed
if [[ $(echo $MEMORY_USAGE | sed 's/%//') -gt 80 ]]; then
    print_warning "High memory usage detected - applying optimizations"
    
    # Restart application with optimized settings
    sudo systemctl restart email-campaign-manager-optimized
    
    # Clear system cache
    sudo sync && sudo echo 3 > /proc/sys/vm/drop_caches
    
    print_success "Memory optimizations applied"
else
    print_success "System resources are within normal limits"
fi

# Monitor application performance
print_status "Monitoring application performance..."

# Check if application is responding
if curl -s http://localhost:8000 > /dev/null; then
    print_success "Application is responding"
else
    print_error "Application is not responding"
    sudo systemctl restart email-campaign-manager-optimized
fi

# Check service status
if sudo systemctl is-active --quiet email-campaign-manager-optimized; then
    print_success "Service is running"
else
    print_error "Service is not running"
    sudo systemctl start email-campaign-manager-optimized
fi

echo ""
print_success "Performance check completed!"
'''
    
    with open('check_performance.sh', 'w') as f:
        f.write(perf_script)
    
    os.chmod('check_performance.sh', 0o755)
    log("✅ Created performance monitoring script")

def main():
    """Main optimization function"""
    log("🚀 Starting server optimization for low-memory environment...")
    
    # Check if running as root
    if os.geteuid() == 0:
        log("❌ This script should not be run as root")
        sys.exit(1)
    
    # Get current memory usage
    initial_memory = get_memory_usage()
    log(f"📊 Initial memory usage: {initial_memory:.1f} MB")
    
    # Run optimizations
    optimize_system_settings()
    optimize_application_settings()
    optimize_json_files()
    create_memory_monitor()
    create_optimized_service()
    create_performance_script()
    
    # Final memory check
    final_memory = get_memory_usage()
    log(f"📊 Final memory usage: {final_memory:.1f} MB")
    
    log("✅ Server optimization completed!")
    log("")
    log("📋 Next steps:")
    log("1. Install optimized service: sudo cp email-campaign-manager-optimized.service /etc/systemd/system/")
    log("2. Enable optimized service: sudo systemctl enable email-campaign-manager-optimized")
    log("3. Stop old service: sudo systemctl stop email-campaign-manager")
    log("4. Start optimized service: sudo systemctl start email-campaign-manager-optimized")
    log("5. Run performance check: ./check_performance.sh")
    log("6. Start memory monitor: python3 memory_monitor.py &")

if __name__ == "__main__":
    main()