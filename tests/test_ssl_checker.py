"""Tests for SSL certificate checker and related API endpoints."""

import asyncio
import ssl
import socket
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.core.ssl_checker import SSLChecker, CertificateInfo, ssl_checker


# ---------------------------------------------------------------------------
# Unit tests for CertificateInfo
# ---------------------------------------------------------------------------


class TestCertificateInfo:
    def test_default_values(self):
        info = CertificateInfo(hostname="example.com", port=443)
        assert info.hostname == "example.com"
        assert info.port == 443
        assert info.is_expired is False
        assert info.is_expiring_soon is False
        assert info.error is None
        assert info.san_list == []
        assert isinstance(info.checked_at, datetime)

    def test_to_dict_serialization(self):
        now = datetime.utcnow()
        info = CertificateInfo(
            hostname="example.com",
            port=443,
            not_before=now - timedelta(days=30),
            not_after=now + timedelta(days=60),
            days_until_expiry=60,
            subject={"commonName": "example.com"},
            issuer={"commonName": "Let's Encrypt"},
        )
        d = info.to_dict()
        assert isinstance(d["not_before"], str)
        assert isinstance(d["not_after"], str)
        assert isinstance(d["checked_at"], str)
        assert d["hostname"] == "example.com"
        assert d["days_until_expiry"] == 60

    def test_to_dict_with_none_dates(self):
        info = CertificateInfo(hostname="test.local", port=8443)
        d = info.to_dict()
        assert d["not_before"] is None
        assert d["not_after"] is None

    def test_error_state(self):
        info = CertificateInfo(
            hostname="bad.host",
            port=443,
            error="Connection refused",
        )
        d = info.to_dict()
        assert d["error"] == "Connection refused"


# ---------------------------------------------------------------------------
# Unit tests for SSLChecker
# ---------------------------------------------------------------------------


