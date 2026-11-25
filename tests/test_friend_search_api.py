from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User


def test_friend_search_returns_matching_public_profiles():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        users = []
        for username in ("alice", "alexander", "charlie"):
            response = client.post(
                "/auth/register",
                json={
                    "username": username,
                    "email": f"{username}@example.com",
                    "password": "questpass123",
                },
            )
            assert response.status_code == 201
            users.append(response.json())

        alice_headers = {
            "Authorization": f"Bearer {users[0]['access_token']}"
        }

        response = client.get(
            "/friends/search",
            params={"q": "ale"},
            headers=alice_headers,
        )

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["username"] == "alexander"
        assert results[0]["friend_id"] == 2
        assert "email" not in results[0]

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_friend_search_excludes_self_and_inactive_users():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        alice = client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "questpass123",
            },
        )
        bob = client.post(
            "/auth/register",
            json={
                "username": "bobby",
                "email": "bob@example.com",
                "password": "questpass123",
            },
        )

        assert alice.status_code == 201
        assert bob.status_code == 201

        with Session(engine) as db:
            inactive_user = db.query(User).filter_by(username="bobby").first()
            inactive_user.is_active = False
            db.commit()

        headers = {
            "Authorization": f"Bearer {alice.json()['access_token']}"
        }

        response = client.get(
            "/friends/search",
            params={"q": "al"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json() == []

        response = client.get(
            "/friends/search",
            params={"q": "bo"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_friend_search_rejects_short_queries_and_requires_auth():
    client = TestClient(app)

    assert client.get(
        "/friends/search",
        params={"q": "a"},
    ).status_code == 401
