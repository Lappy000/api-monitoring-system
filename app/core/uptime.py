"""Uptime calculator for analyzing endpoint availability and performance."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UptimeCalculator:
    """
    Calculator for endpoint uptime and availability statistics.
    
    Provides methods to calculate uptime percentages, aggregated statistics,
    and downtime incidents for different time periods.
    """
    
    PERIOD_HOURS = {
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
    }
    
    def __init__(self, db: AsyncSession):
        """
        Initialize uptime calculator.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def calculate_uptime(
        self,
        endpoint_id: int,
        period: str = "24h"
    ) -> float:
        """
        Calculate uptime percentage for an endpoint over a period.
        
        Args:
            endpoint_id: ID of the endpoint
            period: Time period (24h, 7d, 30d)
            
        Returns:
            float: Uptime percentage (0-100)
            
        Example:
            ```python
            calculator = UptimeCalculator(db)
            uptime = await calculator.calculate_uptime(endpoint_id=1, period="7d")
            print(f"7-day uptime: {uptime:.2f}%")
            ```
        """
        if period not in self.PERIOD_HOURS:
            raise ValueError(f"Invalid period: {period}. Use one of: {list(self.PERIOD_HOURS.keys())}")
        
        hours = self.PERIOD_HOURS[period]
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Count total checks
        total_result = await self.db.execute(
            select(func.count(CheckResult.id)).where(
                and_(
                    CheckResult.endpoint_id == endpoint_id,
                    CheckResult.checked_at >= since
                )
            )
        )
        total_checks = total_result.scalar() or 0
        
        if total_checks == 0:
            logger.warning(
                f"No checks found for uptime calculation",
                extra={
                    "endpoint_id": endpoint_id,
                    "period": period
                }
            )
            return 0.0
        
        # Count successful checks
        success_result = await self.db.execute(
            select(func.count(CheckResult.id)).where(
                and_(
                    CheckResult.endpoint_id == endpoint_id,
                    CheckResult.checked_at >= since,
                    CheckResult.success == True
                )
            )
        )
        successful_checks = success_result.scalar() or 0
        
        uptime_percentage = (successful_checks / total_checks) * 100
        
        logger.debug(
            f"Calculated uptime",
            extra={
                "endpoint_id": endpoint_id,
                "period": period,
                "uptime": uptime_percentage,
                "total_checks": total_checks,
                "successful_checks": successful_checks
            }
        )
        
        return round(uptime_percentage, 2)
    
    async def get_statistics(
        self,
        endpoint_id: int,
        period: str = "24h"
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for an endpoint.
        
        Args:
            endpoint_id: ID of the endpoint
            period: Time period (24h, 7d, 30d)
            
        Returns:
            dict: Statistics including uptime, response times, check counts
            
        Example:
            ```python
            stats = await calculator.get_statistics(endpoint_id=1, period="24h")
            print(f"Uptime: {stats['uptime_percentage']}%")
            print(f"Avg Response Time: {stats['avg_response_time']}s")
            ```
        """
        if period not in self.PERIOD_HOURS:
            raise ValueError(f"Invalid period: {period}")
        
        hours = self.PERIOD_HOURS[period]
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get endpoint info
        endpoint_result = await self.db.execute(
            select(Endpoint).where(Endpoint.id == endpoint_id)
        )
        endpoint = endpoint_result.scalar_one_or_none()
        
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")
        
        # Get all checks in period
        checks_result = await self.db.execute(
            select(CheckResult).where(
                and_(
                    CheckResult.endpoint_id == endpoint_id,
                    CheckResult.checked_at >= since
                )
            ).order_by(CheckResult.checked_at.desc())
        )
        checks = checks_result.scalars().all()
        
        if not checks:
            return {
                "endpoint_id": endpoint_id,
                "endpoint_name": endpoint.name,
                "period": period,
                "uptime_percentage": 0.0,
                "total_checks": 0,
                "successful_checks": 0,
                "failed_checks": 0,
                "avg_response_time": None,
                "min_response_time": None,
                "max_response_time": None,
                "last_check": None,
                "last_success": None,
                "last_failure": None,
            }
        
        # Calculate statistics
        successful_checks = [c for c in checks if c.success]
        failed_checks = [c for c in checks if not c.success]
        
        response_times = [c.response_time for c in checks if c.response_time is not None]
        
        uptime_percentage = (len(successful_checks) / len(checks)) * 100
        
        # Find last success and failure
        last_success = next((c for c in checks if c.success), None)
        last_failure = next((c for c in checks if not c.success), None)
        
        stats = {
            "endpoint_id": endpoint_id,
            "endpoint_name": endpoint.name,
            "period": period,
            "uptime_percentage": round(uptime_percentage, 2),
            "total_checks": len(checks),
            "successful_checks": len(successful_checks),
            "failed_checks": len(failed_checks),
            "avg_response_time": round(sum(response_times) / len(response_times), 3) if response_times else None,
            "min_response_time": round(min(response_times), 3) if response_times else None,
            "max_response_time": round(max(response_times), 3) if response_times else None,
            "last_check": checks[0].checked_at.isoformat() if checks else None,
            "last_success": last_success.checked_at.isoformat() if last_success else None,
            "last_failure": last_failure.checked_at.isoformat() if last_failure else None,
        }
        
        logger.info(
            f"Generated statistics",
            extra={
                "endpoint_id": endpoint_id,
                "period": period,
                "uptime": stats["uptime_percentage"]
            }
        )
        
        return stats
    
    async def get_downtime_incidents(
        self,
        endpoint_id: int,
        period: str = "24h",
        min_duration_minutes: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get list of downtime incidents for an endpoint.
        
        An incident is a continuous period of failed checks.
        
        Args:
            endpoint_id: ID of the endpoint
            period: Time period (24h, 7d, 30d)
            min_duration_minutes: Minimum duration to consider an incident
            
        Returns:
            list: List of downtime incidents with start, end, and duration
            
        Example:
            ```python
            incidents = await calculator.get_downtime_incidents(
                endpoint_id=1,
                period="7d",
                min_duration_minutes=5
            )
            for incident in incidents:
                print(f"Downtime: {incident['duration_minutes']} minutes")
            ```
        """
        if period not in self.PERIOD_HOURS:
            raise ValueError(f"Invalid period: {period}")
        
        hours = self.PERIOD_HOURS[period]
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get all failed checks in period
        result = await self.db.execute(
            select(CheckResult).where(
                and_(
                    CheckResult.endpoint_id == endpoint_id,
                    CheckResult.checked_at >= since,
                    CheckResult.success == False
                )
            ).order_by(CheckResult.checked_at)
        )
        failed_checks = result.scalars().all()
        
        if not failed_checks:
            return []
        
        # Group consecutive failures into incidents
        incidents = []
        current_incident = {
            "start": failed_checks[0].checked_at,
            "end": failed_checks[0].checked_at,
            "failures": [failed_checks[0]],
        }
        
        for check in failed_checks[1:]:
            # If this failure is within 2x the check interval of the last failure,
            # consider it part of the same incident
            time_diff = (check.checked_at - current_incident["end"]).total_seconds()
            
            # Assume check interval is around 60 seconds (could be refined)
            if time_diff <= 120:  # 2 minutes
                current_incident["end"] = check.checked_at
                current_incident["failures"].append(check)
            else:
                # Save current incident and start a new one
                duration_minutes = (
                    current_incident["end"] - current_incident["start"]
                ).total_seconds() / 60
                
                if duration_minutes >= min_duration_minutes:
                    incidents.append({
                        "start": current_incident["start"].isoformat(),
                        "end": current_incident["end"].isoformat(),
                        "duration_minutes": round(duration_minutes, 1),
                        "failure_count": len(current_incident["failures"]),
                        "errors": list(set(
                            f.error_message for f in current_incident["failures"]
                            if f.error_message
                        ))
                    })
                
                current_incident = {
                    "start": check.checked_at,
                    "end": check.checked_at,
                    "failures": [check],
                }
        
        # Don't forget the last incident
        duration_minutes = (
            current_incident["end"] - current_incident["start"]
        ).total_seconds() / 60
        
        if duration_minutes >= min_duration_minutes:
            incidents.append({
                "start": current_incident["start"].isoformat(),
                "end": current_incident["end"].isoformat(),
                "duration_minutes": round(duration_minutes, 1),
                "failure_count": len(current_incident["failures"]),
                "errors": list(set(
                    f.error_message for f in current_incident["failures"]
                    if f.error_message
                ))
            })
        
        logger.info(
            f"Found downtime incidents",
            extra={
                "endpoint_id": endpoint_id,
                "period": period,
                "incident_count": len(incidents)
            }
        )
        
        return incidents
    
    async def get_overall_summary(self) -> Dict[str, Any]:
        """
        Get overall summary statistics for all endpoints.
        
        Returns:
            dict: Summary statistics
            
        Example:
            ```python
            summary = await calculator.get_overall_summary()
            print(f"Total endpoints: {summary['total_endpoints']}")
            print(f"Healthy: {summary['healthy_endpoints']}")
            ```
        """
        # Get all endpoints
        endpoints_result = await self.db.execute(select(Endpoint))
        all_endpoints = endpoints_result.scalars().all()
        
        active_endpoints = [e for e in all_endpoints if e.is_active]
        
        # Get recent check for each active endpoint
        healthy_count = 0
        unhealthy_count = 0
        
        for endpoint in active_endpoints:
            # Get most recent check
            result = await self.db.execute(
                select(CheckResult).where(
                    CheckResult.endpoint_id == endpoint.id
                ).order_by(CheckResult.checked_at.desc()).limit(1)
            )
            last_check = result.scalar_one_or_none()
            
            if last_check and last_check.success:
                healthy_count += 1
            else:
                unhealthy_count += 1
        
        summary = {
            "total_endpoints": len(all_endpoints),
            "active_endpoints": len(active_endpoints),
            "inactive_endpoints": len(all_endpoints) - len(active_endpoints),
            "healthy_endpoints": healthy_count,
            "unhealthy_endpoints": unhealthy_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Generated overall summary", extra=summary)
        
        return summary