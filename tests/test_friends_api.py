
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

        # Alice should see Bob's profile.
        alice_friend = alice_friends.json()[0]
        assert alice_friend["friendship_id"] == request_id
        assert alice_friend["friend_id"] == 2
        assert alice_friend["username"] == "bob"
        assert "friends_since" in alice_friend

        # Bob should see Alice's profile, not his own.
        bob_friend = bob_friends.json()[0]
        assert bob_friend["friendship_id"] == request_id
        assert bob_friend["friend_id"] == 1
        assert bob_friend["username"] == "alice"
        assert "friends_since" in bob_friend

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

def test_friend_request_edge_cases():
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
        for username in ("alice", "bob", "charlie"):
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
        bob_headers = {
            "Authorization": f"Bearer {users[1]['access_token']}"
        }
        charlie_headers = {
            "Authorization": f"Bearer {users[2]['access_token']}"
        }

        # A user cannot request themselves.
        self_request = client.post(
            "/friends/request",
            json={"friend_id": 1},
            headers=alice_headers,
        )
        assert self_request.status_code == 400

        # Alice sends Bob a request.
        request = client.post(
            "/friends/request",
            json={"friend_id": 2},
            headers=alice_headers,
        )
        assert request.status_code == 201
        request_id = request.json()["id"]

        # Bob cannot create a reverse request while Alice's is pending.
        reverse_request = client.post(
            "/friends/request",
            json={"friend_id": 1},
            headers=bob_headers,
        )
        assert reverse_request.status_code == 409

        # Charlie cannot accept a request addressed to Bob.
        unauthorized_accept = client.post(
            f"/friends/requests/{request_id}/accept",
            headers=charlie_headers,
        )
        assert unauthorized_accept.status_code == 404

        # Bob can decline his incoming request.
        declined = client.post(
            f"/friends/requests/{request_id}/decline",
            headers=bob_headers,
        )
        assert declined.status_code == 200
        assert declined.json()["status"] == "declined"

        # The same request cannot be declined again.
        repeated_decline = client.post(
            f"/friends/requests/{request_id}/decline",
            headers=bob_headers,
        )
        assert repeated_decline.status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_declined_friend_request_can_be_retried_by_either_user():
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

        for username in ("alice", "bob"):
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
        bob_headers = {
            "Authorization": f"Bearer {users[1]['access_token']}"
        }

        first_request = client.post(
            "/friends/request",
            json={"friend_id": 2},
            headers=alice_headers,
        )
        assert first_request.status_code == 201
        request_id = first_request.json()["id"]

        declined = client.post(
            f"/friends/requests/{request_id}/decline",
            headers=bob_headers,
        )
        assert declined.status_code == 200
        assert declined.json()["status"] == "declined"

        retry = client.post(
            "/friends/request",
            json={"friend_id": 1},
            headers=bob_headers,
        )
        assert retry.status_code == 201
        assert retry.json()["id"] == request_id
        assert retry.json()["user_id"] == 2
        assert retry.json()["friend_id"] == 1
        assert retry.json()["status"] == "pending"

        with Session(engine) as db:
            friendships = db.scalars(select(Friendship)).all()
            assert len(friendships) == 1
            assert friendships[0].status == "pending"

            notifications = db.scalars(select(Notification)).all()
            assert len(notifications) == 2
            assert notifications[1].user_id == 1

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
