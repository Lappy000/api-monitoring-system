"""Regression tests for packaging the FastAPI application, not backfill modules."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_build_manifest_packages_the_fastapi_application():
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["build-system"]["build-backend"] == "setuptools.build_meta"
    assert manifest["tool"]["setuptools"]["packages"]["find"] == {
        "where": ["."],
        "include": ["app", "app.*"],
        "namespaces": False,
    }
    assert manifest["tool"]["setuptools"]["dynamic"]["dependencies"] == {
        "file": ["requirements.txt"]
    }


def test_dev_extra_matches_requirements_dev():
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.strip()
        for line in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith(("#", "-r "))
    }
    assert set(manifest["project"]["optional-dependencies"]["dev"]) == requirements


def test_distribution_uses_the_app_version_and_entry_point():
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "app.__version__"}
    assert manifest["project"]["scripts"]["api-monitoring-system"] == "app.cli:main"
    assert manifest["project"]["requires-python"] == ">=3.11"
