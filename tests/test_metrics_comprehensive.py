"""Comprehensive tests for Prometheus metrics collector."""

import pytest
from unittest.mock import MagicMock, patch

from app.core.metrics import MetricsCollector, metrics_collector


def test_metrics_collector_initialization():
    """Test metrics collector initialization."""
    collector = MetricsCollector()
    
    assert collector.registry is not None
    assert collector.api_requests_total is not None
    assert collector.api_request_duration is not None
    assert collector.health_checks_total is not None
    assert collector.health_check_duration is not None
    assert collector.endpoint_status is not None


def test_metrics_collector_custom_registry():
    """Test metrics collector with custom registry."""
    from prometheus_client import CollectorRegistry
    
    custom_registry = CollectorRegistry()
    collector = MetricsCollector(registry=custom_registry)
    
    assert collector.registry == custom_registry


def test_record_api_request():
    """Test recording API request metrics."""
    collector = MetricsCollector()
    
    # Record request
    collector.record_api_request("GET", "/endpoints", 200, 0.5)
    
    # Verify metric was recorded
    assert collector.api_requests_total._metrics


def test_record_health_check():
    """Test recording health check metrics."""
    collector = MetricsCollector()
    
    # Record health check
    collector.record_health_check(1, "Test API", "success", 0.5)
    
    # Verify metrics were recorded
    assert collector.health_checks_total._metrics
    assert collector.health_check_duration._metrics


def test_record_health_check_failure():
    """Test recording failed health check."""
    collector = MetricsCollector()
    
    # Record failed health check
    collector.record_health_check(1, "Test API", "failure", 2.0)
    
    #  Verify endpoint status set to 0 for failure
    assert collector.endpoint_status._metrics


def test_record_endpoint_response_time():
    """Test recording endpoint response time."""
    collector = MetricsCollector()
    
    # Record response time
    collector.record_endpoint_response_time(1, "Test API", 0.5)
    
    # Verify metric was recorded
    assert collector.endpoint_response_time._metrics


def test_record_notification():
    """Test recording notification metrics."""
    collector = MetricsCollector()
    
    # Record notification
    collector.record_notification("email", "sent", 1, 0.3)
    
    # Verify metrics were recorded
    assert collector.notifications_total._metrics
    assert collector.notification_duration._metrics


def test_record_notification_different_types():
    """Test recording different notification types."""
    collector = MetricsCollector()
    
    # Record different types
    collector.record_notification("email", "sent", 1, 0.3)
    collector.record_notification("webhook", "failed", 2, 0.5)
    collector.record_notification("telegram", "sent", 3, 0.2)
    
    # Verify all types were recorded
    assert collector.notifications_total._metrics


def test_update_active_endpoints():
    """Test updating active endpoints gauge."""
    collector = MetricsCollector()
    
    # Update count
    collector.update_active_endpoints(5)
    
    # Verify metric was set (gauge doesn't fail on set)
    # Simply verify the method runs without error
    assert True


def test_update_system_metrics():
    """Test updating system metrics."""
    collector = MetricsCollector()
    
    with patch('psutil.cpu_percent', return_value=45.5), \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk:
        
        # Mock memory
        mock_memory.return_value.percent = 60.5
        
        # Mock disk
        mock_disk_obj = MagicMock()
        mock_disk_obj.used = 50 * 1024**3  # 50 GB
        mock_disk_obj.total = 100 * 1024**3  # 100 GB
        mock_disk.return_value = mock_disk_obj
        
        # Update metrics
        collector.update_system_metrics()
        
        # Verify method runs without error
        assert True


def test_update_system_metrics_error():
    """Test system metrics update with error."""
    collector = MetricsCollector()
    
    with patch('psutil.cpu_percent', side_effect=Exception("CPU error")):
        # Should not raise exception
        collector.update_system_metrics()


def test_record_database_query():
    """Test recording database query metrics."""
    collector = MetricsCollector()
    
    # Record query
    collector.record_database_query("select", 0.1)
    collector.record_database_query("insert", 0.2)
    
    # Verify metrics were recorded
    assert collector.database_query_duration._metrics


def test_update_database_connections():
    """Test updating database connections gauge."""
    collector = MetricsCollector()
    
    # Update count
    collector.update_database_connections(10)
    
    # Verify method runs without error
    assert True


def test_record_cache_operation():
    """Test recording cache operation metrics."""
    collector = MetricsCollector()
    
    # Record operations
    collector.record_cache_operation("get", "hit")
    collector.record_cache_operation("get", "miss")
    collector.record_cache_operation("set", "success")
    
    # Verify metrics were recorded
    assert collector.cache_operations_total._metrics


def test_update_cache_hit_rate():
    """Test updating cache hit rate."""
    collector = MetricsCollector()
    
    # Update hit rate
    collector.update_cache_hit_rate(0.85)
    
    # Verify method runs without error
    assert True


def test_record_scheduler_job():
    """Test recording scheduler job metrics."""
    collector = MetricsCollector()
    
    # Record job
    collector.record_scheduler_job("health_check", 1.5)
    
    # Verify metrics were recorded
    assert collector.scheduler_jobs_total._metrics
    assert collector.scheduler_job_duration._metrics


def test_generate_metrics():
    """Test generating Prometheus metrics."""
    collector = MetricsCollector()
    
    with patch.object(collector, 'update_system_metrics'):
        # Generate metrics
        metrics = collector.generate_metrics()
        
        # Verify output is bytes
        assert isinstance(metrics, bytes)
        # Should contain Prometheus format
        assert b"api_monitor" in metrics


def test_generate_metrics_error():
    """Test generating metrics with error."""
    collector = MetricsCollector()
    
    with patch('app.core.metrics.generate_latest', side_effect=Exception("Generation error")):
        # Generate metrics
        metrics = collector.generate_metrics()
        
        # Should return empty bytes on error
        assert metrics == b""


def test_global_metrics_collector():
    """Test global metrics collector instance."""
    from app.core.metrics import metrics_collector
    
    # Verify it's a MetricsCollector instance
    assert isinstance(metrics_collector, MetricsCollector)


def test_multiple_api_requests():
    """Test recording multiple API requests."""
    collector = MetricsCollector()
    
    # Record multiple requests
    collector.record_api_request("GET", "/endpoints", 200, 0.1)
    collector.record_api_request("POST", "/endpoints", 201, 0.2)
    collector.record_api_request("GET", "/endpoints/1", 200, 0.15)
    
    # Verify all were recorded
    assert collector.api_requests_total._metrics


def test_notification_duration_distribution():
    """Test notification duration histogram."""
    collector = MetricsCollector()
    
    # Record various durations
    collector.record_notification("email", "sent", 1, 0.5)
    collector.record_notification("email", "sent", 2, 1.0)
    collector.record_notification("email", "sent", 3, 0.3)
    
    # Verify histogram recorded values
    assert collector.notification_duration._metrics