class TestSSLChecker:
    def setup_method(self):
        self.checker = SSLChecker(default_timeout=5, expiry_warning_days=30)

    @pytest.mark.asyncio
    async def test_non_https_url(self):
        result = await self.checker.check_certificate("http://example.com/api")
        assert result.error is not None
        assert "not HTTPS" in result.error
        assert result.hostname == "example.com"

    @pytest.mark.asyncio
    async def test_empty_hostname(self):
        result = await self.checker.check_certificate("https:///path")
        assert result.error is not None
        assert "Could not parse hostname" in result.error

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        with patch.object(
            self.checker,
            "_fetch_certificate",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await self.checker.check_certificate("https://slow.example.com")
            assert result.error is not None
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_connection_refused(self):
        with patch.object(
            self.checker,
            "_fetch_certificate",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = await self.checker.check_certificate("https://down.example.com")
            assert result.error is not None
            assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_ssl_verification_error(self):
        with patch.object(
            self.checker,
            "_fetch_certificate",
            side_effect=ssl.SSLCertVerificationError("certificate verify failed"),
        ):
            result = await self.checker.check_certificate("https://selfsigned.example.com")
            assert result.error is not None
            assert "SSL verification error" in result.error

    @pytest.mark.asyncio
    async def test_valid_certificate_parsing(self):
        future_date = datetime.utcnow() + timedelta(days=90)
        past_date = datetime.utcnow() - timedelta(days=30)

        mock_cert = {
            "subject": ((("commonName", "example.com"),),),
            "issuer": (
                (("organizationName", "Let's Encrypt"),),
                (("commonName", "R3"),),
            ),
            "version": 3,
            "serialNumber": "ABC123",
            "notBefore": past_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "notAfter": future_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "subjectAltName": (
                ("DNS", "example.com"),
                ("DNS", "*.example.com"),
            ),
        }

        with patch.object(self.checker, "_fetch_certificate", return_value=mock_cert):
            result = await self.checker.check_certificate("https://example.com")

        assert result.error is None
        assert result.is_expired is False
        assert result.is_expiring_soon is False
        assert result.days_until_expiry > 80
        assert result.subject["commonName"] == "example.com"
        assert result.issuer["commonName"] == "R3"
        assert "example.com" in result.san_list
        assert "*.example.com" in result.san_list

    @pytest.mark.asyncio
    async def test_expired_certificate(self):
        expired_date = datetime.utcnow() - timedelta(days=10)

        mock_cert = {
            "subject": ((("commonName", "expired.example.com"),),),
            "issuer": ((("commonName", "Test CA"),),),
            "notBefore": (expired_date - timedelta(days=365)).strftime(
                "%b %d %H:%M:%S %Y GMT"
            ),
            "notAfter": expired_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "subjectAltName": (),
        }

        with patch.object(self.checker, "_fetch_certificate", return_value=mock_cert):
            result = await self.checker.check_certificate("https://expired.example.com")

        assert result.is_expired is True
        assert result.days_until_expiry < 0

    @pytest.mark.asyncio
    async def test_expiring_soon_certificate(self):
        soon_date = datetime.utcnow() + timedelta(days=15)

        mock_cert = {
            "subject": ((("commonName", "expiring.example.com"),),),
            "issuer": ((("commonName", "Test CA"),),),
            "notBefore": (soon_date - timedelta(days=365)).strftime(
                "%b %d %H:%M:%S %Y GMT"
            ),
            "notAfter": soon_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "subjectAltName": (),
        }

        with patch.object(self.checker, "_fetch_certificate", return_value=mock_cert):
            result = await self.checker.check_certificate("https://expiring.example.com")

        assert result.is_expired is False
        assert result.is_expiring_soon is True
        assert result.days_until_expiry <= 30

    @pytest.mark.asyncio
    async def test_check_multiple_urls(self):
        async def mock_check(url, timeout=None):
            hostname = url.replace("https://", "").split("/")[0]
            return CertificateInfo(
                hostname=hostname,
                port=443,
                days_until_expiry=90,
            )

        with patch.object(self.checker, "check_certificate", side_effect=mock_check):
            results = await self.checker.check_multiple(
                [
                    "https://a.example.com",
                    "https://b.example.com",
                    "https://c.example.com",
                ],
                concurrency=2,
            )

        assert len(results) == 3
        assert results[0].hostname == "a.example.com"
        assert results[1].hostname == "b.example.com"
        assert results[2].hostname == "c.example.com"

    @pytest.mark.asyncio
    async def test_check_multiple_with_exception(self):
        call_count = 0

        async def flaky_check(url, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Simulated failure")
            hostname = url.replace("https://", "").split("/")[0]
            return CertificateInfo(hostname=hostname, port=443)

        with patch.object(self.checker, "check_certificate", side_effect=flaky_check):
            results = await self.checker.check_multiple(
                ["https://ok1.com", "https://fail.com", "https://ok2.com"]
            )

        assert len(results) == 3
        assert results[0].error is None
        assert results[1].error is not None
        assert "Simulated failure" in results[1].error
        assert results[2].error is None

    def test_parse_dn_flat(self):
        dn = (
            (("commonName", "example.com"),),
            (("organizationName", "Test"),),
        )
        result = SSLChecker._parse_dn(dn)
        assert result == {"commonName": "example.com", "organizationName": "Test"}

    def test_parse_cert_date_valid(self):
        dt = SSLChecker._parse_cert_date("Jan  5 12:00:00 2025 GMT")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 5

    def test_parse_cert_date_none(self):
        assert SSLChecker._parse_cert_date(None) is None

    def test_parse_cert_date_invalid(self):
        assert SSLChecker._parse_cert_date("not-a-date") is None

    def test_extract_san(self):
        cert = {
            "subjectAltName": (
                ("DNS", "example.com"),
                ("DNS", "www.example.com"),
                ("IP Address", "1.2.3.4"),
            )
        }
        san = SSLChecker._extract_san(cert)
        assert san == ["example.com", "www.example.com", "1.2.3.4"]

    def test_extract_san_empty(self):
        assert SSLChecker._extract_san({}) == []


# ---------------------------------------------------------------------------
# Unit tests for module-level singleton
# ---------------------------------------------------------------------------


class TestSSLCheckerSingleton:
    def test_singleton_exists(self):
        assert ssl_checker is not None
        assert isinstance(ssl_checker, SSLChecker)
        assert ssl_checker.default_timeout == 10
        assert ssl_checker.expiry_warning_days == 30
