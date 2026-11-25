from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.notification import Notification
from app.models.point_event import PointEvent


@pytest.fixture
def social_client():
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

    yield TestClient(app), engine

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client, username):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "questpass123",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_friends(client, alice_headers, bob_headers):
    request = client.post(
        "/friends/request",
        json={"friend_id": 2},
        headers=alice_headers,
    )
    assert request.status_code == 201

    accepted = client.post(
        f"/friends/requests/{request.json()['id']}/accept",
        headers=bob_headers,
    )
    assert accepted.status_code == 200


def test_cheering_awards_points_and_enforces_daily_limit(social_client):
    client, engine = social_client
    alice_headers = register(client, "cheer_alice")
    bob_headers = register(client, "cheer_bob")
    make_friends(client, alice_headers, bob_headers)

    for remaining in range(4, -1, -1):
        response = client.post(
            "/social/users/2/cheer",
            headers=alice_headers,
        )
        assert response.status_code == 201
        assert response.json()["points_awarded"] == 1
        assert response.json()["cheers_remaining"] == remaining

    blocked = client.post(
        "/social/users/2/cheer",
        headers=alice_headers,
    )
    assert blocked.status_code == 429

    with Session(engine) as db:
        points = db.scalar(
            select(func.sum(PointEvent.points)).where(
                PointEvent.user_id == 1,
                PointEvent.source == "cheer",
            )
        )
        notifications = db.scalars(
            select(Notification).where(
                Notification.user_id == 2,
                Notification.type == "cheer",
            )
        ).all()

        assert points == 5
        assert len(notifications) == 5


def test_unaccepted_user_cannot_cheer_or_request_help(social_client):
    client, _ = social_client
    alice_headers = register(client, "stranger_alice")
    register(client, "stranger_bob")

    cheer = client.post(
        "/social/users/2/cheer",
        headers=alice_headers,
    )
    assert cheer.status_code == 403

    task = client.post(
        "/tasks/",
        json={
            "title": "Study",
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        headers=alice_headers,
    )
    assert task.status_code == 201

    help_request = client.post(
        "/social/help-requests",
        json={
            "friend_id": 2,
            "task_id": task.json()["id"],
            "message": "Could you help?",
        },
        headers=alice_headers,
    )
    assert help_request.status_code == 403


def test_accepted_help_awards_helper_and_updates_progress_and_leaderboard(
    social_client,
):
    client, engine = social_client
    alice_headers = register(client, "help_alice")
    bob_headers = register(client, "help_bob")
    make_friends(client, alice_headers, bob_headers)

    task = client.post(
        "/tasks/",
        json={
            "title": "Finish project",
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        headers=alice_headers,
    )
    assert task.status_code == 201
    task_id = task.json()["id"]

    request = client.post(
        "/social/help-requests",
        json={
            "friend_id": 2,
            "task_id": task_id,
            "message": "Please help me finish this task.",
        },
        headers=alice_headers,
    )
    assert request.status_code == 201
    request_id = request.json()["id"]
    assert request.json()["status"] == "open"

    incoming = client.get(
        "/social/help-requests/incoming",
        headers=bob_headers,
    )
    assert incoming.status_code == 200
    assert len(incoming.json()) == 1

    accepted = client.post(
        f"/social/help-requests/{request_id}/accept",
        headers=bob_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    completed = client.post(
        f"/tasks/{task_id}/complete",
        headers=alice_headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    alice_progress = client.get(
        "/progress/summary",
        headers=alice_headers,
    )
    assert alice_progress.status_code == 200
    assert alice_progress.json()["tasks_completed"] == 1
    assert alice_progress.json()["total_points"] == 10

    bob_progress = client.get(
        "/progress/summary",
        headers=bob_headers,
    )
    assert bob_progress.status_code == 200
    assert bob_progress.json()["total_points"] == 5

    leaderboard = client.get(
        "/leaderboard/",
        headers=alice_headers,
    )
    assert leaderboard.status_code == 200

    entries = leaderboard.json()["leaderboard"]
    assert len(entries) == 2
    assert entries[0]["username"] == "help_alice"
    assert entries[0]["points"] == 10
    assert entries[0]["is_you"] is True
    assert entries[1]["username"] == "help_bob"
    assert entries[1]["points"] == 5
    assert entries[1]["is_you"] is False

    with Session(engine) as db:
        helper_events = db.scalars(
            select(PointEvent).where(
                PointEvent.user_id == 2,
                PointEvent.source == "help_friend",
            )
        ).all()
        assert len(helper_events) == 1
        assert helper_events[0].points == 5


def test_help_request_outgoing_decline_and_cancel(social_client):
    client, engine = social_client
    alice_headers = register(client, "lifecycle_alice")
    bob_headers = register(client, "lifecycle_bob")
    make_friends(client, alice_headers, bob_headers)

    deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    first_task = client.post(
        "/tasks/",
        json={"title": "First task", "deadline": deadline},
        headers=alice_headers,
    )
    second_task = client.post(
        "/tasks/",
        json={"title": "Second task", "deadline": deadline},
        headers=alice_headers,
    )
    assert first_task.status_code == 201
    assert second_task.status_code == 201

    first_request = client.post(
        "/social/help-requests",
        json={
            "friend_id": 2,
            "task_id": first_task.json()["id"],
            "message": "Please help with this.",
        },
        headers=alice_headers,
    )
    second_request = client.post(
        "/social/help-requests",
        json={
            "friend_id": 2,
            "task_id": second_task.json()["id"],
            "message": "Please help with this too.",
        },
        headers=alice_headers,
    )
    assert first_request.status_code == 201
    assert second_request.status_code == 201

    outgoing = client.get(
        "/social/help-requests/outgoing",
        headers=alice_headers,
    )
    assert outgoing.status_code == 200
    assert len(outgoing.json()) == 2

    first_id = first_request.json()["id"]
    second_id = second_request.json()["id"]

    declined = client.post(
        f"/social/help-requests/{first_id}/decline",
        headers=bob_headers,
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"

    # Only the requester can cancel their own open request.
    unauthorized_cancel = client.delete(
        f"/social/help-requests/{second_id}",
        headers=bob_headers,
    )
    assert unauthorized_cancel.status_code == 404

    cancelled = client.delete(
        f"/social/help-requests/{second_id}",
        headers=alice_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # Closed requests cannot be declined or cancelled again.
    repeated_decline = client.post(
        f"/social/help-requests/{first_id}/decline",
        headers=bob_headers,
    )
    repeated_cancel = client.delete(
        f"/social/help-requests/{second_id}",
        headers=alice_headers,
    )
    assert repeated_decline.status_code == 404
    assert repeated_cancel.status_code == 404

    with Session(engine) as db:
        notifications = db.scalars(
            select(Notification).where(
                Notification.type == "help_declined"
            )
        ).all()
        assert len(notifications) == 1
        assert notifications[0].user_id == 1
