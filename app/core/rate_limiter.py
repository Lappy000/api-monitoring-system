"""Shared rate limiter instance for the application."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create single limiter instance shared across all modules
limiter = Limiter(key_func=get_remote_address)