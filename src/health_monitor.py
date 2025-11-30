"""
Enterprise Health Monitoring
Real-time system health checks, alerting, and diagnostics
"""

import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .core.config_manager import ConfigManager
from .core.file_lock import SafeFileHandler
from .core.logging_setup import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    response_time_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    api_latency_ms: float = 0.0
    signals_per_hour: float = 0.0
    last_signal_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    uptime_seconds: float = 0.0


class HealthMonitor:
    """
    Enterprise health monitoring system

    Features:
    - Periodic health checks
    - File system monitoring
    - API availability checks
    - Performance metrics collection
    - Alerting on issues
    - Heartbeat for external monitoring
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize health monitor"""
        self.config = config_manager or ConfigManager()
        self._start_time = datetime.now()
        self._health_checks: Dict[str, HealthCheck] = {}
        self._metrics = SystemMetrics()
        self._alert_callbacks: List[Callable[[str, str], None]] = []
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        # File paths to monitor
        self._monitored_files = {
            'signals': self.config.get_file_path('signals_file'),
            'historical': self.config.get_file_path('historical_data'),
            'live_feed': self.config.get_file_path('live_feed'),
        }

        self._heartbeat_file = Path(self.config.monitoring.heartbeat_file)

        logger.info("HealthMonitor initialized")

    def register_alert_callback(self, callback: Callable[[str, str], None]):
        """Register callback for alerts: callback(alert_type, message)"""
        self._alert_callbacks.append(callback)

    def _send_alert(self, alert_type: str, message: str):
        """Send alert to all registered callbacks"""
        logger.warning(f"ALERT [{alert_type}]: {message}")
        for callback in self._alert_callbacks:
            try:
                callback(alert_type, message)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def check_file_health(self, name: str, file_path: Path, max_age_seconds: int = 300) -> HealthCheck:
        """Check health of a monitored file"""
        start = time.time()

        try:
            if not file_path.exists():
                return HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"File not found: {file_path}",
                    response_time_ms=(time.time() - start) * 1000
                )

            # Check file age
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_seconds = (datetime.now() - mtime).total_seconds()

            if age_seconds > max_age_seconds:
                return HealthCheck(
                    name=name,
                    status=HealthStatus.DEGRADED,
                    message=f"File stale: last modified {age_seconds:.0f}s ago",
                    response_time_ms=(time.time() - start) * 1000,
                    details={'last_modified': mtime.isoformat(), 'age_seconds': age_seconds}
                )

            # Check file is readable
            try:
                with open(file_path, 'r') as f:
                    f.read(1)
            except Exception as e:
                return HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"File not readable: {e}",
                    response_time_ms=(time.time() - start) * 1000
                )

            return HealthCheck(
                name=name,
                status=HealthStatus.HEALTHY,
                message="OK",
                response_time_ms=(time.time() - start) * 1000,
                details={'last_modified': mtime.isoformat(), 'size_bytes': file_path.stat().st_size}
            )

        except Exception as e:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                response_time_ms=(time.time() - start) * 1000
            )

    def check_api_health(self, api_name: str, test_func: Callable[[], bool]) -> HealthCheck:
        """Check health of an API endpoint"""
        start = time.time()

        try:
            result = test_func()
            response_time = (time.time() - start) * 1000

            if result:
                status = HealthStatus.HEALTHY if response_time < 5000 else HealthStatus.DEGRADED
                return HealthCheck(
                    name=api_name,
                    status=status,
                    message="OK" if status == HealthStatus.HEALTHY else f"Slow response: {response_time:.0f}ms",
                    response_time_ms=response_time
                )
            else:
                return HealthCheck(
                    name=api_name,
                    status=HealthStatus.UNHEALTHY,
                    message="API test failed",
                    response_time_ms=response_time
                )

        except Exception as e:
            return HealthCheck(
                name=api_name,
                status=HealthStatus.UNHEALTHY,
                message=f"API error: {e}",
                response_time_ms=(time.time() - start) * 1000
            )

    def check_system_resources(self) -> HealthCheck:
        """Check system resource usage"""
        start = time.time()

        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent

            self._metrics.cpu_usage = cpu
            self._metrics.memory_usage = memory
            self._metrics.disk_usage = disk

            issues = []
            if cpu > 90:
                issues.append(f"High CPU: {cpu:.1f}%")
            if memory > 90:
                issues.append(f"High Memory: {memory:.1f}%")
            if disk > 90:
                issues.append(f"High Disk: {disk:.1f}%")

            if issues:
                status = HealthStatus.DEGRADED if len(issues) < 2 else HealthStatus.UNHEALTHY
                return HealthCheck(
                    name="system_resources",
                    status=status,
                    message="; ".join(issues),
                    response_time_ms=(time.time() - start) * 1000,
                    details={'cpu': cpu, 'memory': memory, 'disk': disk}
                )

            return HealthCheck(
                name="system_resources",
                status=HealthStatus.HEALTHY,
                message=f"CPU: {cpu:.1f}%, Memory: {memory:.1f}%, Disk: {disk:.1f}%",
                response_time_ms=(time.time() - start) * 1000,
                details={'cpu': cpu, 'memory': memory, 'disk': disk}
            )

        except ImportError:
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message="psutil not installed",
                response_time_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                response_time_ms=(time.time() - start) * 1000
            )

    def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks"""
        checks = {}

        # File health checks
        for name, path in self._monitored_files.items():
            max_age = 3600 if name == 'historical' else 60  # Historical updates hourly
            checks[f"file_{name}"] = self.check_file_health(name, path, max_age)

        # System resources
        checks["system_resources"] = self.check_system_resources()

        # Update stored checks
        self._health_checks = checks

        # Check for alerts
        self._check_alerts(checks)

        return checks

    def _check_alerts(self, checks: Dict[str, HealthCheck]):
        """Check if any health checks warrant alerts"""
        for name, check in checks.items():
            if check.status == HealthStatus.UNHEALTHY:
                self._send_alert("UNHEALTHY", f"{name}: {check.message}")
            elif check.status == HealthStatus.DEGRADED:
                # Only alert on degraded if it persists
                prev_check = self._health_checks.get(name)
                if prev_check and prev_check.status == HealthStatus.DEGRADED:
                    self._send_alert("DEGRADED", f"{name}: {check.message}")

    def update_heartbeat(self):
        """Update heartbeat file for external monitoring"""
        try:
            self._heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
            self._heartbeat_file.write_text(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Failed to update heartbeat: {e}")

    def record_signal(self):
        """Record that a signal was generated"""
        self._metrics.last_signal_time = datetime.now()

    def record_trade(self):
        """Record that a trade was executed"""
        self._metrics.last_trade_time = datetime.now()

    def get_uptime(self) -> timedelta:
        """Get system uptime"""
        return datetime.now() - self._start_time

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        if not self._health_checks:
            return HealthStatus.UNKNOWN

        statuses = [c.status for c in self._health_checks.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        uptime = self.get_uptime()

        return {
            'overall_status': self.get_overall_status().value,
            'uptime_seconds': uptime.total_seconds(),
            'uptime_formatted': str(uptime).split('.')[0],
            'last_check': datetime.now().isoformat(),
            'checks': {
                name: {
                    'status': check.status.value,
                    'message': check.message,
                    'response_time_ms': check.response_time_ms,
                    'details': check.details
                }
                for name, check in self._health_checks.items()
            },
            'metrics': {
                'cpu_usage': self._metrics.cpu_usage,
                'memory_usage': self._metrics.memory_usage,
                'disk_usage': self._metrics.disk_usage,
                'last_signal_time': self._metrics.last_signal_time.isoformat() if self._metrics.last_signal_time else None,
                'last_trade_time': self._metrics.last_trade_time.isoformat() if self._metrics.last_trade_time else None
            }
        }

    def start_monitoring(self, interval_seconds: Optional[int] = None):
        """Start background health monitoring"""
        if self._running:
            return

        interval = interval_seconds or self.config.monitoring.health_check_interval_seconds
        self._running = True

        def monitor_loop():
            while self._running:
                try:
                    self.run_all_checks()
                    self.update_heartbeat()
                except Exception as e:
                    logger.error(f"Health check error: {e}")

                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Health monitoring started (interval: {interval}s)")

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Health monitoring stopped")

    def get_summary(self) -> str:
        """Get human-readable health summary"""
        report = self.get_health_report()

        lines = [
            "=" * 50,
            "SYSTEM HEALTH STATUS",
            "=" * 50,
            f"Overall: {report['overall_status'].upper()}",
            f"Uptime: {report['uptime_formatted']}",
            "",
            "Component Status:",
        ]

        for name, check in report['checks'].items():
            status_icon = {
                'healthy': 'OK',
                'degraded': 'WARN',
                'unhealthy': 'FAIL',
                'unknown': '???'
            }.get(check['status'], '???')

            lines.append(f"  [{status_icon}] {name}: {check['message']}")

        if report['metrics']['last_signal_time']:
            lines.append(f"\nLast Signal: {report['metrics']['last_signal_time']}")
        if report['metrics']['last_trade_time']:
            lines.append(f"Last Trade: {report['metrics']['last_trade_time']}")

        lines.append("=" * 50)

        return "\n".join(lines)
