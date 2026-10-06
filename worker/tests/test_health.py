import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_without_logging_the_call(caplog: pytest.LogCaptureFixture) -> None:
    with TestClient(create_app()) as client, caplog.at_level(logging.INFO, logger="app.main"):
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"] == "application/json"
    assert not any(record.name == "app.main" for record in caplog.records)
