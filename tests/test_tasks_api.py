from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.point_event import PointEvent


def test_task_crud_and_user_isolation():
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

        # Register two users.
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

        alice_headers = {
            "Authorization": f"Bearer {alice.json()['access_token']}"
        }
        bob_headers = {
            "Authorization": f"Bearer {bob.json()['access_token']}"
        }

        # Alice creates a task.
        created = client.post(
            "/tasks/",
            json={
                "title": "Finish BuddyQuest",
                "notes": "Complete task API implementation",
            },
            headers=alice_headers,
        )

        assert created.status_code == 201
        task = created.json()
        task_id = task["id"]

        assert task["title"] == "Finish BuddyQuest"
        assert task["user_id"] == 1
        assert task["status"] == "pending"
        assert task["completion_points"] == 0

        # Alice can retrieve her task.
        retrieved = client.get(
            f"/tasks/{task_id}",
            headers=alice_headers,
        )
        assert retrieved.status_code == 200
        assert retrieved.json()["id"] == task_id

        # Alice can see her task in her task list.
        alice_tasks = client.get("/tasks/", headers=alice_headers)
        assert alice_tasks.status_code == 200
        assert len(alice_tasks.json()) == 1
        assert alice_tasks.json()[0]["id"] == task_id

        # Bob's task list must not contain Alice's task.
        bob_tasks = client.get("/tasks/", headers=bob_headers)
        assert bob_tasks.status_code == 200
        assert bob_tasks.json() == []

        # Bob cannot retrieve Alice's task.
        assert client.get(
            f"/tasks/{task_id}",
            headers=bob_headers,
        ).status_code == 404

        # Bob cannot update Alice's task.
        unauthorized_update = client.put(
            f"/tasks/{task_id}",
            json={
                "title": "Changed by Bob",
                "notes": "This should not work",
            },
            headers=bob_headers,
        )
        assert unauthorized_update.status_code == 404

        # Bob cannot delete Alice's task.
        unauthorized_delete = client.delete(
            f"/tasks/{task_id}",
            headers=bob_headers,
        )
        assert unauthorized_delete.status_code == 404

        # Alice can update her task.
        updated = client.put(
            f"/tasks/{task_id}",
            json={
                "title": "Finish BuddyQuest API",
                "notes": "Task CRUD tests are passing",
            },
            headers=alice_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Finish BuddyQuest API"
        assert updated.json()["notes"] == "Task CRUD tests are passing"

        # Verify the database still has Alice's updated task.
        with Session(engine) as db:
            saved_task = db.scalar(
                select(Task).where(Task.id == task_id)
            )
            assert saved_task is not None
            assert saved_task.user_id == 1
            assert saved_task.title == "Finish BuddyQuest API"

        # Alice can delete her task.
        deleted = client.delete(
            f"/tasks/{task_id}",
            headers=alice_headers,
        )
        assert deleted.status_code == 204

        # Deleted task can no longer be retrieved.
        assert client.get(
            f"/tasks/{task_id}",
            headers=alice_headers,
        ).status_code == 404

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_task_routes_require_authentication():
    client = TestClient(app)

    assert client.get("/tasks/").status_code == 401

    assert client.post(
        "/tasks/",
        json={"title": "Unauthorised task"},
    ).status_code == 401

def test_task_completion_scoring_grace_period_and_idempotency():
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
                "username": "completion_alice",
                "email": "completion_alice@example.com",
                "password": "questpass123",
            },
        )
        bob = client.post(
            "/auth/register",
            json={
                "username": "completion_bob",
                "email": "completion_bob@example.com",
                "password": "questpass123",
            },
        )

        assert alice.status_code == 201
        assert bob.status_code == 201

        alice_headers = {
            "Authorization": f"Bearer {alice.json()['access_token']}"
        }
        bob_headers = {
            "Authorization": f"Bearer {bob.json()['access_token']}"
        }

        now = datetime.now(timezone.utc)

        def create_task(title, deadline):
            response = client.post(
                "/tasks/",
                json={
                    "title": title,
                    "deadline": deadline.isoformat(),
                },
                headers=alice_headers,
            )
            assert response.status_code == 201
            return response.json()["id"]

        on_time_id = create_task("On-time task", now + timedelta(minutes=10))
        late_id = create_task("Late task", now - timedelta(minutes=2))
        expired_id = create_task("Expired task", now - timedelta(minutes=10))

        # Another user cannot complete Alice's task.
        forbidden = client.post(
            f"/tasks/{on_time_id}/complete",
            headers=bob_headers,
        )
        assert forbidden.status_code == 404

        # Completing before the deadline awards 10 points.
        on_time = client.post(
            f"/tasks/{on_time_id}/complete",
            headers=alice_headers,
        )
        assert on_time.status_code == 200
        assert on_time.json()["status"] == "completed"
        assert on_time.json()["completion_points"] == 10
        assert on_time.json()["completed_at"] is not None

        # Repeating completion must not award points again.
        duplicate = client.post(
            f"/tasks/{on_time_id}/complete",
            headers=alice_headers,
        )
        assert duplicate.status_code == 409

        # Completing two minutes after the deadline is still within grace.
        late = client.post(
            f"/tasks/{late_id}/complete",
            headers=alice_headers,
        )
        assert late.status_code == 200
        assert late.json()["status"] == "completed"
        assert late.json()["completion_points"] == 3

        # Completing after the five-minute grace period records a miss.
        expired = client.post(
            f"/tasks/{expired_id}/complete",
            headers=alice_headers,
        )
        assert expired.status_code == 409

        with Session(engine) as db:
            events = db.scalars(
                select(PointEvent).order_by(PointEvent.id)
            ).all()

            assert len(events) == 3

            events_by_task = {event.task_id: event for event in events}

            assert events_by_task[on_time_id].source == "task_completion_on_time"
            assert events_by_task[on_time_id].points == 10

            assert events_by_task[late_id].source == "task_completion_late"
            assert events_by_task[late_id].points == 3

            assert events_by_task[expired_id].source == "task_missed"
            assert events_by_task[expired_id].points == 0

            expired_task = db.get(Task, expired_id)
            assert expired_task.status == "missed"
            assert expired_task.completion_points == 0

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_deadline_extension_audit_limit_and_fair_play():
    from app.models.deadline_extension import DeadlineExtension

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

        alice_headers = {
            "Authorization": f"Bearer {alice.json()['access_token']}"
        }
        bob_headers = {
            "Authorization": f"Bearer {bob.json()['access_token']}"
        }
        alice_account = client.get("/auth/me", headers=alice_headers)
        assert alice_account.status_code == 200
        alice_id = alice_account.json()["id"]

        def create_task(title, deadline):
            response = client.post(
                "/tasks/",
                json={
                    "title": title,
                    "deadline": deadline.isoformat(),
                },
                headers=alice_headers,
            )
            assert response.status_code == 201
            return response.json()["id"]

        now = datetime.now(timezone.utc)
        original_deadline = now + timedelta(hours=1)
        extended_deadline = now + timedelta(hours=2)

        task_id = create_task("Extend this task", original_deadline)

        # Another user cannot extend Alice's task.
        forbidden = client.post(
            f"/tasks/{task_id}/extend",
            json={"new_deadline": extended_deadline.isoformat()},
            headers=bob_headers,
        )
        assert forbidden.status_code == 404

        # A new deadline must be later than the existing deadline.
        invalid_extension = client.post(
            f"/tasks/{task_id}/extend",
            json={
                "new_deadline": (
                    original_deadline - timedelta(minutes=1)
                ).isoformat()
            },
            headers=alice_headers,
        )
        assert invalid_extension.status_code == 400

        # Alice can extend the task once.
        extended = client.post(
            f"/tasks/{task_id}/extend",
            json={"new_deadline": extended_deadline.isoformat()},
            headers=alice_headers,
        )
        assert extended.status_code == 200
        returned_deadline = datetime.fromisoformat(
            extended.json()["deadline"]
        ).replace(tzinfo=timezone.utc)
        assert returned_deadline == extended_deadline

        # The audit record preserves the original and new deadlines.
        with Session(engine) as db:
            audit = db.scalar(
                select(DeadlineExtension).where(
                    DeadlineExtension.task_id == task_id
                )
            )
            assert audit is not None
            assert audit.extended_by_user_id == alice_id
            assert audit.original_deadline.replace(
                tzinfo=timezone.utc
            ) == original_deadline
            assert audit.new_deadline.replace(
                tzinfo=timezone.utc
            ) == extended_deadline
            assert audit.extended_at is not None

        # A second extension is rejected.
        second_extension = client.post(
            f"/tasks/{task_id}/extend",
            json={
                "new_deadline": (
                    extended_deadline + timedelta(hours=1)
                ).isoformat()
            },
            headers=alice_headers,
        )
        assert second_extension.status_code == 409

        # Ordinary updates cannot change the deadline.
        bypass_extension = client.put(
            f"/tasks/{task_id}",
            json={
                "deadline": (
                    extended_deadline + timedelta(hours=1)
                ).isoformat()
            },
            headers=alice_headers,
        )
        assert bypass_extension.status_code == 422

        # Ordinary edits still work before the extended deadline.
        normal_update = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated task title"},
            headers=alice_headers,
        )
        assert normal_update.status_code == 200
        assert normal_update.json()["title"] == "Updated task title"

        # An expired task cannot be extended or edited.
        expired_id = create_task(
            "Expired task",
            datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        expired_extension = client.post(
            f"/tasks/{expired_id}/extend",
            json={
                "new_deadline": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat()
            },
            headers=alice_headers,
        )
        assert expired_extension.status_code == 409

        expired_update = client.put(
            f"/tasks/{expired_id}",
            json={"title": "Too late"},
            headers=alice_headers,
        )
        assert expired_update.status_code == 409

        # A completed task cannot be edited.
        completed_id = create_task(
            "Completed task",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        completed = client.post(
            f"/tasks/{completed_id}/complete",
            headers=alice_headers,
        )
        assert completed.status_code == 200

        completed_update = client.put(
            f"/tasks/{completed_id}",
            json={"title": "Change after completion"},
            headers=alice_headers,
        )
        assert completed_update.status_code == 409

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
