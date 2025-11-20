"""Pytest configuration for async tests and markers.

To run async tests, ensure pytest-asyncio is installed:
    pip install pytest-asyncio

Or use the dev dependencies:
    pip install -e ".[dev]"

Test markers:
    integration: Tests that make real API calls (slow, may fail due to network)

Run tests:
    pytest tests/                           # Run all tests except integration
    pytest tests/ -m integration           # Run only integration tests
    pytest tests/ -m "not integration"     # Explicitly skip integration tests
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests that make real API calls (deselect with '-m \"not integration\"')",
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip integration tests unless explicitly requested.

    Integration tests are skipped by default because they:
    - Make real API calls
    - Are slower
    - May fail due to network issues or API changes
    """
    # Don't auto-skip if user explicitly selected integration tests
    if config.getoption("-m") == "integration":
        return

    # Skip integration tests by default
    skip_integration = pytest.mark.skip(
        reason="Integration test - skipped by default. Run with: pytest -m integration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
