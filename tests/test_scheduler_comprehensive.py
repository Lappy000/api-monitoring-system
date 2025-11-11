"""Comprehensive tests for scheduler module."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.core.scheduler import MonitoringScheduler, get_scheduler, set_scheduler
from app.config import Config
from app.core.health_checker import HealthChecker
from app.core.notifications import NotificationManager
from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock(spec=Config)
    return config


@pytest.fixture
def mock_health_checker():
    """Create mock health checker."""
    health_checker = MagicMock(spec=HealthChecker)
    health_checker.start = AsyncMock()
    health_checker.close = AsyncMock()
    return health_checker


@pytest.fixture
def mock_notification_manager():
    """Create mock notification manager."""
    notification_manager = MagicMock(spec=NotificationManager)
    notification_manager.notify_failure = AsyncMock()
    notification_manager.notify_recovery = AsyncMock()
    notification_manager.close = AsyncMock()
    return notification_manager


@pytest.fixture
def scheduler(mock_config, mock_health_checker, mock_notification_manager):
    """Create scheduler instance."""
    return MonitoringScheduler(mock_config, mock_health_checker, mock_notification_manager)


@pytest.fixture
def sample_endpoint():
    """Create sample endpoint."""
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.name = "Test API"
    endpoint.url = "https://api.example.com/health"
    endpoint.interval = 60
    endpoint.is_active = True
    return endpoint


@pytest.fixture
def sample_check_result():
    """Create sample check result."""
    result = MagicMock(spec=CheckResult)
    result.success = True
    result.error_message = None
    result.status_code = 200
    result.checked_at = datetime.utcnow()
    result.response_time = 0.5
    return result


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler, mock_config, mock_health_checker, mock_notification_manager):
    """Test scheduler initialization."""
    assert scheduler.config == mock_config
    assert scheduler.health_checker == mock_health_checker
    assert scheduler.notification_manager == mock_notification_manager
    assert scheduler.jobs == {}
    assert scheduler.previous_states == {}
    assert scheduler.scheduler is not None


@pytest.mark.asyncio
async def test_scheduler_start(scheduler, sample_endpoint):
    """Test scheduler start."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.scheduler, 'start') as mock_start:
        
        # Mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_endpoint]
        mock_db.execute.return_value = mock_result
        
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock add_endpoint_job
        with patch.object(scheduler, 'add_endpoint_job', new_callable=AsyncMock) as mock_add:
            await scheduler.start()
            
            # Verify health checker started
            scheduler.health_checker.start.assert_called_once()
            
            # Verify scheduler started
            mock_start.assert_called_once()
            
            # Verify endpoints were loaded and jobs added
            mock_add.assert_called_once_with(sample_endpoint)


@pytest.mark.asyncio
async def test_scheduler_stop(scheduler):
    """Test scheduler stop."""
    with patch.object(scheduler.scheduler, 'shutdown') as mock_shutdown:
        await scheduler.stop()
        
        # Verify scheduler shutdown
        mock_shutdown.assert_called_once_with(wait=False)
        
        # Verify health checker closed
        scheduler.health_checker.close.assert_called_once()


@pytest.mark.asyncio
async def test_add_endpoint_job(scheduler, sample_endpoint):
    """Test adding endpoint job."""
    with patch.object(scheduler.scheduler, 'add_job') as mock_add_job:
        mock_job = MagicMock()
        mock_job.id = "job_123"
        mock_add_job.return_value = mock_job
        
        await scheduler.add_endpoint_job(sample_endpoint)
        
        # Verify job was added
        mock_add_job.assert_called_once()
        call_args = mock_add_job.call_args
        
        # Check job parameters
        assert call_args[0][0] == scheduler._check_endpoint
        assert call_args[1]['args'] == [sample_endpoint.id]
        assert call_args[1]['id'] == f"endpoint_{sample_endpoint.id}"
        assert call_args[1]['name'] == f"Check {sample_endpoint.name}"
        
        # Verify job stored in mapping
        assert scheduler.jobs[sample_endpoint.id] == "job_123"


@pytest.mark.asyncio
async def test_add_endpoint_job_duplicate(scheduler, sample_endpoint):
    """Test adding duplicate endpoint job."""
    # Add job first time
    scheduler.jobs[sample_endpoint.id] = "existing_job"
    
    # Try to add again
    with patch.object(scheduler.scheduler, 'add_job') as mock_add_job:
        await scheduler.add_endpoint_job(sample_endpoint)
        
        # Should not add duplicate
        mock_add_job.assert_not_called()


