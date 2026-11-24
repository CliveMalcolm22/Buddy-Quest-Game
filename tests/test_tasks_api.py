from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task


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