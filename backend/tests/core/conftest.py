"""Hermetic fixtures for TASK-101 core tests.

Every test gets its own SQLite database via a `get_db` dependency override;
the app lifespan never runs here, so no request can reach the shared
development database regardless of conftest import order.
"""
import pytest

from helpers import build_isolated_client


@pytest.fixture
def client(tmp_path):
    test_client, engine = build_isolated_client(tmp_path)
    yield test_client
    engine.dispose()