@pytest.mark.asyncio
async def test_remove_endpoint_job(scheduler, sample_endpoint):
    """Test removing endpoint job."""
    # Add job first
    scheduler.jobs[sample_endpoint.id] = "job_123"
    scheduler.previous_states[sample_endpoint.id] = True
    
    with patch.object(scheduler.scheduler, 'remove_job') as mock_remove_job:
        await scheduler.remove_endpoint_job(sample_endpoint.id)
        
        # Verify job was removed
        mock_remove_job.assert_called_once_with("job_123")
        
        # Verify cleanup
        assert sample_endpoint.id not in scheduler.jobs
        assert sample_endpoint.id not in scheduler.previous_states


@pytest.mark.asyncio
async def test_remove_endpoint_job_not_found(scheduler):
    """Test removing non-existent endpoint job."""
    with patch.object(scheduler.scheduler, 'remove_job') as mock_remove_job:
        await scheduler.remove_endpoint_job(999)
        
        # Should not attempt to remove
        mock_remove_job.assert_not_called()


@pytest.mark.asyncio
async def test_update_endpoint_job_active(scheduler, sample_endpoint):
    """Test updating active endpoint job."""
    # Add endpoint to jobs first
    scheduler.jobs[sample_endpoint.id] = "job_123"
    
    with patch.object(scheduler, 'remove_endpoint_job', new_callable=AsyncMock) as mock_remove, \
         patch.object(scheduler, 'add_endpoint_job', new_callable=AsyncMock) as mock_add:
        
        sample_endpoint.is_active = True
        await scheduler.update_endpoint_job(sample_endpoint)
        
        # Should remove and re-add
        mock_remove.assert_called_once_with(sample_endpoint.id)
        mock_add.assert_called_once_with(sample_endpoint)


@pytest.mark.asyncio
async def test_update_endpoint_job_inactive(scheduler, sample_endpoint):
    """Test updating inactive endpoint job."""
    # Add endpoint to jobs first
    scheduler.jobs[sample_endpoint.id] = "job_123"
    
    with patch.object(scheduler, 'remove_endpoint_job', new_callable=AsyncMock) as mock_remove, \
         patch.object(scheduler, 'add_endpoint_job', new_callable=AsyncMock) as mock_add:
        
        sample_endpoint.is_active = False
        await scheduler.update_endpoint_job(sample_endpoint)
        
        # Should only remove, not add
        mock_remove.assert_called_once_with(sample_endpoint.id)
        mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_check_endpoint_success(scheduler, sample_endpoint, sample_check_result, mock_db):
    """Test successful endpoint check."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.health_checker, 'check_and_save', new_callable=AsyncMock) as mock_check:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        mock_check.return_value = sample_check_result
        
        # Run check
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # Verify endpoint was checked
        mock_check.assert_called_once_with(sample_endpoint, mock_db)
        
        # Verify no notifications sent (still successful)
        scheduler.notification_manager.notify_failure.assert_not_called()
        scheduler.notification_manager.notify_recovery.assert_not_called()


@pytest.mark.asyncio
async def test_check_endpoint_failure_notification(scheduler, sample_endpoint, sample_check_result, mock_db):
    """Test endpoint check failure triggers notification."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.health_checker, 'check_and_save', new_callable=AsyncMock) as mock_check:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        # Set check to fail
        sample_check_result.success = False
        sample_check_result.error_message = "Connection timeout"
        mock_check.return_value = sample_check_result
        
        # Run check (first failure)
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # Verify failure notification sent
        scheduler.notification_manager.notify_failure.assert_called_once_with(
            sample_endpoint,
            sample_check_result,
            mock_db
        )
        
        # Verify state updated
        assert scheduler.previous_states[sample_endpoint.id] is False


@pytest.mark.asyncio
async def test_check_endpoint_recovery_notification(scheduler, sample_endpoint, sample_check_result, mock_db):
    """Test endpoint recovery triggers notification."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.health_checker, 'check_and_save', new_callable=AsyncMock) as mock_check:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        # Set previous state to failed
        scheduler.previous_states[sample_endpoint.id] = False
        
        # Set current check to succeed
        sample_check_result.success = True
        mock_check.return_value = sample_check_result
        
        # Run check
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # Verify recovery notification sent
        scheduler.notification_manager.notify_recovery.assert_called_once_with(
            sample_endpoint,
            sample_check_result,
            mock_db
        )
        
        # Verify state updated
        assert scheduler.previous_states[sample_endpoint.id] is True


@pytest.mark.asyncio
async def test_check_endpoint_inactive(scheduler, sample_endpoint, mock_db):
    """Test checking inactive endpoint."""
    with patch('app.core.scheduler.async_session') as mock_session_factory:
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        sample_endpoint.is_active = False
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        # Run check
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # Verify no health check performed
        scheduler.health_checker.check_and_save.assert_not_called()


@pytest.mark.asyncio
async def test_check_endpoint_not_found(scheduler, mock_db):
    """Test checking non-existent endpoint."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler, 'remove_endpoint_job', new_callable=AsyncMock) as mock_remove:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Run check
        await scheduler._check_endpoint(999)
        
        # Verify job removal attempted
        mock_remove.assert_called_once_with(999)


