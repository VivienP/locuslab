"""Pytest configuration and shared fixtures."""

from __future__ import annotations


def pytest_addoption(parser: object) -> None:
    """Add --update-goldens option for regenerating golden snapshot files."""
    p = parser  # type: ignore[union-attr]
    p.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Regenerate golden snapshot files instead of comparing against them.",
    )
