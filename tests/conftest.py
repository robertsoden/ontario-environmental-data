"""Pytest configuration for async tests.

To run async tests, ensure pytest-asyncio is installed:
    pip install pytest-asyncio

Or use the dev dependencies:
    pip install -e ".[dev]"
"""

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
