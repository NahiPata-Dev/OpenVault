import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECRET_KEY", "test-session-secret-key-that-is-long-enough")
os.environ.setdefault("DEMO_PASSWORD", "test-demo-password")

from app.database import Base
from app.main import create_app
from app.seed import DEMO_USER_IDS, seed_database


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'openvault-test.db'}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    seed_database(session_factory, demo_password="test-demo-password")
    app = create_app(
        database_url=database_url,
        secret_key="test-session-secret-key-that-is-long-enough",
        initialize_database=False,
        demo_mode=True,
    )
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def login(client: TestClient, account_key: str) -> None:
    response = client.post(
        "/api/auth/demo-login",
        json={
            "account_id": DEMO_USER_IDS[account_key],
            "password": "test-demo-password",
        },
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def requester_login(client: TestClient) -> TestClient:
    login(client, "requester_a")
    return client


@pytest.fixture
def manager_login(client: TestClient) -> TestClient:
    login(client, "lab_manager")
    return client
