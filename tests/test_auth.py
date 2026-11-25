from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


def test_registration_login_account_and_logout_flow():
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
        registration = client.post(
            "/auth/register",
            json={
                "username": "Alice_1",
                "email": " Alice@Example.com ",
                "password": "questpass123",
                "display_name": "Alice",
            },
        )
        assert registration.status_code == 201
        registration_token = registration.json()["access_token"]
        assert registration.json()["token_type"] == "bearer"

        account = client.get("/auth/me", headers={"Authorization": f"Bearer {registration_token}"})
        assert account.status_code == 200
        assert account.json()["username"] == "alice_1"
        assert account.json()["email"] == "alice@example.com"
        assert "password_hash" not in account.json()

        login = client.post("/auth/login", json={"email": "ALICE@example.com", "password": "questpass123"})
        assert login.status_code == 200
        login_token = login.json()["access_token"]
        assert login_token != registration_token

        logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {login_token}"})
        assert logout.status_code == 204
        revoked_account = client.get("/auth/me", headers={"Authorization": f"Bearer {login_token}"})
        assert revoked_account.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_auth_rejects_duplicate_registration_invalid_credentials_and_missing_token():
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
        user = {"username": "alice", "email": "alice@example.com", "password": "questpass123"}
        assert client.post("/auth/register", json=user).status_code == 201
        assert client.post("/auth/register", json=user).status_code == 409
        assert client.post("/auth/login", json={"email": "alice@example.com", "password": "incorrect123"}).status_code == 401
        assert client.get("/auth/me").status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_registration_validates_email_and_password():
    client = TestClient(app)
    invalid_email = client.post(
        "/auth/register",
        json={"username": "alice", "email": "invalid", "password": "questpass123"},
    )
    weak_password = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password"},
    )

    assert invalid_email.status_code == 422
    assert weak_password.status_code == 422

def test_browser_login_sets_http_only_cookie_and_logout_clears_it():
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

        registration = client.post(
            "/auth/register",
            json={
                "username": "cookieuser",
                "email": "cookie@example.com",
                "password": "questpass123",
            },
        )
        assert registration.status_code == 201

        login = client.post(
            "/auth/login",
            json={
                "email": "cookie@example.com",
                "password": "questpass123",
            },
        )
        assert login.status_code == 200

        cookie = login.cookies.get("buddy_quest_session")
        assert cookie
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=lax" in login.headers["set-cookie"].lower()

        account = client.get("/auth/me")
        assert account.status_code == 200
        assert account.json()["username"] == "cookieuser"

        logout = client.post("/auth/logout")
        assert logout.status_code == 204

        revoked_account = client.get("/auth/me")
        assert revoked_account.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
