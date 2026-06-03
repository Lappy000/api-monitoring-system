"""Health check and diagnostics endpoints."""

from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app import __version__
from app.schemas.stats import HealthResponse
from app.core.scheduler import get_scheduler
from app.core.circuit_breaker import circuit_breaker_registry
from app.core.ssl_checker import ssl_checker, CertificateInfo
from app.database.session import async_session
from app.models.endpoint import Endpoint
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns system health status including database connection and scheduler status.
    """
    scheduler = get_scheduler()

    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.utcnow().isoformat(),
        database="connected",
        scheduler="running" if scheduler else "stopped",
    )


@router.get("/health/circuit-breakers")
async def circuit_breaker_status() -> JSONResponse:
    """
    Get status of all circuit breakers.

    Returns detailed state information for monitoring and debugging.
    """
    states = circuit_breaker_registry.get_all_states()

    total = len(states)
    open_count = sum(1 for s in states.values() if s["state"] == "open")
    half_open_count = sum(1 for s in states.values() if s["state"] == "half_open")
    closed_count = sum(1 for s in states.values() if s["state"] == "closed")

    return JSONResponse(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_circuit_breakers": total,
                "open": open_count,
                "half_open": half_open_count,
                "closed": closed_count,
            },
            "circuit_breakers": states,
        }
    )


@router.post("/health/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str) -> JSONResponse:
    """
    Reset a specific circuit breaker to CLOSED state.

    Useful for manual recovery after an outage has been resolved.
    """
    success = await circuit_breaker_registry.reset_circuit_breaker(name)
    if not success:
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"Circuit breaker '{name}' not found",
                "available": list(circuit_breaker_registry.circuit_breakers.keys()),
            },
        )

    logger.info("Circuit breaker reset via API", extra={"circuit_name": name})
    return JSONResponse(
        {
            "status": "reset",
            "circuit_breaker": name,
            "new_state": "closed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@router.post("/health/circuit-breakers/reset-all")
async def reset_all_circuit_breakers() -> JSONResponse:
    """Reset all circuit breakers to CLOSED state."""
    await circuit_breaker_registry.reset_all()
    logger.info("All circuit breakers reset via API")
    return JSONResponse(
        {
            "status": "all_reset",
            "count": len(circuit_breaker_registry.circuit_breakers),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@router.get("/health/ssl")
async def check_ssl_certificates(
    endpoint_id: Optional[int] = Query(None, description="Check a specific endpoint by ID"),
    warning_days: int = Query(30, ge=1, le=365, description="Days before expiry to flag as warning"),
) -> JSONResponse:
    """
    Check TLS certificate expiry for monitored HTTPS endpoints.

    Returns certificate details including issuer, validity period,
    days until expiry, and Subject Alternative Names.

    Only HTTPS endpoints are checked; HTTP endpoints are skipped.
    """
    ssl_checker.expiry_warning_days = warning_days

    async with async_session() as db:
        if endpoint_id is not None:
            result = await db.execute(
                select(Endpoint).where(
                    Endpoint.id == endpoint_id,
                    Endpoint.is_active == True,
                )
            )
            endpoints = result.scalars().all()
            if not endpoints:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Active endpoint with id={endpoint_id} not found"},
                )
        else:
            result = await db.execute(
                select(Endpoint).where(Endpoint.is_active == True)
            )
            endpoints = result.scalars().all()

    if not endpoints:
        return JSONResponse({"certificates": [], "summary": _empty_summary()})

    urls = [ep.url for ep in endpoints]
    certs = await ssl_checker.check_multiple(urls)

    certificates = []
    for ep, cert in zip(endpoints, certs):
        entry = cert.to_dict()
        entry["endpoint_id"] = ep.id
        entry["endpoint_name"] = ep.name
        certificates.append(entry)

    expired = [c for c in certificates if c.get("is_expired")]
    expiring = [c for c in certificates if c.get("is_expiring_soon")]
    errors = [c for c in certificates if c.get("error")]
    https_checked = [c for c in certificates if c.get("error") is None or "not HTTPS" not in (c.get("error") or "")]
    skipped = len(certificates) - len(https_checked)

    summary = {
        "total_endpoints": len(certificates),
        "https_checked": len(https_checked) - len(errors),
        "skipped_non_https": skipped,
        "valid": len(https_checked) - len(expired) - len(expiring) - len(errors) + skipped,
        "expiring_soon": len(expiring),
        "expired": len(expired),
        "errors": len(errors),
        "warning_threshold_days": warning_days,
        "checked_at": datetime.utcnow().isoformat(),
    }

    return JSONResponse({"summary": summary, "certificates": certificates})


def _empty_summary() -> Dict[str, Any]:
    return {
        "total_endpoints": 0,
        "https_checked": 0,
        "skipped_non_https": 0,
        "valid": 0,
        "expiring_soon": 0,
        "expired": 0,
        "errors": 0,
        "warning_threshold_days": 30,
        "checked_at": datetime.utcnow().isoformat(),
    }