@pytest.mark.asyncio
async def test_check_endpoint_exception(scheduler, sample_endpoint, mock_db):
    """Test endpoint check with exception."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch('app.core.scheduler.logger.exception') as mock_log_exception:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = Exception("Database error")
        mock_db.execute.return_value = mock_result
        
        # Run check
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # Verify exception logged
        mock_log_exception.assert_called_once()


def test_get_job_status(scheduler, sample_endpoint):
    """Test getting job status."""
    # Add job
    scheduler.jobs[sample_endpoint.id] = "job_123"
    
    # Mock job
    mock_job = MagicMock()
    mock_job.id = "job_123"
    mock_job.name = "Check Test API"
    mock_job.next_run_time = datetime.utcnow()
    mock_job.trigger = "interval[0:01:00]"
    
    scheduler.scheduler.get_job = MagicMock(return_value=mock_job)
    
    # Get status
    status = scheduler.get_job_status(sample_endpoint.id)
    
    # Verify status
    assert status is not None
    assert status["job_id"] == "job_123"
    assert status["name"] == "Check Test API"
    assert "next_run_time" in status
    assert "trigger" in status


def test_get_job_status_not_found(scheduler):
    """Test getting status of non-existent job."""
    status = scheduler.get_job_status(999)
    assert status is None


def test_get_job_status_job_removed(scheduler, sample_endpoint):
    """Test getting status when job was removed from scheduler."""
    # Add to mapping but not in scheduler
    scheduler.jobs[sample_endpoint.id] = "job_123"
    scheduler.scheduler.get_job = MagicMock(return_value=None)
    
    status = scheduler.get_job_status(sample_endpoint.id)
    assert status is None


def test_get_all_jobs_status(scheduler, sample_endpoint):
    """Test getting status of all jobs."""
    # Add job
    scheduler.jobs[sample_endpoint.id] = "job_123"
    
    # Mock job
    mock_job = MagicMock()
    mock_job.id = "job_123"
    mock_job.name = "Check Test API"
    mock_job.next_run_time = datetime.utcnow()
    mock_job.trigger = "interval[0:01:00]"
    
    scheduler.scheduler.get_job = MagicMock(return_value=mock_job)
    
    # Get all statuses
    statuses = scheduler.get_all_jobs_status()
    
    # Verify
    assert len(statuses) == 1
    assert sample_endpoint.id in statuses


def test_get_all_jobs_status_empty(scheduler):
    """Test getting status when no jobs."""
    statuses = scheduler.get_all_jobs_status()
    assert statuses == {}


def test_get_scheduler_default():
    """Test getting default scheduler (None)."""
    result = get_scheduler()
    assert result is None


def test_set_and_get_scheduler(scheduler):
    """Test setting and getting scheduler."""
    set_scheduler(scheduler)
    result = get_scheduler()
    assert result == scheduler


def test_set_scheduler_overwrite(scheduler):
    """Test overwriting scheduler."""
    set_scheduler(scheduler)
    
    new_scheduler = MagicMock(spec=MonitoringScheduler)
    set_scheduler(new_scheduler)
    
    result = get_scheduler()
    assert result == new_scheduler


@pytest.mark.asyncio
async def test_check_endpoint_consecutive_failures(scheduler, sample_endpoint, sample_check_result, mock_db):
    """Test consecutive failures don't send duplicate notifications."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.health_checker, 'check_and_save', new_callable=AsyncMock) as mock_check:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        # Set check to fail
        sample_check_result.success = False
        mock_check.return_value = sample_check_result
        
        # First failure - should notify
        await scheduler._check_endpoint(sample_endpoint.id)
        assert scheduler.notification_manager.notify_failure.call_count == 1
        
        # Second failure - should not notify again (no state change)
        await scheduler._check_endpoint(sample_endpoint.id)
        assert scheduler.notification_manager.notify_failure.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_check_endpoint_consecutive_success(scheduler, sample_endpoint, sample_check_result, mock_db):
    """Test consecutive successes don't send notifications."""
    with patch('app.core.scheduler.async_session') as mock_session_factory, \
         patch.object(scheduler.health_checker, 'check_and_save', new_callable=AsyncMock) as mock_check:
        
        # Setup mocks
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_endpoint
        mock_db.execute.return_value = mock_result
        
        # Set previous state to success
        scheduler.previous_states[sample_endpoint.id] = True
        
        # Set check to succeed
        sample_check_result.success = True
        mock_check.return_value = sample_check_result
        
        # Run check
        await scheduler._check_endpoint(sample_endpoint.id)
        
        # No notifications should be sent
        scheduler.notification_manager.notify_failure.assert_not_called()
        scheduler.notification_manager.notify_recovery.assert_not_called()