"""`get_db` commits before the response is sent, so a failed commit is a 5xx."""
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.core import database
from src.core.database import DbSession, get_db


class _FailingCommitSession:
    def __init__(self):
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        raise RuntimeError("commit failed")

    async def rollback(self):
        self.rolled_back = True


@pytest.fixture
def session(monkeypatch):
    session = _FailingCommitSession()
    monkeypatch.setattr(database, "async_session_factory", lambda: session)
    return session


def _client(dependency) -> TestClient:
    app = FastAPI()

    @app.post("/write")
    async def write(session: dependency) -> dict:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_a_failed_commit_through_db_session_is_a_500(session):
    response = _client(DbSession).post("/write")
    assert response.status_code == 500
    assert session.rolled_back is True


def test_a_bare_depends_reports_success_for_a_rolled_back_write(session):
    """Why `DbSession` exists: the default scope commits after the 2xx is sent."""
    response = _client(Annotated[object, Depends(get_db)]).post("/write")
    assert response.status_code == 200
    assert session.rolled_back is True
