"""
ACMS Nox Configuration
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""

from __future__ import annotations

import pathlib

import nox

REPO_DIR = pathlib.Path(__file__).parent


@nox.session(python="3.11")
def lint(session: nox.Session) -> None:
    """Run Ruff and Black in check mode."""
    session.install("ruff", "black")
    session.run("ruff", "check", "core")
    session.run("black", "--check", "core", "noxfile.py")


@nox.session(python="3.11")
def tests(session: nox.Session) -> None:
    """Execute the pytest suite when tests are available."""
    tests_path = REPO_DIR / "tests"
    if not tests_path.exists():
        session.log("No tests directory detected; skipping pytest run.")
        return
    session.install("-r", "requirements.txt")
    session.install("pytest")
    session.run("pytest", str(tests_path))


@nox.session(name="type-check", python="3.11")
def type_check(session: nox.Session) -> None:
    """Run mypy for static type checking."""
    session.install("mypy")
    session.run("mypy", "core")


@nox.session(name="format", python="3.11")
def format_code(session: nox.Session) -> None:
    """Format the codebase with Black."""
    session.install("black")
    session.run("black", "core", "noxfile.py")
