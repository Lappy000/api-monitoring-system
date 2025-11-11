"""Prometheus metrics collection for API monitoring system."""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)
from typing import Optional
from datetime import datetime
import psutil
import os

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Prometheus metrics collector for API Monitor."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            registry: Optional custom registry
        """
        self.registry = registry or CollectorRegistry()
        self._setup_metrics()
        logger.info("Prometheus metrics collector initialized")
    
    def _setup_metrics(self) -> None:
        """Setup all Prometheus metrics."""
        
        # API Metrics
        self.api_requests_total = Counter(
            'api_monitor_requests_total',
            'Total number of API requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'api_monitor_request_duration_seconds',
            'API request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Health Check Metrics
        self.health_checks_total = Counter(
            'api_monitor_health_checks_total',
            'Total number of health checks performed',
            ['endpoint_id', 'endpoint_name', 'status'],
            registry=self.registry
        )
        
        self.health_check_duration = Histogram(
            'api_monitor_health_check_duration_seconds',
            'Health check duration in seconds',
            ['endpoint_id', 'endpoint_name'],
            registry=self.registry
        )
        
        self.endpoint_status = Gauge(
            'api_monitor_endpoint_status',
            'Current endpoint status (1=up, 0=down)',
            ['endpoint_id', 'endpoint_name', 'url'],
            registry=self.registry
        )
        
        self.endpoint_response_time = Gauge(
            'api_monitor_endpoint_response_time_seconds',
            'Last response time for endpoint',
            ['endpoint_id', 'endpoint_name'],
            registry=self.registry
        )
        
        # Notification Metrics
        self.notifications_total = Counter(
            'api_monitor_notifications_total',
            'Total number of notifications sent',
            ['type', 'status', 'endpoint_id'],
            registry=self.registry
        )
        
        self.notification_duration = Histogram(
            'api_monitor_notification_duration_seconds',
            'Notification sending duration',
            ['type'],
            registry=self.registry
        )
        
        # System Metrics
        self.active_endpoints = Gauge(
            'api_monitor_active_endpoints',
            'Number of active monitoring endpoints',
            registry=self.registry
        )
        
        self.system_cpu_usage = Gauge(
            'api_monitor_system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'api_monitor_system_memory_usage_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk_usage = Gauge(
            'api_monitor_system_disk_usage_percent',
            'System disk usage percentage',
            registry=self.registry
        )
        
        # Database Metrics
        self.database_connections = Gauge(
            'api_monitor_database_connections',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.database_query_duration = Histogram(
            'api_monitor_database_query_duration_seconds',
            'Database query duration',
            ['query_type'],
            registry=self.registry
        )
        
        # Cache Metrics
        self.cache_operations_total = Counter(
            'api_monitor_cache_operations_total',
            'Total cache operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'api_monitor_cache_hit_rate',
            'Cache hit rate (0-1)',
            registry=self.registry
        )
        
        # Scheduler Metrics
        self.scheduler_jobs_total = Counter(
            'api_monitor_scheduler_jobs_total',
            'Total scheduled jobs executed',
            ['job_type'],
            registry=self.registry
        )
        
        self.scheduler_job_duration = Histogram(
            'api_monitor_scheduler_job_duration_seconds',
            'Scheduled job execution duration',
            ['job_type'],
            registry=self.registry
        )
    
    def record_api_request(self, method: str, endpoint: str, status: int, duration: float) -> None:
        """
        Record API request metrics.
        
        Args:
            method: HTTP method
            endpoint: Endpoint path
            status: HTTP status code
            duration: Request duration in seconds
        """
        self.api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()
        
        self.api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_health_check(self, endpoint_id: int, endpoint_name: str, status: str, duration: float) -> None:
        """
        Record health check metrics.
        
        Args:
            endpoint_id: Endpoint ID
            endpoint_name: Endpoint name
            status: Check status (success/failure)
            duration: Check duration in seconds
        """
        self.health_checks_total.labels(
            endpoint_id=str(endpoint_id),
            endpoint_name=endpoint_name,
            status=status
        ).inc()
        
        self.health_check_duration.labels(
            endpoint_id=str(endpoint_id),
            endpoint_name=endpoint_name
        ).observe(duration)
        
        # Update endpoint status gauge
        status_value = 1 if status == "success" else 0
        self.endpoint_status.labels(
            endpoint_id=str(endpoint_id),
            endpoint_name=endpoint_name,
            url=""  # Would need to pass actual URL
        ).set(status_value)
    
    def record_endpoint_response_time(self, endpoint_id: int, endpoint_name: str, response_time: float) -> None:
        """
        Record endpoint response time.
        
        Args:
            endpoint_id: Endpoint ID
            endpoint_name: Endpoint name
            response_time: Response time in seconds
        """
        self.endpoint_response_time.labels(
            endpoint_id=str(endpoint_id),
            endpoint_name=endpoint_name
        ).set(response_time)
    
    def record_notification(self, notification_type: str, status: str, endpoint_id: int, duration: float) -> None:
        """
        Record notification metrics.
        
        Args:
            notification_type: Type of notification (email, webhook, telegram)
            status: Notification status (sent, failed)
            endpoint_id: Endpoint ID
            duration: Notification sending duration
        """
        self.notifications_total.labels(
            type=notification_type,
            status=status,
            endpoint_id=str(endpoint_id)
        ).inc()
        
        self.notification_duration.labels(
            type=notification_type
        ).observe(duration)
    
    def update_active_endpoints(self, count: int) -> None:
        """
        Update active endpoints gauge.
        
        Args:
            count: Number of active endpoints
        """
        self.active_endpoints.set(count)
    
    def update_system_metrics(self) -> None:
        """Update system resource usage metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.system_disk_usage.set((disk.used / disk.total) * 100)
            
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    def record_database_query(self, query_type: str, duration: float) -> None:
        """
        Record database query metrics.
        
        Args:
            query_type: Type of query (select, insert, update, delete)
            duration: Query duration in seconds
        """
        self.database_query_duration.labels(query_type=query_type).observe(duration)
    
    def update_database_connections(self, count: int) -> None:
        """
        Update database connections gauge.
        
        Args:
            count: Number of active connections
        """
        self.database_connections.set(count)
    
    def record_cache_operation(self, operation: str, status: str) -> None:
        """
        Record cache operation metrics.
        
        Args:
            operation: Cache operation (get, set, delete)
            status: Operation status (hit, miss, error)
        """
        self.cache_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
    
    def update_cache_hit_rate(self, hit_rate: float) -> None:
        """
        Update cache hit rate gauge.
        
        Args:
            hit_rate: Cache hit rate (0-1)
        """
        self.cache_hit_rate.set(hit_rate)
    
    def record_scheduler_job(self, job_type: str, duration: float) -> None:
        """
        Record scheduler job metrics.
        
        Args:
            job_type: Type of scheduled job
            duration: Job execution duration
        """
        self.scheduler_jobs_total.labels(job_type=job_type).inc()
        self.scheduler_job_duration.labels(job_type=job_type).observe(duration)
    
    def generate_metrics(self) -> bytes:
        """
        Generate Prometheus metrics output.
        
        Returns:
            bytes: Prometheus metrics in text format
        """
        try:
            self.update_system_metrics()
            return generate_latest(self.registry)
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return b""


# Global metrics collector instance
metrics_collector = MetricsCollector()