from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


def test_weekly_progress_returns_seven_days_and_daily_totals():
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

        registered = client.post(
            "/auth/register",
            json={
                "username": "weeklyuser",
                "email": "weekly@example.com",
                "password": "questpass123",
            },
        )
        assert registered.status_code == 201

        headers = {
            "Authorization": f"Bearer {registered.json()['access_token']}"
        }

        now = datetime.now(timezone.utc)

        def create_task(title):
            response = client.post(
                "/tasks/",
                json={
                    "title": title,
                    "start_time": now.isoformat(),
                    "deadline": (now + timedelta(hours=1)).isoformat(),
                },
                headers=headers,
            )
            assert response.status_code == 201
            return response.json()["id"]

        first_id = create_task("Weekly task one")
        create_task("Weekly task two")

        completed = client.post(
            f"/tasks/{first_id}/complete",
            headers=headers,
        )
        assert completed.status_code == 200

        response = client.get("/progress/weekly", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data["days"]) == 7

        today = next(
            day for day in data["days"]
            if day["date"] == now.date().isoformat()
        )

        assert today["planned_tasks"] == 2
        assert today["completed_tasks"] == 1
        assert today["points"] == 10
        assert today["completion_rate"] == 50
        assert today["qualifying_day"] is False

    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
