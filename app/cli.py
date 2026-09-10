"""Console launcher for the FastAPI application."""

import argparse
from typing import Optional, Sequence

import uvicorn

from app.config import load_config


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run the ASGI app using the existing YAML/environment configuration."""
    parser = argparse.ArgumentParser(description="Run the API Monitor FastAPI server.")
    parser.parse_args(argv)

    config = load_config()
    uvicorn.run(
        "app.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        workers=config.api.workers if not config.api.reload else 1,
        log_level=config.logging.level.lower(),
    )
