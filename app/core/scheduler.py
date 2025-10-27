"""Scheduler for periodic endpoint health checks using APScheduler."""

import asyncio
from typing import Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint
from app.core.health_checker import HealthChecker
from app.core.notifications import NotificationManager
from app.config import Config
from app.utils.logger import get_logger
from app.database.session import async_session

logger = get_logger(__name__)


class MonitoringScheduler:
    """
    Scheduler for managing periodic endpoint health checks.
    
    Uses APScheduler to run health checks at different intervals
    for each endpoint.
    """
    
    def __init__(
        self,
        config: Config,
        health_checker: HealthChecker,
        notification_manager: NotificationManager
    ):
        """
        Initialize monitoring scheduler.
        
        Args:
            config: Application configuration
            health_checker: Health checker instance
            notification_manager: Notification manager instance
        """
        self.config = config
        self.health_checker = health_checker
        self.notification_manager = notification_manager
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[int, str] = {}  # endpoint_id -> job_id mapping
        self.previous_states: Dict[int, bool] = {}  # endpoint_id -> success state
        
        logger.info("Monitoring scheduler initialized")
    
    async def start(self) -> None:
        """Start the scheduler and add jobs for all active endpoints."""
        logger.info("Starting monitoring scheduler")
        
        # Start health checker
        await self.health_checker.start()
        
        # Load and schedule all active endpoints
        async with async_session() as db:
            result = await db.execute(
                select(Endpoint).where(Endpoint.is_active == True)
            )
            endpoints = result.scalars().all()
            
            for endpoint in endpoints:
                await self.add_endpoint_job(endpoint)
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info(
            f"Monitoring scheduler started",
            extra={"active_jobs": len(self.jobs)}
        )
    
    async def stop(self) -> None:
        """Stop the scheduler and cleanup resources."""
        logger.info("Stopping monitoring scheduler")
        
        # Stop scheduler
        self.scheduler.shutdown(wait=False)
        
        # Stop health checker
        await self.health_checker.close()
        
        logger.info("Monitoring scheduler stopped")
    
    async def add_endpoint_job(self, endpoint: Endpoint) -> None:
        """
        Add a scheduled job for an endpoint.
        
        Args:
            endpoint: Endpoint to monitor
        """
        if endpoint.id in self.jobs:
            logger.warning(
                f"Job already exists for endpoint",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name
                }
            )
            return
        
        # Create job
        job = self.scheduler.add_job(
            self._check_endpoint,
            trigger=IntervalTrigger(seconds=endpoint.interval),
            args=[endpoint.id],
            id=f"endpoint_{endpoint.id}",
            name=f"Check {endpoint.name}",
            replace_existing=True
        )
        
        self.jobs[endpoint.id] = job.id
        
        logger.info(
            f"Added monitoring job",
            extra={
                "endpoint_id": endpoint.id,
                "endpoint_name": endpoint.name,
                "interval": endpoint.interval,
                "job_id": job.id
            }
        )
    
    async def remove_endpoint_job(self, endpoint_id: int) -> None:
        """
        Remove a scheduled job for an endpoint.
        
        Args:
            endpoint_id: ID of endpoint to stop monitoring
        """
        if endpoint_id not in self.jobs:
            logger.warning(
                f"No job found for endpoint",
                extra={"endpoint_id": endpoint_id}
            )
            return
        
        job_id = self.jobs[endpoint_id]
        self.scheduler.remove_job(job_id)
        del self.jobs[endpoint_id]
        
        # Clean up previous state
        if endpoint_id in self.previous_states:
            del self.previous_states[endpoint_id]
        
        logger.info(
            f"Removed monitoring job",
            extra={
                "endpoint_id": endpoint_id,
                "job_id": job_id
            }
        )
    
    async def update_endpoint_job(self, endpoint: Endpoint) -> None:
        """
        Update a scheduled job for an endpoint.
        
        Args:
            endpoint: Endpoint with updated configuration
        """
        # Remove existing job
        if endpoint.id in self.jobs:
            await self.remove_endpoint_job(endpoint.id)
        
        # Add new job if endpoint is active
        if endpoint.is_active:
            await self.add_endpoint_job(endpoint)
        
        logger.info(
            f"Updated monitoring job",
            extra={
                "endpoint_id": endpoint.id,
                "endpoint_name": endpoint.name,
                "is_active": endpoint.is_active
            }
        )
    
    async def _check_endpoint(self, endpoint_id: int) -> None:
        """
        Perform health check for an endpoint.
        
        This is the main worker function that runs periodically.
        
        Args:
            endpoint_id: ID of endpoint to check
        """
        async with async_session() as db:
            try:
                # Get endpoint
                result = await db.execute(
                    select(Endpoint).where(Endpoint.id == endpoint_id)
                )
                endpoint = result.scalar_one_or_none()
                
                if not endpoint:
                    logger.error(
                        f"Endpoint not found",
                        extra={"endpoint_id": endpoint_id}
                    )
                    # Remove job for non-existent endpoint
                    await self.remove_endpoint_job(endpoint_id)
                    return
                
                if not endpoint.is_active:
                    logger.debug(
                        f"Skipping inactive endpoint",
                        extra={"endpoint_id": endpoint_id}
                    )
                    return
                
                # Perform health check
                logger.debug(
                    f"Performing scheduled check",
                    extra={
                        "endpoint_id": endpoint.id,
                        "endpoint_name": endpoint.name
                    }
                )
                
                check_result = await self.health_checker.check_and_save(
                    endpoint,
                    db
                )
                
                # Get previous state
                previous_success = self.previous_states.get(endpoint_id)
                current_success = check_result.success
                
                # Send notifications based on state changes
                if not current_success:
                    # Endpoint is down
                    if previous_success is None or previous_success:
                        # First failure or transition from up to down
                        logger.warning(
                            f"Endpoint check failed",
                            extra={
                                "endpoint_id": endpoint.id,
                                "endpoint_name": endpoint.name,
                                "error": check_result.error_message
                            }
                        )
                        
                        await self.notification_manager.notify_failure(
                            endpoint,
                            check_result,
                            db
                        )
                
                elif current_success and previous_success == False:
                    # Endpoint recovered (transition from down to up)
                    logger.info(
                        f"Endpoint recovered",
                        extra={
                            "endpoint_id": endpoint.id,
                            "endpoint_name": endpoint.name
                        }
                    )
                    
                    await self.notification_manager.notify_recovery(
                        endpoint,
                        check_result,
                        db
                    )
                
                # Update previous state
                self.previous_states[endpoint_id] = current_success
                
            except Exception as e:
                logger.exception(
                    f"Error during scheduled check",
                    extra={
                        "endpoint_id": endpoint_id,
                        "error": str(e)
                    }
                )
    
    def get_job_status(self, endpoint_id: int) -> Optional[Dict]:
        """
        Get status of a monitoring job.
        
        Args:
            endpoint_id: ID of endpoint
            
        Returns:
            dict: Job status information or None if not found
        """
        if endpoint_id not in self.jobs:
            return None
        
        job_id = self.jobs[endpoint_id]
        job = self.scheduler.get_job(job_id)
        
        if not job:
            return None
        
        return {
            "job_id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
    
    def get_all_jobs_status(self) -> Dict[int, Dict]:
        """
        Get status of all monitoring jobs.
        
        Returns:
            dict: Mapping of endpoint_id to job status
        """
        status = {}
        for endpoint_id in self.jobs:
            job_status = self.get_job_status(endpoint_id)
            if job_status:
                status[endpoint_id] = job_status
        
        return status


# Global scheduler instance
_scheduler: Optional[MonitoringScheduler] = None


def get_scheduler() -> Optional[MonitoringScheduler]:
    """
    Get global scheduler instance.
    
    Returns:
        MonitoringScheduler: Scheduler instance or None if not initialized
    """
    return _scheduler


def set_scheduler(scheduler: MonitoringScheduler) -> None:
    """
    Set global scheduler instance.
    
    Args:
        scheduler: Scheduler instance to set
    """
    global _scheduler
    _scheduler = scheduler