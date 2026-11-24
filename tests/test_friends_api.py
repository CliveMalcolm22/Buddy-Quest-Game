
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.friendship import Friendship
from app.models.notification import Notification


def test_friend_request_lifecycle():
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
                "username": "bob",
                "email": "bob@example.com",
                "password": "questpass123",
            },
        )

        assert alice.status_code == 201
        assert bob.status_code == 201

        alice_token = alice.json()["access_token"]
        bob_token = bob.json()["access_token"]

        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        # Alice sends Bob a friend request.
        request = client.post(
            "/friends/request",
            json={"friend_id": 2},
            headers=alice_headers,
        )
        assert request.status_code == 201
        request_data = request.json()
        assert request_data["user_id"] == 1
        assert request_data["friend_id"] == 2
        assert request_data["status"] == "pending"

        request_id = request_data["id"]

        # Bob receives the request.
        incoming = client.get(
            "/friends/requests/incoming",
            headers=bob_headers,
        )
        assert incoming.status_code == 200
        assert len(incoming.json()) == 1
        assert incoming.json()[0]["id"] == request_id

        # Alice sees the outgoing request.
        outgoing = client.get(
            "/friends/requests/outgoing",
            headers=alice_headers,
        )
        assert outgoing.status_code == 200
        assert len(outgoing.json()) == 1

        # Duplicate request is rejected.
        duplicate = client.post(
            "/friends/request",
            json={"friend_id": 2},
            headers=alice_headers,
        )
        assert duplicate.status_code == 409

        # Bob accepts the request.
        accepted = client.post(
            f"/friends/requests/{request_id}/accept",
            headers=bob_headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"

        # Both users can see the accepted friendship.
        alice_friends = client.get("/friends/", headers=alice_headers)
        bob_friends = client.get("/friends/", headers=bob_headers)

        assert len(alice_friends.json()) == 1
        assert len(bob_friends.json()) == 1

        # A second acceptance is rejected.
        repeated_accept = client.post(
            f"/friends/requests/{request_id}/accept",
            headers=bob_headers,
        )
        assert repeated_accept.status_code == 404

        with Session(engine) as db:
            notifications = db.scalars(
                select(Notification).order_by(Notification.id)
            ).all()
            assert len(notifications) == 2
            assert notifications[0].type == "friend_request"
            assert notifications[1].type == "friend_request_accepted"

            friendship = db.get(Friendship, request_id)
            assert friendship.status == "accepted"

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_friend_requests_require_authentication():
    client = TestClient(app)

    assert client.get("/friends/").status_code == 401
    assert client.post(
        "/friends/request",
        json={"friend_id": 2},
    ).status_code == 401
