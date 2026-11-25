from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


def test_task_crud_validates_times_and_retains_history():
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
        token = client.post(
            "/auth/register",
            json={"username": "task_user", "email": "task@example.com", "password": "questpass123"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        other_token = client.post(
            "/auth/register",
            json={"username": "other_user", "email": "other@example.com", "password": "questpass123"},
        ).json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        start = datetime.now(timezone.utc) + timedelta(hours=1)
        deadline = start + timedelta(hours=1)
        payload = {
            "title": "Plan review",
            "notes": "Initial notes",
            "start_time": start.isoformat(),
            "deadline": deadline.isoformat(),
        }

        assert client.post("/tasks/", json={"title": "No times"}, headers=headers).status_code == 422
        assert client.post(
            "/tasks/",
            json={**payload, "deadline": (start - timedelta(minutes=5)).isoformat()},
            headers=headers,
        ).status_code == 422

        created = client.post("/tasks/", json=payload, headers=headers)
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert created.json()["user_id"] > 0
        assert client.get(f"/tasks/{task_id}", headers=other_headers).status_code == 404
        assert client.get("/tasks/", headers=headers).json()[0]["id"] == task_id
        assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 200

        edited_payload = {**payload, "title": "Revised review", "notes": "Updated notes"}
        assert client.put(f"/tasks/{task_id}", json=edited_payload, headers=headers).json()["title"] == "Revised review"
        history = client.get(f"/tasks/{task_id}/history", headers=headers)
        assert [entry["action"] for entry in history.json()] == ["created", "updated"]

        assert client.delete(f"/tasks/{task_id}", headers=headers).status_code == 204
        assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404
        assert client.get(f"/tasks/{task_id}/history", headers=headers).json()[-1]["action"] == "deleted"
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()