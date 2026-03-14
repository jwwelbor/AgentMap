"""Benchmark test configuration."""


def pytest_configure(config):
    """Register benchmark marker."""
    config.addinivalue_line(
        "markers",
        "benchmark: Performance benchmark tests (deselected by default)",
    )
