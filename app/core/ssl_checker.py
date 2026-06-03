"""SSL certificate expiry checker for monitored endpoints.

Extracts TLS certificate information from HTTPS endpoints and tracks
expiry dates, issuer details, and certificate chain validity.
"""

import asyncio
import ssl
import socket
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from dataclasses import dataclass, field, asdict

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CertificateInfo:
    """Parsed TLS certificate information."""

    hostname: str
    port: int
    subject: Dict[str, str] = field(default_factory=dict)
    issuer: Dict[str, str] = field(default_factory=dict)
    serial_number: Optional[str] = None
    version: Optional[int] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    days_until_expiry: Optional[int] = None
    is_expired: bool = False
    is_expiring_soon: bool = False
    san_list: List[str] = field(default_factory=list)
    fingerprint_sha256: Optional[str] = None
    error: Optional[str] = None
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        data = asdict(self)
        for key in ("not_before", "not_after", "checked_at"):
            val = data.get(key)
            if isinstance(val, datetime):
                data[key] = val.isoformat()
        return data


class SSLChecker:
    """
    Async SSL certificate checker.

    Connects to HTTPS endpoints, retrieves the server certificate,
    and parses expiry, issuer, and SAN information.
    """

    def __init__(
        self,
        default_timeout: int = 10,
        expiry_warning_days: int = 30,
    ):
        """
        Args:
            default_timeout: TCP connection timeout in seconds.
            expiry_warning_days: Days before expiry to flag as expiring soon.
        """
        self.default_timeout = default_timeout
        self.expiry_warning_days = expiry_warning_days

    async def check_certificate(
        self,
        url: str,
        timeout: Optional[int] = None,
    ) -> CertificateInfo:
        """
        Retrieve and parse the TLS certificate for the given URL.

        Args:
            url: Full URL (scheme required). Non-HTTPS URLs return an error.
            timeout: Override connection timeout.

        Returns:
            CertificateInfo with parsed certificate data or error details.
        """
        parsed = urlparse(url)

        if parsed.scheme != "https":
            hostname = parsed.hostname or url
            port = parsed.port or 443
            return CertificateInfo(
                hostname=hostname,
                port=port,
                error=f"URL scheme is '{parsed.scheme}', not HTTPS — skipping SSL check",
            )

        hostname = parsed.hostname
        port = parsed.port or 443
        connect_timeout = timeout or self.default_timeout

        if not hostname:
            return CertificateInfo(
                hostname="unknown",
                port=port,
                error="Could not parse hostname from URL",
            )

        try:
            cert_dict = await self._fetch_certificate(
                hostname, port, connect_timeout
            )
            return self._parse_certificate(hostname, port, cert_dict)
        except ssl.SSLCertVerificationError as exc:
            logger.warning(
                "SSL verification failed",
                extra={"hostname": hostname, "port": port, "error": str(exc)},
            )
            return CertificateInfo(
                hostname=hostname,
                port=port,
                error=f"SSL verification error: {exc}",
            )
        except (socket.timeout, asyncio.TimeoutError):
            logger.warning(
                "SSL check timed out",
                extra={
                    "hostname": hostname,
                    "port": port,
                    "timeout": connect_timeout,
                },
            )
            return CertificateInfo(
                hostname=hostname,
                port=port,
                error=f"Connection timed out after {connect_timeout}s",
            )
        except (ConnectionRefusedError, OSError) as exc:
            logger.warning(
                "SSL connection failed",
                extra={"hostname": hostname, "port": port, "error": str(exc)},
            )
            return CertificateInfo(
                hostname=hostname,
                port=port,
                error=f"Connection failed: {exc}",
            )
        except Exception as exc:
            logger.error(
                "Unexpected error during SSL check",
                extra={"hostname": hostname, "port": port, "error": str(exc)},
            )
            return CertificateInfo(
                hostname=hostname,
                port=port,
                error=f"Unexpected error: {exc}",
            )

    async def _fetch_certificate(
        self,
        hostname: str,
        port: int,
        timeout: int,
    ) -> Dict[str, Any]:
        """Open a TLS connection and return the peer certificate dict."""
        ctx = ssl.create_default_context()

        loop = asyncio.get_running_loop()
        cert_dict: Dict[str, Any] = await loop.run_in_executor(
            None,
            self._blocking_fetch,
            hostname,
            port,
            timeout,
            ctx,
        )
        return cert_dict

    @staticmethod
    def _blocking_fetch(
        hostname: str,
        port: int,
        timeout: int,
        ctx: ssl.SSLContext,
    ) -> Dict[str, Any]:
        """Synchronous TLS handshake (runs in executor thread)."""
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as tls:
                cert = tls.getpeercert()
                if cert is None:
                    raise ssl.SSLError("No certificate returned by peer")
                return cert

    def _parse_certificate(
        self,
        hostname: str,
        port: int,
        cert: Dict[str, Any],
    ) -> CertificateInfo:
        """Parse the raw certificate dict into CertificateInfo."""
        subject = self._parse_dn(cert.get("subject", ()))
        issuer = self._parse_dn(cert.get("issuer", ()))

        not_before = self._parse_cert_date(cert.get("notBefore"))
        not_after = self._parse_cert_date(cert.get("notAfter"))

        now = datetime.utcnow()
        days_until_expiry: Optional[int] = None
        is_expired = False
        is_expiring_soon = False

        if not_after is not None:
            delta = not_after - now
            days_until_expiry = delta.days
            is_expired = delta.total_seconds() < 0
            is_expiring_soon = (
                not is_expired and days_until_expiry <= self.expiry_warning_days
            )

        san_list = self._extract_san(cert)
        serial = cert.get("serialNumber")

        info = CertificateInfo(
            hostname=hostname,
            port=port,
            subject=subject,
            issuer=issuer,
            serial_number=serial,
            version=cert.get("version"),
            not_before=not_before,
            not_after=not_after,
            days_until_expiry=days_until_expiry,
            is_expired=is_expired,
            is_expiring_soon=is_expiring_soon,
            san_list=san_list,
        )

        if is_expired:
            logger.error(
                "Certificate is EXPIRED",
                extra={"hostname": hostname, "port": port, "not_after": str(not_after)},
            )
        elif is_expiring_soon:
            logger.warning(
                "Certificate expiring soon",
                extra={
                    "hostname": hostname,
                    "port": port,
                    "days_until_expiry": days_until_expiry,
                },
            )
        else:
            logger.info(
                "Certificate check passed",
                extra={
                    "hostname": hostname,
                    "port": port,
                    "days_until_expiry": days_until_expiry,
                    "issuer_cn": issuer.get("commonName", "N/A"),
                },
            )

        return info

    @staticmethod
    def _parse_dn(dn_tuples: tuple) -> Dict[str, str]:
        """Flatten an X.509 distinguished name tuple into a dict."""
        result: Dict[str, str] = {}
        for rdn in dn_tuples:
            for attr_type, attr_value in rdn:
                result[attr_type] = attr_value
        return result

    @staticmethod
    def _parse_cert_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse certificate date string (e.g. 'Jan  5 12:00:00 2025 GMT')."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%b  %d %H:%M:%S %Y %Z")
            except ValueError:
                return None

    @staticmethod
    def _extract_san(cert: Dict[str, Any]) -> List[str]:
        """Extract Subject Alternative Names from certificate."""
        san_entries = cert.get("subjectAltName", ())
        return [value for _type, value in san_entries]

    async def check_multiple(
        self,
        urls: List[str],
        concurrency: int = 10,
    ) -> List[CertificateInfo]:
        """
        Check certificates for multiple URLs concurrently.

        Args:
            urls: List of endpoint URLs.
            concurrency: Maximum parallel checks.

        Returns:
            List of CertificateInfo results (order matches input).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded_check(url: str) -> CertificateInfo:
            async with semaphore:
                return await self.check_certificate(url)

        tasks = [_bounded_check(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        checked: List[CertificateInfo] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                parsed = urlparse(url)
                checked.append(
                    CertificateInfo(
                        hostname=parsed.hostname or url,
                        port=parsed.port or 443,
                        error=f"Check failed: {result}",
                    )
                )
            else:
                checked.append(result)

        return checked


# Module-level singleton
ssl_checker = SSLChecker()
