"""Health checker for monitoring API endpoints with async HTTP requests."""

import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.utils.logger import get_logger
from app.utils.retry import retry_with_backoff, RetryError
from app.core.circuit_breaker import get_health_check_circuit_breaker

logger = get_logger(__name__)


class HealthCheckResult:
    """Result of a health check operation."""
    
    def __init__(
        self,
        success: bool,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """
        Initialize health check result.
        
        Args:
            success: Whether the check was successful
            status_code: HTTP status code (if request succeeded)
            response_time: Response time in seconds
            error_message: Error message (if check failed)
        """
        self.success = success
        self.status_code = status_code
        self.response_time = response_time
        self.error_message = error_message
        self.checked_at = datetime.utcnow()
    
    def __repr__(self) -> str:
        """String representation of health check result."""
        return (
            f"<HealthCheckResult(success={self.success}, "
            f"status_code={self.status_code}, "
            f"response_time={self.response_time})>"
        )


class HealthChecker:
    """
    Health checker for monitoring API endpoints.
    
    Performs async HTTP requests with timeout handling, error categorization,
    and response time measurement. Uses circuit breaker pattern for fault tolerance.
    """
    
    def __init__(
        self,
        max_concurrent: int = 20,
        default_timeout: int = 5
    ):
        """
        Initialize health checker.
        
        Args:
            max_concurrent: Maximum concurrent checks
            default_timeout: Default timeout in seconds
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            "Health checker initialized",
            extra={
                "max_concurrent": max_concurrent,
                "default_timeout": default_timeout
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self) -> None:
        """Start the HTTP session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.default_timeout)
            connector = aiohttp.TCPConnector(limit=self.max_concurrent)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
            logger.info("HTTP session started")
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP session closed")
    
    async def check_endpoint(
        self,
        endpoint: Endpoint,
        use_retry: bool = True
    ) -> HealthCheckResult:
        """
        Perform health check on a single endpoint with circuit breaker protection.
        
        Args:
            endpoint: Endpoint to check
            use_retry: Whether to use retry mechanism
            
        Returns:
            HealthCheckResult: Result of the health check
            
        Example:
            ```python
            async with HealthChecker() as checker:
                result = await checker.check_endpoint(endpoint)
                print(f"Success: {result.success}, Status: {result.status_code}")
            ```
        """
        logger.debug(
            f"Starting health check",
            extra={
                "endpoint_id": endpoint.id,
                "endpoint_name": endpoint.name,
                "url": endpoint.url,
                "method": endpoint.method
            }
        )
        
        # Get circuit breaker for this endpoint
        circuit_breaker = get_health_check_circuit_breaker(endpoint.name)
        
        # Calculate timeout for circuit breaker call (endpoint timeout + buffer)
        circuit_breaker_timeout = endpoint.timeout + 2
        
        if use_retry:
            try:
                # Wrap the actual check with circuit breaker and retry
                async def _check_with_circuit_breaker():
                    # Add timeout protection to prevent hanging
                    try:
                        return await asyncio.wait_for(
                            circuit_breaker.call(self._perform_check, endpoint),
                            timeout=circuit_breaker_timeout
                        )
                    except asyncio.TimeoutError:
                        raise Exception(f"Circuit breaker call timed out after {circuit_breaker_timeout}s")
                
                return await retry_with_backoff(
                    _check_with_circuit_breaker,
                    max_attempts=3,
                    base_delay=1.0,
                    exceptions=(aiohttp.ClientError, asyncio.TimeoutError, Exception)
                )
            except RetryError as e:
                logger.error(
                    f"Health check failed after retries",
                    extra={
                        "endpoint_id": endpoint.id,
                        "endpoint_name": endpoint.name,
                        "error": str(e)
                    }
                )
                return HealthCheckResult(
                    success=False,
                    error_message=f"Failed after retries: {str(e)}"
                )
        else:
            # Use circuit breaker without retry but with timeout protection
            try:
                return await asyncio.wait_for(
                    circuit_breaker.call(self._perform_check, endpoint),
                    timeout=circuit_breaker_timeout
                )
            except asyncio.TimeoutError:
                error_msg = f"Circuit breaker call timed out after {circuit_breaker_timeout}s"
                logger.error(
                    f"Health check timeout",
                    extra={
                        "endpoint_id": endpoint.id,
                        "endpoint_name": endpoint.name,
                        "timeout": circuit_breaker_timeout
                    }
                )
                return HealthCheckResult(
                    success=False,
                    error_message=error_msg
                )
            except Exception as e:
                logger.error(
                    f"Health check failed with circuit breaker",
                    extra={
                        "endpoint_id": endpoint.id,
                        "endpoint_name": endpoint.name,
                        "error": str(e)
                    }
                )
                return HealthCheckResult(
                    success=False,
                    error_message=str(e)
                )
    
    async def _perform_check(self, endpoint: Endpoint) -> HealthCheckResult:
        """
        Perform the actual HTTP request.
        
        Args:
            endpoint: Endpoint to check
            
        Returns:
            HealthCheckResult: Result of the check
        """
        if not self.session:
            await self.start()
        
        start_time = time.time()
        
        try:
            # Prepare request parameters
            kwargs: Dict[str, Any] = {
                "timeout": aiohttp.ClientTimeout(total=endpoint.timeout)
            }
            
            # Add headers if provided
            if endpoint.headers:
                kwargs["headers"] = endpoint.headers
            
            # Add body for POST/PUT/PATCH requests
            if endpoint.method.upper() in ("POST", "PUT", "PATCH") and endpoint.body:
                kwargs["json"] = endpoint.body
            
            # Perform request
            async with self.session.request(
                method=endpoint.method.upper(),
                url=endpoint.url,
                **kwargs
            ) as response:
                # Calculate response time
                response_time = time.time() - start_time
                
                # Read response (to ensure full request completion)
                await response.read()
                
                # Check if status matches expected
                success = response.status == endpoint.expected_status
                
                logger.info(
                    f"Health check completed",
                    extra={
                        "endpoint_id": endpoint.id,
                        "endpoint_name": endpoint.name,
                        "status_code": response.status,
                        "expected_status": endpoint.expected_status,
                        "response_time": response_time,
                        "success": success
                    }
                )
                
                return HealthCheckResult(
                    success=success,
                    status_code=response.status,
                    response_time=response_time,
                    error_message=None if success else f"Expected status {endpoint.expected_status}, got {response.status}"
                )
        
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            error_msg = f"Request timed out after {endpoint.timeout}s"
            
            logger.warning(
                f"Health check timeout",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name,
                    "timeout": endpoint.timeout,
                    "response_time": response_time
                }
            )
            
            return HealthCheckResult(
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
        
        except aiohttp.ClientConnectorError as e:
            response_time = time.time() - start_time
            error_msg = f"Connection error: {str(e)}"
            
            logger.error(
                f"Health check connection error",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name,
                    "error": str(e),
                    "response_time": response_time
                }
            )
            
            return HealthCheckResult(
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
        
        except aiohttp.ClientError as e:
            response_time = time.time() - start_time
            error_msg = f"Client error: {str(e)}"
            
            logger.error(
                f"Health check client error",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name,
                    "error": str(e),
                    "response_time": response_time
                }
            )
            
            return HealthCheckResult(
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
        
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Unexpected error: {str(e)}"
            
            logger.exception(
                f"Health check unexpected error",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name,
                    "error": str(e),
                    "response_time": response_time
                }
            )
            
            return HealthCheckResult(
                success=False,
                response_time=response_time,
                error_message=error_msg
            )
    
    async def check_and_save(
        self,
        endpoint: Endpoint,
        db: AsyncSession
    ) -> CheckResult:
        """
        Check endpoint and save result to database.
        
        Args:
            endpoint: Endpoint to check
            db: Database session
            
        Returns:
            CheckResult: Database record of the check result
        """
        # Perform health check
        result = await self.check_endpoint(endpoint)
        
        # Create database record
        check_result = CheckResult(
            endpoint_id=endpoint.id,
            status_code=result.status_code,
            response_time=result.response_time,
            success=result.success,
            error_message=result.error_message,
            checked_at=result.checked_at
        )
        
        # Save to database
        db.add(check_result)
        await db.commit()
        await db.refresh(check_result)
        
        logger.info(
            f"Check result saved to database",
            extra={
                "endpoint_id": endpoint.id,
                "check_result_id": check_result.id,
                "success": result.success
            }
        )
        
        return check_result
    
    async def check_all_active(
        self,
        db: AsyncSession
    ) -> list[CheckResult]:
        """
        Check all active endpoints and save results.
        
        Args:
            db: Database session
            
        Returns:
            list[CheckResult]: List of check results
        """
        # Get all active endpoints
        result = await db.execute(
            select(Endpoint).where(Endpoint.is_active == True)
        )
        endpoints = result.scalars().all()
        
        logger.info(
            f"Checking all active endpoints",
            extra={"count": len(endpoints)}
        )
        
        # Check all endpoints concurrently with circuit breakers
        tasks = []
        for endpoint in endpoints:
            # Get circuit breaker for this endpoint
            circuit_breaker = get_health_check_circuit_breaker(endpoint.name)
            
            # Create task with circuit breaker protection and timeout
            async def check_with_circuit_breaker(endpoint):
                try:
                    # Add timeout protection (5 seconds default + 2 second buffer)
                    timeout = getattr(endpoint, 'timeout', 5) + 2
                    return await asyncio.wait_for(
                        circuit_breaker.call(self.check_and_save, endpoint, db),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        f"Health check timed out in circuit breaker",
                        extra={
                            "endpoint_id": endpoint.id,
                            "endpoint_name": endpoint.name,
                            "timeout": timeout
                        }
                    )
                    return CheckResult(
                        endpoint_id=endpoint.id,
                        success=False,
                        error_message=f"Circuit breaker call timed out after {timeout}s",
                        checked_at=datetime.utcnow()
                    )
                except Exception as e:
                    logger.error(
                        f"Health check failed due to circuit breaker",
                        extra={
                            "endpoint_id": endpoint.id,
                            "endpoint_name": endpoint.name,
                            "error": str(e)
                        }
                    )
                    # Return a failed check result
                    return CheckResult(
                        endpoint_id=endpoint.id,
                        success=False,
                        error_message=f"Circuit breaker error: {str(e)}",
                        checked_at=datetime.utcnow()
                    )
            
            tasks.append(check_with_circuit_breaker(endpoint))
        
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and count successes
        valid_results = [r for r in check_results if isinstance(r, CheckResult)]
        success_count = sum(1 for r in valid_results if r.success)
        
        logger.info(
            f"Completed checking all active endpoints",
            extra={
                "total": len(endpoints),
                "successful": success_count,
                "failed": len(valid_results) - success_count
            }
        )
        
        return valid_results

